"""
app_config — 共享配置管理和密码工具
被 main.py、login_window.py、update_manager.py 共同导入
"""
import sys
import os
import json
import shutil
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
        """运行时文件目录：打包后为 exe 旁的 appdata 文件夹，保持 exe 目录整洁"""
        if getattr(sys, 'frozen', False):
            d = Path(sys.executable).parent / "appdata"
            d.mkdir(parents=True, exist_ok=True)
            return d
        return Path(__file__).resolve().parent

    def _resolve_config_path(self, filename):
        """config.json 位于运行时目录（打包后为 appdata/）"""
        return self.base_dir / filename

    @staticmethod
    def _bundled_config_path():
        """PyInstaller 打包内置的 config.json（用于首次运行引导复制）"""
        if not getattr(sys, 'frozen', False):
            return None
        meipass = getattr(sys, '_MEIPASS', None)
        base = Path(meipass) if meipass else Path(sys.executable).parent
        return base / "config.json"

    def is_dev_mode(self):
        return not getattr(sys, 'frozen', False)

    @property
    def data_dir(self):
        """远程同步数据目录（remote/，与本地数据分开放）"""
        d = self.base_dir / "remote"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def remote_dir(self):
        """远程同步数据目录的正式名称"""
        return self.data_dir

    @property
    def local_dir(self):
        """本地个人数据目录（local_state.json、日志、更新脚本）"""
        d = self.base_dir / "local"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def local_state_path(self):
        """本地个人配置（记住登录、注册用户），不参与远程同步"""
        return self.local_dir / "local_state.json"

    # ---------- 读写 ----------

    def _load(self):
        self._load_data()
        self._load_local_state()

    def _load_data(self):
        self._data = self._defaults()
        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._data = self._deep_merge(self._data, json.load(f))
        else:
            # 首次运行：从打包内置的 config.json 复制引导配置到 appdata/
            bundled = self._bundled_config_path()
            if bundled is not None and bundled.exists():
                try:
                    with open(bundled, "r", encoding="utf-8") as f:
                        self._data = self._deep_merge(self._data, json.load(f))
                    shutil.copyfile(bundled, self._config_path)
                except Exception:
                    pass

        # 叠加私有仓库同步下来的远程配置（网络引导项除外，避免循环依赖）
        overlay = self.data_dir / "config.json"
        if overlay.exists():
            try:
                with open(overlay, "r", encoding="utf-8") as f:
                    remote = json.load(f)
                remote.pop("app", None)          # 版本/名称以本地引导配置为准
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

        # 本地只保留 token 与“记住我”勾选状态，账号信息一律来自远程
        self._local_state = {
            k: v for k, v in self._local_state.items() if k in ("github_token", "remembered")
        }
        self._local_state.setdefault("remembered", {})

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
        """只持久化引导相关配置（app/update/sync），账号与纪念信息以远程为准"""
        slim = {
            "app": self._data.get("app", {}),
            "update": self._data.get("update", {}),
            "sync": self._data.get("sync", {}),
        }
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(slim, f, ensure_ascii=False, indent=4)

    @staticmethod
    def _defaults():
        return {
            "app": {"version": "1.0.0", "name": "Commemorate", "build_date": ""},
            "update": {
                "check_url": "",
                "auto_check": True,
                "skip_version": None,
                "repo_owner": "jx-2-a",
                "repo_name": "Commemorate",
                "branch": "main",
            },
            "sync": {
                "repo_owner": "",
                "repo_name": "my-app-data",
                "branch": "main",
                "use_api": True,
                "files": ["config.json", "data.csv", "rules.txt"],
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

    @app_version.setter
    def app_version(self, value):
        self._data.setdefault("app", {})["version"] = value

    @property
    def app_name(self):
        return self._data.get("app", {}).get("name", "Commemorate")

    @property
    def update_check_url(self):
        url = self._data.get("update", {}).get("check_url", "")
        if url:
            return url
        # 未显式配置时，默认从公开仓库的 version.json 检查更新（无需 token）
        owner = self._data.get("update", {}).get("repo_owner", "")
        repo = self._data.get("update", {}).get("repo_name", "")
        if owner and repo:
            branch = self._data.get("update", {}).get("branch", "main")
            return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/version.json"
        # 兼容旧配置：从数据仓库推导
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
            "files", ["config.json", "data.csv", "rules.txt"]
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
        """读取 GitHub 令牌：优先环境变量，其次本地配置（local_state.json）"""
        token = os.environ.get(self.sync_push_token_env or "GITHUB_TOKEN", "")
        if token:
            return token
        return self._local_state.get("github_token", "")

    def set_local_token(self, token):
        """把令牌保存到本地配置（gitignored），不依赖环境变量"""
        self._local_state["github_token"] = token
        self.save_local_state()

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

    def all_users(self):
        """可登录账户：全部来自远程 config.json 的 auth.local_users"""
        return list(self.local_users)

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
