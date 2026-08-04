"""
UpdateManager — 版本检查 & 自动更新
异步检查私有仓库 version.json，从公开仓库 Release/app.zip 下载更新包，
校验 SHA-256 后解压，生成 updater.bat 替换脚本
"""
import hashlib
import os
import sys
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from PyQt5.QtCore import Qt, QObject, QUrl, pyqtSignal, QEventLoop
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QBrush, QPen
from PyQt5.QtWidgets import (
    QDialog, QLabel, QMessageBox, QPushButton, QProgressDialog,
    QApplication
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from app_config import ConfigManager


# ── 版本工具 ───────────────────────────────────────────────

def version_tuple(v: str) -> tuple:
    """将 "1.2.3" 或 "1.2.3-beta" 转为可比较的元组"""
    v = v.split("-")[0].split("+")[0]
    parts = v.split(".")
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(0)
    while len(result) < 3:
        result.append(0)
    return tuple(result)


def is_newer(remote: str, local: str) -> bool:
    """remote 版本是否比 local 更新"""
    return version_tuple(remote) > version_tuple(local)


def _find_exe(root: Path):
    """在解压目录中查找可执行文件，优先 Commemorate.exe"""
    for p in root.rglob("*.exe"):
        if p.name.lower() == "commemorate.exe":
            return p
    exes = list(root.rglob("*.exe"))
    return exes[0] if exes else None


# ── UpdateManager ──────────────────────────────────────────

class UpdateManager(QObject):
    """管理版本检查和下载"""

    check_completed = pyqtSignal(str, str, bool)  # latest_version, current_version, needs_update
    download_progress = pyqtSignal(int)            # percent 0-100
    download_finished = pyqtSignal(str)            # filepath
    error_occurred = pyqtSignal(str)               # message

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self._manager = QNetworkAccessManager(self)
        self._download_reply = None
        self._latest_data = {}

    def check_for_update(self):
        """向服务器查询最新版本"""
        url = self.config.update_check_url
        if not url:
            self.error_occurred.emit("未配置更新检查地址")
            return

        request = QNetworkRequest(QUrl(url))
        request.setTransferTimeout(8000)
        if "api.github.com" in url:
            # GitHub Contents API：请求原始文件内容，私有仓库需要 token
            request.setRawHeader(b"Accept", b"application/vnd.github.raw+json")
            token = self.config.sync_token()
            if token:
                request.setRawHeader(b"Authorization", f"token {token}".encode("utf-8"))
        reply = self._manager.get(request)

        def on_finished():
            if reply.error() != QNetworkReply.NoError:
                self.error_occurred.emit(f"检查更新失败: {reply.errorString()}")
                reply.deleteLater()
                return

            try:
                data = json.loads(reply.readAll().data().decode("utf-8"))
                latest = data.get("version") or data.get("latest_version") or "0.0.0"
                current = self.config.app_version

                # 检查是否跳过了此版本
                skip = self.config.update_skip_version
                needs = is_newer(latest, current)
                if skip and version_tuple(latest) <= version_tuple(skip):
                    needs = False

                self._latest_data = data
                self.check_completed.emit(latest, current, needs)
            except Exception as e:
                self.error_occurred.emit(f"解析版本信息失败: {e}")
            reply.deleteLater()

        reply.finished.connect(on_finished)

    def download_update(self, save_dir: str = None):
        """下载新版本更新包 app.zip"""
        download_url = self._latest_data.get("download_url", "")
        if not download_url:
            self.error_occurred.emit("未配置下载地址")
            return

        # 支持 {version} 占位符
        download_url = download_url.replace(
            "{version}", self._latest_data.get("version", "")
        )

        if save_dir is None:
            save_dir = Path(tempfile.gettempdir()) / "Commemorate_update"
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / "app.zip"
        self._save_path = str(save_path)
        self._zip_path = str(save_path)

        request = QNetworkRequest(QUrl(download_url))
        request.setAttribute(
            QNetworkRequest.RedirectPolicyAttribute,
            QNetworkRequest.NoLessSafeRedirectPolicy,
        )
        self._download_reply = self._manager.get(request)
        self._download_reply.downloadProgress.connect(self._on_progress)
        self._download_reply.finished.connect(self._on_download_finished)

    def _on_progress(self, received, total):
        if total > 0:
            percent = int(received / total * 100)
            self.download_progress.emit(percent)

    def _on_download_finished(self):
        reply = self._download_reply
        if reply.error() != QNetworkReply.NoError:
            self.error_occurred.emit(f"下载失败: {reply.errorString()}")
            reply.deleteLater()
            return
        data = reply.readAll()
        with open(self._save_path, "wb") as f:
            f.write(data)
        reply.deleteLater()

        # 校验 SHA-256（可选，version.json 未填则跳过）
        expected = (self._latest_data.get("sha256") or "").strip().lower()
        if expected:
            actual = hashlib.sha256(bytes(data)).hexdigest().lower()
            if actual != expected:
                self.error_occurred.emit("更新包校验失败：文件损坏或来源不可信")
                return

        self._extract_update()

    def _extract_update(self):
        """解压更新包并找到新的 exe"""
        version = self._latest_data.get("version", "new")
        extract_dir = Path(self._zip_path).parent / f"v{version}"
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        try:
            with zipfile.ZipFile(self._zip_path) as zf:
                zf.extractall(str(extract_dir))
        except (zipfile.BadZipFile, OSError) as e:
            self.error_occurred.emit(f"更新包解压失败: {e}")
            return

        exe_path = _find_exe(extract_dir)
        if not exe_path:
            self.error_occurred.emit("更新包中未找到可执行文件")
            return
        self.download_finished.emit(str(exe_path))

    def cancel_download(self):
        if self._download_reply and self._download_reply.isRunning():
            self._download_reply.abort()

    def schedule_update(self, new_exe_path: str):
        """生成 updater.bat 并启动"""
        if not getattr(sys, 'frozen', False):
            self.error_occurred.emit("开发模式不支持自动更新，请手动拉取代码")
            return

        target_exe = sys.executable
        source = Path(new_exe_path)
        tmp_dir = source.parent

        # 更新脚本放在本地数据目录 appdata/local/
        bat_dir = Path(target_exe).parent / "appdata" / "local"
        bat_path = bat_dir / "updater.bat"

        bat_content = f'''@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

set "TARGET={target_exe}"
set "SOURCE={new_exe_path}"
set "TMPDIR={tmp_dir}"
set "BAT_FILE=%0"

echo.
echo  ╔══════════════════════════════════╗
echo  ║     Commemorate  更新程序        ║
echo  ╚══════════════════════════════════╝
echo.

echo  等待主程序关闭...
set /a COUNT=0
:WAIT_LOOP
    tasklist /FI "IMAGENAME eq Commemorate.exe" 2>NUL | find /I "Commemorate.exe" >NUL
    if errorlevel 1 goto REPLACE
    timeout /t 1 /nobreak >NUL
    set /a COUNT+=1
    if !COUNT! geq 15 goto FORCE
    goto WAIT_LOOP

:FORCE
echo  强制关闭残留进程...
taskkill /F /IM Commemorate.exe 2>NUL
timeout /t 2 /nobreak >NUL

:REPLACE
echo  正在更新文件...
move /Y "%SOURCE%" "%TARGET%" >NUL 2>&1
if errorlevel 1 (
    echo  更新失败！请手动替换文件。
    pause
    exit /b 1
)

echo  更新完成！正在启动...
start "" "%TARGET%"

timeout /t 3 /nobreak >NUL
rmdir /s /q "%TMPDIR%" 2>NUL
del "%BAT_FILE%" 2>NUL
(goto) 2>nul & del "%~f0"
endlocal
'''

        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)

        os.startfile(str(bat_path))


