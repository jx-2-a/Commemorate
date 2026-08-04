"""
浪漫纪念动画窗口 — Romantic Commemorative Window
一个全屏无边框窗口，用流动的星光、漂浮的爱心和柔光粒子
来纪念生命中某个珍贵的时刻。

启动流程: 登录 → 版本检查 → 主窗口
"""
import os
import sys
import math
import random
import traceback
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, QEventLoop
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QRadialGradient, QLinearGradient,
    QPen, QBrush, QPainterPath, QFontMetrics
)
from PyQt5.QtWidgets import QApplication, QWidget

from app_config import ConfigManager


# ============================================================
#  崩溃日志工具
# ============================================================

def _log_dir() -> Path:
    """可执行文件 / 脚本所在目录（日志放在这里）"""
    if getattr(sys, 'frozen', False):
        d = Path(sys.executable).parent / "appdata" / "local"
    else:
        d = Path(__file__).resolve().parent / "local"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_crash_log(etype, value, tb):
    """把完整异常堆栈追加写入 commemorate.log"""
    try:
        path = _log_dir() / "commemorate.log"
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
            traceback.print_exception(etype, value, tb, file=f)
    except Exception:
        pass


def _install_excepthook():
    """未捕获异常同时写入日志并打印到控制台"""
    def hook(etype, value, tb):
        _write_crash_log(etype, value, tb)
        traceback.print_exception(etype, value, tb)
    sys.excepthook = hook


# ============================================================
#  粒子类
# ============================================================

class Star:
    """闪烁的星星"""

    def __init__(self, w, h):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h * 0.7)
        self.size = random.uniform(0.5, 2.5)
        self.brightness = random.uniform(0.3, 1.0)
        self.twinkle_speed = random.uniform(0.02, 0.06)
        self.twinkle_offset = random.uniform(0, math.pi * 2)

    def update(self, frame):
        self.brightness = 0.3 + 0.7 * abs(math.sin(frame * self.twinkle_speed + self.twinkle_offset))


class Heart:
    """漂浮上升的爱心粒子"""

    def __init__(self, w, h):
        self.x = random.uniform(0, w)
        self.y = random.uniform(h, h + 200)
        self.size = random.uniform(6, 22)
        self.speed = random.uniform(0.4, 1.6)
        self.wobble_amp = random.uniform(0.3, 1.2)
        self.wobble_speed = random.uniform(0.01, 0.04)
        self.wobble_offset = random.uniform(0, math.pi * 2)
        self.opacity = random.uniform(0.15, 0.55)
        hue = random.uniform(340, 360) if random.random() < 0.5 else random.uniform(0, 15)
        self.color = QColor()
        self.color.setHsv(int(hue % 360), random.randint(120, 200), random.randint(220, 255))

    def update(self, frame, w, h):
        self.y -= self.speed
        self.x += math.sin(frame * self.wobble_speed + self.wobble_offset) * self.wobble_amp
        if self.y < -60:
            self.y = random.uniform(h, h + 200)
            self.x = random.uniform(0, w)
        self.opacity = 0.15 + 0.4 * abs(math.sin(frame * 0.015 + self.wobble_offset))


class Firefly:
    """萤火虫光点——在画面中轻盈游走"""

    def __init__(self, w, h):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.target_x = self.x
        self.target_y = self.y
        self.size = random.uniform(15, 40)
        self.opacity = 0.0
        self.phase_offset = random.uniform(0, math.pi * 2)
        self.move_timer = random.randint(0, 120)

    def update(self, frame, w, h):
        self.move_timer -= 1
        if self.move_timer <= 0:
            self.target_x = random.uniform(50, w - 50)
            self.target_y = random.uniform(50, h - 150)
            self.move_timer = random.randint(60, 200)
        self.x += (self.target_x - self.x) * 0.02
        self.y += (self.target_y - self.y) * 0.02
        self.opacity = 0.15 + 0.55 * abs(math.sin(frame * 0.03 + self.phase_offset))


