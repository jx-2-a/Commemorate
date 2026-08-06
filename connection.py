"""连接配置：GitHub token + 私有数据仓库信息，加密保存，不随远程同步

每个使用者可以拥有自己独立的数据仓库（也可以导入好友分享的加密文件共用）。
文件位于 appdata/local/：
  - connection.dat      加密后的连接信息（可发送给好友导入）
  - connection_key.txt  加密密码（仅本机，用于自动解密）
"""
import base64
import os
import json
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PROFILE_FILENAME = "connection.dat"
KEY_FILENAME = "connection_key.txt"
ITERATIONS = 200_000


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def encrypt_blob(data: dict, password: str) -> str:
    """把连接信息加密成可分享的字符串"""
    salt = os.urandom(16)
    fernet = Fernet(_derive_key(password, salt))
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    token = fernet.encrypt(payload)
    return base64.urlsafe_b64encode(salt + token).decode("ascii")


def decrypt_blob(blob: str, password: str) -> dict:
    """解密连接信息；密码错误抛 InvalidToken"""
    raw = base64.urlsafe_b64decode(blob.encode("ascii"))
    salt, token = raw[:16], raw[16:]
    fernet = Fernet(_derive_key(password, salt))
    payload = fernet.decrypt(token)
    return json.loads(payload.decode("utf-8"))


def _paths(config):
    local_dir = config.local_dir
    return local_dir / PROFILE_FILENAME, local_dir / KEY_FILENAME


def load_profile(config):
    """读取本地加密连接配置；没有或密码不对时返回 None"""
    dat_path, key_path = _paths(config)
    if not dat_path.is_file() or not key_path.is_file():
        return None
    try:
        password = key_path.read_text(encoding="utf-8").strip()
        return decrypt_blob(dat_path.read_text(encoding="ascii").strip(), password)
    except Exception:
        return None


def save_profile(config, data: dict, password: str) -> str:
    """保存连接配置（加密），返回加密后的字符串"""
    dat_path, key_path = _paths(config)
    blob = encrypt_blob(data, password)
    dat_path.write_text(blob, encoding="ascii")
    key_path.write_text(password, encoding="utf-8")
    return blob


def export_profile(config, password: str) -> str:
    """导出当前连接配置为加密字符串（发好友用）"""
    dat_path, _ = _paths(config)
    if not dat_path.is_file():
        return ""
    return dat_path.read_text(encoding="ascii").strip()


def import_profile(config, blob: str, password: str):
    """导入好友分享的加密连接配置"""
    data = decrypt_blob(blob.strip(), password)
    save_profile(config, data, password)
    return data


def remove_profile(config):
    dat_path, key_path = _paths(config)
    for p in (dat_path, key_path):
        if p.exists():
            p.unlink()
