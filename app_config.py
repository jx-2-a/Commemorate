"""
app_config — 共享配置管理和密码工具
被 main.py、login_window.py、update_manager.py 共同导入
"""
import sys
import os
import json
import hashlib
from pathlib import Path


class ConfigManager:
    """统一管理 config.json 的读取、写入和访问"""

    def __init__(self, config_filename="config.json"):
        self._config_path = self._resolve_config_path(config_filename)
        self._data = {}
        self._local_state = {}
        self._load()

    # ---------- 路径 ----------

    @property
    def base_dir(self):
        """可执行文件 / 脚本所在目录（配置与数据都放在这里）"""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        return Path(__file__).resolve().parent

    def _resolve_config_path(self, filename):
        """PyInstaller 打包模式下 config 在 exe 旁边；开发模式在脚本旁边"""
        return self.base_dir / filename

    def is_dev_mode(self):
        return not getattr(sys, 'frozen', False)

    @property
    def data_dir(self):
        """同步数据目录（默认 <程序目录>/data，不存在则创建）"""
        sub = self._data.get("sync", {}).get("local_dir", "data")
        d = self.base_dir / sub
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def local_state_path(self):
        """本地个人配置（记住登录、注册用户），不参与远程同步"""
        return self.base_dir / "local_state.json"

    # ---------- 读写 ----------

    def _load(self):
        self._load_data()
        self._load_local_state()

    def _load_data(self):
        self._data = self._defaults()
        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._data = self._deep_merge(self._data, json.load(f))

        # 叠加私有仓库同步下来的远程配置（网络引导项除外，避免循环依赖）
        overlay = self.data_dir / "config.json"
        if overlay.exists():
            try:
                with open(overlay, "r", encoding="utf-8") as f:
                    remote = json.load(f)
                remote.pop("update", None)
                remote.pop("sync", None)
                remote.pop("remembered", None)
                self._data = self._deep_merge(self._data, remote)
            except Exception:
                # 远程配置损坏时忽略，继续使用本地配置
                pass

    def reload(self):
        """同步完成后重新读取配置（用户 / 纪念信息可能已更新）"""
        self._load_data()

    def _load_local_state(self):
        if self.local_state_path.exists():
            try:
                with open(self.local_state_path, "r", encoding="utf-8") as f:
                    self._local_state = json.load(f)
            except Exception:
                self._local_state = {}
        else:
            self._local_state = {}

        # 兼容旧版本：把 config.json 里的“记住我”迁移到本地个人配置
        if not self._local_state.get("remembered", {}).get("username"):
            old = self._data.get("remembered", {})
            if old.get("username") or old.get("remember_me"):
                self._local_state["remembered"] = old

    def save_local_state(self):
        """保存本地个人配置（不推送远程）"""
        with open(self.local_state_path, "w", encoding="utf-8") as f:
            json.dump(self._local_state, f, ensure_ascii=False, indent=4)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """递归合并：override 的键覆盖 base，嵌套 dict 逐层合并"""
        result = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def save(self):
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def _defaults():
        return {
            "app": {"version": "1.0.0", "name": "Commemorate", "build_date": ""},
            "update": {"check_url": "", "auto_check": True, "skip_version": None},
            "sync": {
                "repo_owner": "",
                "repo_name": "my-app-data",
                "branch": "main",
                "use_api": True,
                "local_dir": "data",
                "files": ["version.json", "config.json", "data.csv", "rules.txt"],
                "push_files": ["data.csv", "rules.txt"],
                "auto_pull": True,
                "push_token_env": "GITHUB_TOKEN"
            },
            "auth": {
                "mode": "local",
                "api_url": "",
                "request_timeout_seconds": 5,
                "allow_register": False,
                "max_users": 1,
                "local_users": []
            },
            "commemorate": {
                "date": "2021-06-15", "time": "20:30",
                "title": "遇见你", "subtitle": "是我一生中最美丽的意外"
            },
            "remembered": {"username": "", "remember_me": False}
        }

    # ---------- 便捷访问器 ----------

    @property
    def app_version(self):
        return self._data.get("app", {}).get("version", "1.0.0")

    @property
    def app_name(self):
        return self._data.get("app", {}).get("name", "Commemorate")

    @property
    def update_check_url(self):
        url = self._data.get("update", {}).get("check_url", "")
        if url:
            return url
        # 未显式配置时，从私有仓库的 version.json 推导
        owner, repo = self.sync_repo_owner, self.sync_repo_name
        if owner and repo:
            if self.sync_use_api:
                return f"https://api.github.com/repos/{owner}/{repo}/contents/version.json"
            return f"https://raw.githubusercontent.com/{owner}/{repo}/{self.sync_branch}/version.json"
        return ""

    @property
    def update_auto_check(self):
        return self._data.get("update", {}).get("auto_check", True)

    @property
    def update_skip_version(self):
        return self._data.get("update", {}).get("skip_version", None)

    @update_skip_version.setter
    def update_skip_version(self, value):
        self._data.setdefault("update", {})["skip_version"] = value

    @property
    def sync_repo_owner(self):
        return self._data.get("sync", {}).get("repo_owner", "")

    @property
    def sync_repo_name(self):
        return self._data.get("sync", {}).get("repo_name", "my-app-data")

    @property
    def sync_branch(self):
        return self._data.get("sync", {}).get("branch", "main")

    @property
    def sync_use_api(self):
        return self._data.get("sync", {}).get("use_api", True)

    @property
    def sync_files(self):
        return self._data.get("sync", {}).get(
            "files", ["version.json", "config.json", "data.csv", "rules.txt"]
        )

    @property
    def sync_push_files(self):
        return self._data.get("sync", {}).get("push_files", ["data.csv", "rules.txt"])

    @property
    def sync_auto_pull(self):
        return self._data.get("sync", {}).get("auto_pull", True)

    @property
    def sync_push_token_env(self):
        return self._data.get("sync", {}).get("push_token_env", "GITHUB_TOKEN")

    def sync_token(self):
        """读取 GitHub 令牌（用于私有仓库读取和推送）"""
        return os.environ.get(self.sync_push_token_env or "GITHUB_TOKEN", "")

    @property
    def auth_mode(self):
        return self._data.get("auth", {}).get("mode", "local")

    @property
    def auth_api_url(self):
        return self._data.get("auth", {}).get("api_url", "")

    @property
    def auth_timeout(self):
        return self._data.get("auth", {}).get("request_timeout_seconds", 5)

    @property
    def auth_allow_register(self):
        """远程设置：是否开放注册"""
        return self._data.get("auth", {}).get("allow_register", False)

    @property
    def auth_max_users(self):
        """远程设置：允许的用户数量上限"""
        return self._data.get("auth", {}).get("max_users", 1)

    @property
    def local_users(self):
        return self._data.get("auth", {}).get("local_users", [])

    @property
    def registered_users(self):
        """本地注册的用户（保存在 local_state.json，不同步远程）"""
        return self._local_state.get("registered_users", [])

    def add_registered_user(self, username, password_hash):
        users = self._local_state.setdefault("registered_users", [])
        if any(u.get("username") == username for u in users):
            return False
        users.append({
            "username": username,
            "password_hash": password_hash,
            "display_name": username,
        })
        self.save_local_state()
        return True

    def all_users(self):
        """远程管理账户 + 本地注册账户"""
        return list(self.local_users) + list(self.registered_users)

    @property
    def commemorative_date(self):
        return self._data.get("commemorate", {}).get("date", "2021-06-15")

    @property
    def commemorative_time(self):
        return self._data.get("commemorate", {}).get("time", "20:30")

    @property
    def commemorative_title(self):
        return self._data.get("commemorate", {}).get("title", "遇见你")

    @property
    def commemorative_subtitle(self):
        return self._data.get("commemorate", {}).get("subtitle", "是我一生中最美丽的意外")

    @property
    def remembered_username(self):
        return self._local_state.get("remembered", {}).get("username", "")

    @remembered_username.setter
    def remembered_username(self, value):
        self._local_state.setdefault("remembered", {})["username"] = value

    @property
    def remember_me(self):
        return self._local_state.get("remembered", {}).get("remember_me", False)

    @remember_me.setter
    def remember_me(self, value):
        self._local_state.setdefault("remembered", {})["remember_me"] = value

    def save_remember_me(self, username, checked):
        self.remembered_username = username if checked else ""
        self.remember_me = checked
        self.save_local_state()

    def set_pending_auto_login(self, username, password):
        """记录更新重启后的一次性自动登录信息"""
        self._local_state["auto_login"] = {"username": username, "password": password}
        self.save_local_state()

    def take_pending_auto_login(self):
        """取出并清除待自动登录信息，返回 (用户名, 密码) 或 (None, None)"""
        entry = self._local_state.get("auto_login")
        if entry:
            self._local_state.pop("auto_login", None)
            self.save_local_state()
            return entry.get("username", ""), entry.get("password", "")
        return None, None


# ── 密码哈希工具 ───────────────────────────────────────────

def hash_password(password: str, salt: str = None) -> str:
    """生成 salted SHA-256 密码哈希，格式: sha256:<hex_digest>:<hex_salt>"""
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"sha256:{digest}:{salt}"


def verify_password(password: str, stored_hash: str) -> bool:
    """验证密码是否匹配存储的哈希"""
    try:
        parts = stored_hash.split(":")
        if len(parts) != 3 or parts[0] != "sha256":
            return False
        _, digest, salt = parts
        expected = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return digest == expected
    except Exception:
        return False
