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

from PyQt5.QtCore import QObject, QTimer, QUrl, pyqtSignal, pyqtSlot, QEventLoop, Qt
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt5.QtWidgets import QProgressDialog

from app_config import ConfigManager


RAW_BASE = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
API_BASE = "https://api.github.com/repos/{owner}/{repo}/contents/{path}"
GIT_TREE_URL = "https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_blob_sha(data: bytes) -> str:
    """计算 Git blob 的 SHA-1（与 GitHub API 返回的文件 sha 一致）"""
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\x00" + data).hexdigest()


def parse_tree_shas(tree_json: dict) -> dict:
    """把 git trees API 的响应解析为 {path: blob_sha}"""
    result = {}
    for item in tree_json.get("tree", []):
        if item.get("type") == "blob":
            result[item.get("path")] = item.get("sha")
    return result


def filter_changed(data_dir: Path, files, remote_shas: dict):
    """对比本地与远程哈希，返回 (需要下载的文件, 远程缺失的文件)"""
    changed = []
    missing = []
    for path in files:
        remote_sha = remote_shas.get(path)
        if remote_sha is None:
            missing.append(path)
            continue
        local = data_dir / path
        if not local.exists() or git_blob_sha(local.read_bytes()) != remote_sha:
            changed.append(path)
    return changed, missing


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
        QTimer.singleShot(0, self._begin)

    def _begin(self):
        if self._mode == "pull":
            self._pull_stage1()
        else:
            self._next()

    # ---------- 请求构造 ----------

    def _request(self, url: str, token: str = "", accept_raw: bool = True) -> QNetworkRequest:
        req = QNetworkRequest(QUrl(url))
        req.setTransferTimeout(10000)
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

    def _pull_stage1(self):
        """先用一次请求获取远程文件哈希清单，只下载有变化的文件"""
        url = GIT_TREE_URL.format(
            owner=self.config.sync_repo_owner,
            repo=self.config.sync_repo_name,
            branch=self.config.sync_branch,
        )
        req = self._request(url, token=self._token(), accept_raw=False)
        reply = self._manager.get(req)
        reply.finished.connect(lambda r=reply: self._on_tree(r))

    def _on_tree(self, reply):
        try:
            if reply.error() != QNetworkReply.NoError:
                self._errors.append(f"获取远程哈希清单失败: {reply.errorString()}")
            else:
                remote_shas = parse_tree_shas(
                    json.loads(reply.readAll().data().decode("utf-8"))
                )
                changed, missing = filter_changed(
                    self.config.data_dir, self._queue, remote_shas
                )
                for path in missing:
                    self._errors.append(f"远程不存在: {path}")
                self._queue = changed
                self._total = len(changed)
                self._done = 0
        except Exception as e:
            self._errors.append(f"获取远程哈希清单失败: {e}")
        finally:
            reply.deleteLater()
            # 无论是否拿到清单，都进入逐文件阶段（失败时回退为全量下载）
            self._next()

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
                # 本地与远程哈希一致时跳过上传
                local = self.config.data_dir / path
                if sha and local.exists() and git_blob_sha(local.read_bytes()) == sha:
                    self.file_synced.emit(path, False)
                    reply.deleteLater()
                    self._next()
                    return
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


class SyncWorker(QObject):
    """后台线程执行的登录前同步 + 静默版本检查"""

    finished = pyqtSignal(dict)

    def __init__(self, config_filename="config.json", parent=None):
        super().__init__(parent)
        self._config_filename = config_filename

    @pyqtSlot()
    def run(self):
        from app_config import ConfigManager
        from update_manager import UpdateManager, preflight_update

        # 在子线程内创建实例，确保网络对象绑定到本线程的事件循环
        cfg = ConfigManager(self._config_filename)
        mgr = DataSyncManager(cfg)
        loop = QEventLoop()
        mgr.sync_done.connect(loop.quit)
        mgr.pull()
        loop.exec_()

        result = {
            "success": not mgr.errors,
            "sync_errors": mgr.errors,
            "sync_done": mgr._done,
            "preflight": None,
            "preflight_error": None,
        }
        if result["success"]:
            cfg.reload()
            if cfg.update_auto_check and cfg.update_check_url:
                um = UpdateManager(cfg)
                pre = preflight_update(um, cfg)
                if "error" in pre:
                    result["preflight_error"] = pre["error"]
                else:
                    pre["latest_data"] = dict(um._latest_data)
                    result["preflight"] = pre
        self.finished.emit(result)


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
