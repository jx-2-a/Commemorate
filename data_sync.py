"""
data_sync — 通过 GitHub 仓库同步数据文件

拉取: raw.githubusercontent.com（公开仓库）或 api.github.com（私有仓库，需 token）
推送: GitHub Contents API，仅推送 push_files 中允许的文件
"""
import base64
import hashlib
import json
import os
from pathlib import Path

from PyQt5.QtCore import QObject, QTimer, QUrl, pyqtSignal, QEventLoop, Qt
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt5.QtWidgets import QProgressDialog

from app_config import ConfigManager


RAW_BASE = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
API_BASE = "https://api.github.com/repos/{owner}/{repo}/contents/{path}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def file_url(config: ConfigManager, path: str) -> str:
    """根据配置生成文件在仓库中的地址"""
    if config.sync_use_api:
        return API_BASE.format(
            owner=config.sync_repo_owner, repo=config.sync_repo_name, path=path
        )
    return RAW_BASE.format(
        owner=config.sync_repo_owner,
        repo=config.sync_repo_name,
        branch=config.sync_branch,
        path=path,
    )


class DataSyncManager(QObject):
    """拉取 / 推送私有仓库中的同步文件"""

    file_synced = pyqtSignal(str, bool)   # 文件名, 内容是否变化
    sync_done = pyqtSignal(int, int)      # 完成数量, 总数
    error_occurred = pyqtSignal(str)      # 单文件错误（不中断整体）

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self._manager = QNetworkAccessManager(self)
        self._mode = "pull"
        self._queue = []
        self._done = 0
        self._total = 0
        self._errors = []

    # ---------- 公开入口 ----------

    def pull(self, files=None):
        self._start("pull", files or self.config.sync_files)

    def push(self, files=None):
        self._start("push", files or self.config.sync_push_files)

    def _start(self, mode, files):
        self._mode = mode
        self._queue = list(files)
        self._total = len(self._queue)
        self._done = 0
        self._errors = []
        # 用 0 延时保证信号在事件循环启动后再发出
        QTimer.singleShot(0, self._next)

    # ---------- 请求构造 ----------

    def _request(self, url: str, token: str = "", accept_raw: bool = True) -> QNetworkRequest:
        req = QNetworkRequest(QUrl(url))
        if "api.github.com" in url:
            if accept_raw:
                # 拉取：直接拿原始文件内容
                req.setRawHeader(b"Accept", b"application/vnd.github.raw+json")
            else:
                # 推送：需要标准 JSON 响应以读取 sha
                req.setRawHeader(b"Accept", b"application/vnd.github+json")
        if token:
            req.setRawHeader(b"Authorization", f"token {token}".encode("utf-8"))
        req.setRawHeader(b"User-Agent", b"Commemorate")
        return req

    def _token(self):
        return os.environ.get(self.config.sync_push_token_env or "GITHUB_TOKEN", "")

    # ---------- 队列调度 ----------

    def _next(self):
        if not self._queue:
            self.sync_done.emit(self._done, self._total)
            return
        path = self._queue.pop(0)
        if self._mode == "pull":
            self._pull_file(path)
        else:
            self._push_file(path)

    # ---------- 拉取 ----------

    def _pull_file(self, path):
        url = file_url(self.config, path)
        req = self._request(url, token=self._token())
        reply = self._manager.get(req)
        reply.finished.connect(lambda r=reply, p=path: self._on_pulled(r, p))

    def _on_pulled(self, reply, path):
        try:
            if reply.error() != QNetworkReply.NoError:
                self._errors.append(f"拉取 {path}: {reply.errorString()}")
            else:
                data = bytes(reply.readAll())
                dest = self.config.data_dir / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                changed = not dest.exists() or sha256_file(dest) != sha256_bytes(data)
                if changed:
                    dest.write_bytes(data)
                    self._done += 1
                self.file_synced.emit(path, changed)
        except Exception as e:
            self._errors.append(f"拉取 {path}: {e}")
        finally:
            reply.deleteLater()
            self._next()

    # ---------- 推送 ----------

    def _push_file(self, path):
        token = self._token()
        if not token:
            self._errors.append(
                f"推送 {path}: 未设置环境变量 {self.config.sync_push_token_env}"
            )
            self._next()
            return
        src = self.config.data_dir / path
        if not src.exists():
            self._errors.append(f"推送 {path}: 本地文件不存在")
            self._next()
            return
        url = file_url(self.config, path)
        req = self._request(url, token=token, accept_raw=False)
        reply = self._manager.get(req)
        reply.finished.connect(
            lambda r=reply, p=path, u=url, t=token: self._on_sha(r, p, u, t)
        )

    def _on_sha(self, reply, path, url, token):
        sha = None
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        try:
            if reply.error() != QNetworkReply.NoError:
                if status != 404:
                    self._errors.append(
                        f"推送 {path}: 读取远程状态失败 {reply.errorString()}"
                    )
                    reply.deleteLater()
                    self._next()
                    return
                # 404 = 仓库中还没有该文件，首次推送不携带 sha
            else:
                info = json.loads(reply.readAll().data().decode("utf-8"))
                sha = info.get("sha")
        except Exception as e:
            self._errors.append(f"推送 {path}: {e}")
            reply.deleteLater()
            self._next()
            return
        reply.deleteLater()

        try:
            content = base64.b64encode(
                (self.config.data_dir / path).read_bytes()
            ).decode("ascii")
        except OSError as e:
            self._errors.append(f"推送 {path}: {e}")
            self._next()
            return

        body = {
            "message": f"sync: update {path}",
            "content": content,
            "branch": self.config.sync_branch,
        }
        if sha:
            body["sha"] = sha

        req = self._request(url, token=token, accept_raw=False)
        req.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        put_reply = self._manager.put(req, json.dumps(body).encode("utf-8"))
        put_reply.finished.connect(
            lambda r=put_reply, p=path: self._on_pushed(r, p)
        )

    def _on_pushed(self, reply, path):
        try:
            if reply.error() != QNetworkReply.NoError:
                self._errors.append(f"推送 {path}: {reply.errorString()}")
            else:
                self._done += 1
                self.file_synced.emit(path, True)
        except Exception as e:
            self._errors.append(f"推送 {path}: {e}")
        finally:
            reply.deleteLater()
            self._next()

    # ---------- 结果 ----------

    @property
    def errors(self):
        return list(self._errors)


def run_sync(sync_mgr: DataSyncManager, mode="pull", files=None, show_progress=True):
    """阻塞执行一次同步，返回 (完成数量, 错误列表)"""
    result = {"done": 0, "errors": []}
    loop = QEventLoop()
    progress = None

    if show_progress:
        progress = QProgressDialog("正在同步数据…", "", 0, 0, None)
        progress.setWindowTitle("Commemorate 数据同步")
        progress.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        progress.setCancelButton(None)
        progress.setMinimumDuration(600)
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
        """)

    def on_done(done, total):
        result["done"] = done
        if progress is not None:
            progress.close()
        loop.quit()

    sync_mgr.sync_done.connect(on_done)
    if mode == "push":
        sync_mgr.push(files)
    else:
        sync_mgr.pull(files)
    loop.exec_()
    result["errors"] = sync_mgr.errors
    return result["done"], result["errors"]