# ============================================================
#  CommemorateWindow — 纪念动画主窗口（从 config 读取信息）
# ============================================================

class CommemorateWindow(QWidget):
    """纪念动画主窗口"""

    def __init__(self, config: ConfigManager):
        super().__init__()
        self.config = config

        # 从配置读取纪念信息
        self._comm_date = config.commemorative_date
        self._comm_time = config.commemorative_time
        self._comm_title = config.commemorative_title
        self._comm_subtitle = config.commemorative_subtitle

        self.setWindowTitle(f"💖 {config.app_name}")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # 获取屏幕尺寸，窗口覆盖 70% 中心区域
        screen = QApplication.primaryScreen().availableGeometry()
        self.win_w = int(screen.width() * 0.7)
        self.win_h = int(screen.height() * 0.7)
        self.resize(self.win_w, self.win_h)
        self.move((screen.width() - self.win_w) // 2, (screen.height() - self.win_h) // 2)

        # 粒子
        self.stars = [Star(self.win_w, self.win_h) for _ in range(120)]
        self.hearts = [Heart(self.win_w, self.win_h) for _ in range(45)]
        self.fireflies = [Firefly(self.win_w, self.win_h) for _ in range(18)]

        # 帧 & 动画状态
        self.frame = 0
        self.fade_in = 0.0
        self.time_displayed = False

        # 计算距离天数
        try:
            past = datetime.strptime(f"{self._comm_date} {self._comm_time}", "%Y-%m-%d %H:%M")
            now = datetime.now()
            self.days_passed = (now - past).days
        except ValueError:
            self.days_passed = 0

        # 主循环
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)  # ~60 FPS

        # 3 秒后显示时间
        QTimer.singleShot(2500, self._show_time)

    def _show_time(self):
        self.time_displayed = True

    def refresh_from_config(self):
        """数据同步后刷新纪念信息（远程配置可能已更新）"""
        self._comm_date = self.config.commemorative_date
        self._comm_time = self.config.commemorative_time
        self._comm_title = self.config.commemorative_title
        self._comm_subtitle = self.config.commemorative_subtitle
        try:
            past = datetime.strptime(f"{self._comm_date} {self._comm_time}", "%Y-%m-%d %H:%M")
            self.days_passed = (datetime.now() - past).days
        except ValueError:
            self.days_passed = 0
        self.update()

    def _tick(self):
        try:
            self.frame += 1
            if self.fade_in < 1.0:
                self.fade_in = min(1.0, self.fade_in + 0.008)
            for s in self.stars:
                s.update(self.frame)
            for h in self.hearts:
                h.update(self.frame, self.win_w, self.win_h)
            for f in self.fireflies:
                f.update(self.frame, self.win_w, self.win_h)
            self.update()
        except Exception:
            # 动画循环不允许崩溃：记录一次完整堆栈后继续
            if not getattr(self, "_tick_error_logged", False):
                self._tick_error_logged = True
                _write_crash_log(*sys.exc_info())
                traceback.print_exc()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        w, h = self.win_w, self.win_h

        # ── 1. 夜空背景 ──────────────────────────────────
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(5, 2, 20))
        bg.setColorAt(0.4, QColor(18, 8, 40))
        bg.setColorAt(0.75, QColor(25, 10, 45))
        bg.setColorAt(1.0, QColor(40, 15, 55))
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(0, 0, w, h), 20, 20)

        # ── 2. 星星 ──────────────────────────────────────
        for s in self.stars:
            color = QColor(255, 255, 220, int(200 * s.brightness * self.fade_in))
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            r = s.size
            painter.drawEllipse(QPointF(s.x, s.y), r, r)

        # ── 3. 萤火虫光晕 ────────────────────────────────
        for f in self.fireflies:
            alpha = int(255 * f.opacity * self.fade_in)
            if alpha < 5:
                continue
            gradient = QRadialGradient(QPointF(f.x, f.y), f.size)
            c = QColor(255, 220, 140, alpha)
            c0 = QColor(255, 220, 140, 0)
            gradient.setColorAt(0.0, c)
            gradient.setColorAt(0.4, QColor(255, 180, 100, alpha // 2))
            gradient.setColorAt(1.0, c0)
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(f.x, f.y), f.size, f.size)

        # ── 4. 漂浮的爱心 ────────────────────────────────
        for hh in self.hearts:
            color = QColor(hh.color)
            color.setAlpha(int(255 * hh.opacity * self.fade_in))
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            self._draw_heart(painter, hh.x, hh.y, hh.size)

        # ── 5. 中央发光文字 ──────────────────────────────
        title_alpha = int(255 * self.fade_in)
        if title_alpha > 5:
            cx, cy = w / 2, h / 2 - 40
            for layer in range(6):
                glow_alpha = title_alpha // (layer + 1)
                glow_size = 40 + layer * 8
                glow = QRadialGradient(cx, cy, glow_size)
                gc = QColor(255, 200, 220, glow_alpha)
                gc0 = QColor(255, 200, 220, 0)
                glow.setColorAt(0.0, gc)
                glow.setColorAt(0.5, QColor(255, 160, 190, glow_alpha // 3))
                glow.setColorAt(1.0, gc0)
                painter.setBrush(QBrush(glow))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(cx, cy), glow_size, glow_size * 0.7)

            # 主标题
            title_font = QFont("Microsoft YaHei", 42, QFont.Bold)
            painter.setFont(title_font)
            painter.setPen(QColor(255, 240, 245, title_alpha))
            fm = QFontMetrics(title_font)
            tw = fm.horizontalAdvance(self._comm_title)
            painter.drawText(int(cx - tw / 2), int(cy - 30), self._comm_title)

            # 副标题
            sub_font = QFont("Microsoft YaHei", 16)
            sub_font.setItalic(True)
            painter.setFont(sub_font)
            painter.setPen(QColor(255, 210, 230, int(title_alpha * 0.85)))
            fm2 = QFontMetrics(sub_font)
            sw = fm2.horizontalAdvance(self._comm_subtitle)
            painter.drawText(int(cx - sw / 2), int(cy + 10), self._comm_subtitle)

        # ── 6. 底部日期 & 计时 ────────────────────────────
        if self.time_displayed:
            bottom_alpha = min(1.0, (self.frame - 150) / 80.0)
            if bottom_alpha > 0.05:
                alpha = int(255 * bottom_alpha)
                bottom_font = QFont("Microsoft YaHei", 13)
                painter.setFont(bottom_font)
                painter.setPen(QColor(220, 200, 230, alpha))

                date_str = f"{self._comm_date}  {self._comm_time}"
                days_str = f"从那天起，已是第 {self.days_passed} 天"
                fm3 = QFontMetrics(bottom_font)
                dw = fm3.horizontalAdvance(date_str)
                dw2 = fm3.horizontalAdvance(days_str)
                painter.drawText(int(cx - dw / 2), h - 90, date_str)
                painter.drawText(int(cx - dw2 / 2), h - 65, days_str)

                # 装饰线
                painter.setPen(QPen(QColor(180, 140, 200, alpha), 1))
                line_y = h - 78
                painter.drawLine(int(cx - 120), line_y, int(cx + 120), line_y)

        # ── 7. 边框微光 ──────────────────────────────────
        border_color = QColor(180, 140, 200, int(40 * self.fade_in))
        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 19, 19)

        painter.end()

    def _draw_heart(self, painter, x, y, size):
        """用贝塞尔曲线画爱心"""
        path = QPainterPath()
        s = size * 0.45
        path.moveTo(x, y + s * 0.4)
        path.cubicTo(x, y - s * 0.1, x - s * 0.9, y - s * 0.1, x - s * 0.9, y + s * 0.35)
        path.cubicTo(x - s * 0.9, y + s * 1.0, x, y + s * 1.6, x, y + s * 1.9)
        path.cubicTo(x, y + s * 1.6, x + s * 0.9, y + s * 1.0, x + s * 0.9, y + s * 0.35)
        path.cubicTo(x + s * 0.9, y - s * 0.1, x, y - s * 0.1, x, y + s * 0.4)
        painter.drawPath(path)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Q):
            self._shutdown()
        elif event.key() == Qt.Key_F:
            if self.windowState() & Qt.WindowFullScreen:
                self.showNormal()
            else:
                self.showFullScreen()

    def mouseDoubleClickEvent(self, event):
        self._shutdown()

    def closeEvent(self, event):
        # 关闭前停止动画定时器，避免窗口销毁后 _tick 继续访问已删除对象
        self.timer.stop()
        super().closeEvent(event)

    def _shutdown(self):
        self.timer.stop()
        self.close()
        # 主窗口带 Qt.Tool 标志，Qt 不会因“最后一个窗口关闭”自动退出，
        # 这里显式退出事件循环
        app = QApplication.instance()
        if app is not None:
            app.quit()