# ── 更新提示对话框 ─────────────────────────────────────────

class UpdateDialog(QDialog):
    """更新可用提示 — 浪漫主题"""

    def __init__(self, latest: str, current: str, changelog: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("更新可用")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(400, 340)
        self._result = "skip"

        self._setup_ui(latest, current, changelog)
        self._center()

    def _center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )

    def _setup_ui(self, latest, current, changelog):
        title = QLabel("✦  发现新版本  ✦", self)
        title.setAlignment(Qt.AlignCenter)
        title.setGeometry(0, 30, 400, 40)
        title.setStyleSheet("""
            QLabel {
                color: #fff0f5; font-family: "Microsoft YaHei";
                font-size: 22px; font-weight: bold; background: transparent;
            }
        """)

        info = QLabel(
            f"<span style='color:#c8b4d2'>当前版本: v{current}</span><br>"
            f"<span style='color:#ffb4cc'>最新版本: v{latest}</span>", self
        )
        info.setAlignment(Qt.AlignCenter)
        info.setGeometry(0, 80, 400, 50)
        info.setStyleSheet("QLabel { font-family: 'Microsoft YaHei'; font-size: 14px; background: transparent; }")

        cl_label = QLabel(self)
        cl_label.setAlignment(Qt.AlignTop)
        cl_label.setGeometry(50, 145, 300, 80)
        cl_text = changelog.replace("\n", "<br>") if changelog else "暂无更新说明"
        cl_label.setText(f"<span style='color:#c8b4d2;font-size:12px;'>{cl_text}</span>")
        cl_label.setWordWrap(True)
        cl_label.setStyleSheet("background: transparent; font-family: 'Microsoft YaHei';")

        update_btn = QPushButton("立即更新", self)
        update_btn.setGeometry(60, 260, 130, 38)
        update_btn.setStyleSheet("""
            QPushButton {
                color: white; font-family: "Microsoft YaHei"; font-size: 14px; font-weight: bold;
                border: none; border-radius: 19px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #dc5082, stop:1 #a02850);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f06496, stop:1 #b4325a);
            }
        """)
        update_btn.clicked.connect(self._on_install)

        skip_btn = QPushButton("跳过此版本", self)
        skip_btn.setGeometry(210, 260, 130, 38)
        skip_btn.setStyleSheet("""
            QPushButton {
                color: #c8b4d2; font-family: "Microsoft YaHei"; font-size: 13px;
                border: 1.5px solid #78508c; border-radius: 19px;
                background: rgba(30, 15, 50, 150);
            }
            QPushButton:hover {
                background: rgba(50, 25, 70, 180); border-color: #a060b0;
            }
        """)
        skip_btn.clicked.connect(self._on_skip)

    def _on_install(self):
        self._result = "install"
        self.accept()

    def _on_skip(self):
        self._result = "skip"
        self.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(5, 2, 20))
        bg.setColorAt(0.5, QColor(18, 8, 40))
        bg.setColorAt(1.0, QColor(30, 10, 50))
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(2, 2, w - 4, h - 4, 20, 20)
        painter.setPen(QPen(QColor(180, 140, 200, 60), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(3, 3, w - 6, h - 6, 19, 19)
        painter.end()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_skip()


# ── 编排函数 ───────────────────────────────────────────────

def show_update_dialog(update_mgr: UpdateManager, config: ConfigManager) -> str:
    """
    检查更新并显示对话框。
    返回 "install"（安排了更新，应退出）或 "skip"（继续）
    """
    action = ["skip"]  # 用列表做可变容器

    def on_check(latest, current, needs):
        if not needs:
            action[0] = "skip"
            loop.quit()
            return

        if config.is_dev_mode():
            QMessageBox.information(
                None,
                "发现新版本",
                f"最新版本: v{latest}\n\n当前为开发模式，无法自动更新。\n"
                "请手动执行 git pull 拉取最新代码。",
            )
            action[0] = "skip"
            loop.quit()
            return

        dlg = UpdateDialog(latest, current, update_mgr._latest_data.get("changelog", ""))
        dlg.exec_()

        if dlg._result == "install":
            _run_download(update_mgr, action)
        # 如果是 skip，设置并退出
        if action[0] == "skip":
            config.update_skip_version = latest
            config.save()
        loop.quit()

    def on_error(msg):
        action[0] = "skip"
        loop.quit()

    update_mgr.check_completed.connect(on_check)
    update_mgr.error_occurred.connect(on_error)
    update_mgr.check_for_update()

    loop = QEventLoop()
    loop.exec_()

    return action[0]


def _run_download(update_mgr: UpdateManager, action: list):
    """执行下载流程，结果写入 action[0]"""
    progress = QProgressDialog("正在下载更新包...", "取消", 0, 100)
    progress.setWindowTitle("Commemorate 更新")
    progress.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)

    progress.setStyleSheet("""
        QProgressDialog {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #050214, stop:0.5 #120828, stop:1 #1e0a32);
            border: 1.5px solid #b48cc8; border-radius: 12px;
            color: #fff0f5; font-family: "Microsoft YaHei"; font-size: 13px;
        }
        QProgressBar {
            border: 1px solid #78508c; border-radius: 8px;
            background: rgba(30, 15, 50, 200); text-align: center;
            color: #fff0f5; font-size: 11px;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #dc5082, stop:1 #ff8cb4);
            border-radius: 7px;
        }
        QPushButton {
            color: #c8b4d2; font-family: "Microsoft YaHei"; font-size: 12px;
            border: 1px solid #78508c; border-radius: 10px; padding: 4px 16px;
            background: rgba(30, 15, 50, 150);
        }
        QPushButton:hover { background: rgba(50, 25, 70, 180); }
    """)

    progress.canceled.connect(update_mgr.cancel_download)

    dl_loop = QEventLoop()

    def on_progress(pct):
        progress.setValue(pct)

    def on_finished(filepath):
        progress.close()
        update_mgr.schedule_update(filepath)
        action[0] = "install"
        dl_loop.quit()

    def on_error(msg):
        progress.close()
        action[0] = "skip"
        dl_loop.quit()

    update_mgr.download_progress.connect(on_progress)
    update_mgr.download_finished.connect(on_finished)
    update_mgr.error_occurred.connect(on_error)

    update_mgr.download_update()
    dl_loop.exec_()


def preflight_update(update_mgr: UpdateManager, config: ConfigManager) -> dict:
    """登录前静默检查版本，返回 {'needs': bool, 'latest': str, 'current': str}"""
    result = {}
    loop = QEventLoop()

    def on_check(latest, current, needs):
        result.update(latest=latest, current=current, needs=needs)
        loop.quit()

    def on_error(msg):
        result["error"] = msg
        loop.quit()

    update_mgr.check_completed.connect(on_check)
    update_mgr.error_occurred.connect(on_error)
    update_mgr.check_for_update()
    loop.exec_()

    update_mgr.check_completed.disconnect(on_check)
    update_mgr.error_occurred.disconnect(on_error)
    return result