# ============================================================
#  入口 — 由 login_window 和 update_manager 协同编排
# ============================================================

if __name__ == "__main__":
    # 静音 Qt 网络监控的无害警告（Windows 虚拟网卡 / VPN 环境常见）
    os.environ.setdefault("QT_LOGGING_RULES", "qt.network.monitor=false")

    _install_excepthook()

    app = QApplication(sys.argv)
    app.setApplicationName("Commemorate")

    config = ConfigManager("config.json")
    args = sys.argv[1:]

    # ---- 设置本地令牌（--set-token <token>），不依赖环境变量 ----
    if "--set-token" in args:
        idx = args.index("--set-token")
        token = args[idx + 1] if idx + 1 < len(args) else ""
        if token:
            config.set_local_token(token)
            print("本地令牌已保存到 local_state.json")
        else:
            print("用法: python main.py --set-token <token>")
        sys.exit(0)

    # ---- 推送本地数据到私有仓库（--sync-push，可跟文件名） ----
    if "--sync-push" in args:
        from PyQt5.QtWidgets import QMessageBox
        from data_sync import DataSyncManager, run_sync

        idx = args.index("--sync-push")
        files = [a for a in args[idx + 1:] if not a.startswith("-")] or None
        sync_mgr = DataSyncManager(config)
        done, errors = run_sync(sync_mgr, "push", files=files, show_progress=True)

        msg = f"已推送 {done} 个文件到 {config.sync_repo_owner}/{config.sync_repo_name}"
        if errors:
            msg += "\n\n以下文件失败：\n" + "\n".join(errors[:5])
        QMessageBox.information(None, "数据同步", msg)
        sys.exit(0)

    # ---- 先出窗口：后台预创建主窗口（不显示），立即显示登录窗口 ----
    from login_window import LoginWindow
    from data_sync import SyncWorker

    window = CommemorateWindow(config)
    sync_result = {"success": False, "sync_errors": [], "preflight": None}

    login = LoginWindow(config)
    login.update_sync_state("syncing")
    sync_running = {"value": False}
    sync_background = {"thread": None, "worker": None}

    def finalize_sync(result):
        """同步线程结束：成功则重载配置并解锁登录，失败则阻止登录"""
        sync_running["value"] = False
        sync_result.update(result)
        if not result.get("success"):
            detail = result.get("sync_errors", [""])[0] if result.get("sync_errors") else None
            login.update_sync_state("failed", detail)
            return
        config.reload()
        login.update_sync_state("ready")

    def start_sync_thread():
        """启动后台同步线程（不阻塞 UI）：用户信息 + 其他数据 + 静默版本检查"""
        if sync_running["value"]:
            return
        sync_running["value"] = True
        login.update_sync_state("syncing")
        from PyQt5.QtCore import QThread
        t = QThread()
        w = SyncWorker()
        w.moveToThread(t)
        t.started.connect(w.run)
        w.finished.connect(finalize_sync)
        w.finished.connect(t.quit)
        t.finished.connect(w.deleteLater)
        sync_background["thread"] = t
        sync_background["worker"] = w
        t.start()

    def stop_sync_thread():
        """退出前优雅停止后台同步线程，避免 QThread 销毁时线程仍在运行"""
        t = sync_background.get("thread")
        if t is not None:
            t.quit()
            t.wait(10000)
        sync_background.update(thread=None, worker=None)

    # 刷新按钮：同步失败后可一键重试
    login.retry_sync.connect(start_sync_thread)

    # ---- 登录成功：若发现新版本，登录窗口内完成更新流程（不进入主窗口）----
    def on_login_ok(username, password):
        preflight = sync_result.get("preflight") or {}
        if not preflight.get("needs"):
            login.accept()
            return

        from update_manager import UpdateManager
        latest_data = preflight.get("latest_data", {})
        update_mgr = UpdateManager(config)
        update_mgr._latest_data = latest_data

        login.show_update_panel(
            preflight.get("latest", ""),
            preflight.get("current", ""),
            latest_data.get("changelog", ""),
        )

        # 等待用户操作：start（立即更新）/ cancel（取消下载后重试）
        #              / skip（本次跳过，进入主窗口）/ close（关闭退出）
        while True:
            action = ["close"]
            wait_loop = QEventLoop()

            def on_update_action(act):
                action[0] = act
                wait_loop.quit()

            login.update_action.connect(on_update_action)
            wait_loop.exec_()
            login.update_action.disconnect(on_update_action)

            if action[0] == "skip":
                # 本次跳过：进入主窗口，下次登录仍会提示
                login.accept()
                return

            if action[0] != "start":
                login.reject()
                stop_sync_thread()
                window._shutdown()
                sys.exit(0)

            # 用户点击“立即更新”：在登录窗口内下载并显示进度
            done = {"ok": False}
            dl_loop = QEventLoop()

            def on_download_progress(pct):
                login.set_update_state("downloading", {"percent": pct})

            def on_download_finished(filepath):
                login.set_update_state("downloading", {"percent": 100})
                if config.is_dev_mode():
                    login.set_update_state("error", {"message": "开发模式不支持自动更新，请用 git pull 拉取最新代码"})
                else:
                    login.set_update_state("installing")
                    update_mgr.schedule_update(filepath)
                    done["ok"] = True
                dl_loop.quit()

            def on_download_error(msg):
                login.set_update_state("error", {"message": msg})
                dl_loop.quit()

            def on_download_cancel():
                update_mgr.cancel_download()
                login.set_update_state("error", {"message": "已取消下载"})

            login.cancel_update_btn.clicked.connect(on_download_cancel)
            update_mgr.download_progress.connect(on_download_progress)
            update_mgr.download_finished.connect(on_download_finished)
            update_mgr.error_occurred.connect(on_download_error)

            login.set_update_state("start")
            update_mgr.download_update()
            dl_loop.exec_()

            update_mgr.download_progress.disconnect(on_download_progress)
            update_mgr.download_finished.disconnect(on_download_finished)
            update_mgr.error_occurred.disconnect(on_download_error)
            login.cancel_update_btn.clicked.disconnect(on_download_cancel)

            if done["ok"]:
                # 更新已安排：把本地版本号同步为新版本，重启后不再重复提示
                config.app_version = preflight["latest"]
                config.save()
                login.accept()
                stop_sync_thread()
                window._shutdown()
                sys.exit(0)
            # 失败/取消：面板显示错误，用户可点击“重试更新”或关闭退出

    login.login_ok.connect(on_login_ok)

    # ---- 后台线程同步（不阻塞 UI） ----
    if config.sync_auto_pull and "--skip-sync" not in args:
        start_sync_thread()
    else:
        # 跳过同步：使用本地缓存，直接视为同步成功
        finalize_sync({"success": True, "sync_errors": [], "preflight": None})

    # ---- 登录（必须等待同步成功；同步期间按钮禁用） ----
    if login.exec_() != LoginWindow.Accepted:
        stop_sync_thread()
        window._shutdown()
        sys.exit(0)

    # ---- 主窗口正式显示 ----
    window.refresh_from_config()
    window.show()
    window.raise_()
    sys.exit(app.exec_())
