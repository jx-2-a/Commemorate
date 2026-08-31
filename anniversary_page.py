# -*- coding: utf-8 -*-
"""
纪念日记录页 — Anniversary Records Page
========================================
第二个页面：纪念日时间线。

特性：
- 底部内容切换（仿左侧目录的短横线样式）：默认打开最近一次已经过的纪念日，
  往前（左/上滑）看更早的记录，往后看未来几次纪念日的日期、名称与距今时间。
- 每个纪念日前后 3 天内可放送文本 / 上传文件（文档、图片、音频、视频、纯文本）。
- 记录以左侧竖线 + 圆点 + 横线的时间线展示：上传时间、上传用户、内容。
- 图片直接预览、文本直接展示、docx/txt 文档自动读取展示、音视频内嵌播放器；
  点击记录可用默认程序打开。
- 右下角隐藏按钮（与右上角同样的浮现方式）：放送文本 / 上传文件 / 设置纪念日。
- 纪念日设置支持阳历与阴历（农历，内置 1900–2100 年换算表）。

本文件被 main.py 以 PAGE_CLASSES 注册表方式调用，背景（渐变 + 场景动画）
沿用原有 GalleryPage 的绘制，不另做背景。
"""

import calendar
import json
import os
import random
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pyzipper

from PyQt5.QtCore import (
    Qt, QPointF, QRectF, QUrl, QDate, QTimer, QPropertyAnimation, QEasingCurve,
)
from PyQt5.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush, QPixmap,
    QLinearGradient, QFontMetrics, QDesktopServices, QPainterPath,
)
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QDateEdit, QSpinBox, QRadioButton, QButtonGroup,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QSlider,
    QDialogButtonBox, QFormLayout, QFrame, QComboBox, QStackedWidget,
    QGraphicsOpacityEffect, QWidget,
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

from bar_selector import BarSelector

# ============================================================
#  农历（阴历）换算：1900 – 2100
# ============================================================
# 每一年用一个整数编码：低 4 位 = 闰月（0 表示无闰月），
# bit16 = 闰月是否 30 天，bit(16-m) = 第 m 个月是否 30 天。
LUNAR_INFO = [
    0x04bd8, 0x04ae0, 0x0a570, 0x054d5, 0x0d260, 0x0d950, 0x16554, 0x056a0, 0x09ad0, 0x055d2,  # 1900-1909
    0x04ae0, 0x0a5b6, 0x0a4d0, 0x0d250, 0x1d255, 0x0b540, 0x0d6a0, 0x0ada2, 0x095b0, 0x14977,  # 1910-1919
    0x04970, 0x0a4b0, 0x0b4b5, 0x06a50, 0x06d40, 0x1ab54, 0x02b60, 0x09570, 0x052f2, 0x04970,  # 1920-1929
    0x06566, 0x0d4a0, 0x0ea50, 0x06e95, 0x05ad0, 0x02b60, 0x186e3, 0x092e0, 0x1c8d7, 0x0c950,  # 1930-1939
    0x0d4a0, 0x1d8a6, 0x0b550, 0x056a0, 0x1a5b4, 0x025d0, 0x092d0, 0x0d2b2, 0x0a950, 0x0b557,  # 1940-1949
    0x06ca0, 0x0b550, 0x15355, 0x04da0, 0x0a5b0, 0x14573, 0x052b0, 0x0a9a8, 0x0e950, 0x06aa0,  # 1950-1959
    0x0aea6, 0x0ab50, 0x04b60, 0x0aae4, 0x0a570, 0x05260, 0x0f263, 0x0d950, 0x05b57, 0x056a0,  # 1960-1969
    0x096d0, 0x04dd5, 0x04ad0, 0x0a4d0, 0x0d4d4, 0x0d250, 0x0d558, 0x0b540, 0x0b6a0, 0x195a6,  # 1970-1979
    0x095b0, 0x049b0, 0x0a974, 0x0a4b0, 0x0b27a, 0x06a50, 0x06d40, 0x0af46, 0x0ab60, 0x09570,  # 1980-1989
    0x04af5, 0x04970, 0x064b0, 0x074a3, 0x0ea50, 0x06b58, 0x055c0, 0x0ab60, 0x096d5, 0x092e0,  # 1990-1999
    0x0c960, 0x0d954, 0x0d4a0, 0x0da50, 0x07552, 0x056a0, 0x0abb7, 0x025d0, 0x092d0, 0x0cab5,  # 2000-2009
    0x0a950, 0x0b4a0, 0x0baa4, 0x0ad50, 0x055d9, 0x04ba0, 0x0a5b0, 0x15176, 0x052b0, 0x0a930,  # 2010-2019
    0x07954, 0x06aa0, 0x0ad50, 0x05b52, 0x04b60, 0x0a6e6, 0x0a4e0, 0x0d260, 0x0ea65, 0x0d530,  # 2020-2029
    0x05aa0, 0x076a3, 0x096d0, 0x04afb, 0x04ad0, 0x0a4d0, 0x1d0b6, 0x0d250, 0x0d520, 0x0dd45,  # 2030-2039
    0x0b5a0, 0x056d0, 0x055b2, 0x049b0, 0x0a577, 0x0a4b0, 0x0aa50, 0x1b255, 0x06d20, 0x0ada0,  # 2040-2049
    0x14b63, 0x09370, 0x049f8, 0x04970, 0x064b0, 0x168a6, 0x0ea50, 0x06b20, 0x1a6c4, 0x0aae0,  # 2050-2059
    0x092e0, 0x0d2e3, 0x0c960, 0x0d557, 0x0d4a0, 0x0da50, 0x05d55, 0x056a0, 0x0a6d0, 0x055d4,  # 2060-2069
    0x052d0, 0x0a9b8, 0x0a950, 0x0b4a0, 0x0b6a6, 0x0ad50, 0x055a0, 0x0aba4, 0x0a5b0, 0x052b0,  # 2070-2079
    0x0b273, 0x06930, 0x07337, 0x06aa0, 0x0ad50, 0x14b55, 0x04b60, 0x0a570, 0x054e4, 0x0d160,  # 2080-2089
    0x0e968, 0x0d520, 0x0daa0, 0x16aa6, 0x056d0, 0x04ae0, 0x0a9d4, 0x0a2d0, 0x0d150, 0x0f252,  # 2090-2099
    0x0d520,                                                                                    # 2100
]

_TIAN = "甲乙丙丁戊己庚辛壬癸"
_DI = "子丑寅卯辰巳午未申酉戌亥"
_SHENGXIAO = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]
_MONTH_CN = ["", "正月", "二月", "三月", "四月", "五月", "六月",
             "七月", "八月", "九月", "十月", "冬月", "腊月"]
_DAY_CN = ["", "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
           "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
           "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十"]


def _leap_month(y: int) -> int:
    return LUNAR_INFO[y - 1900] & 0x0F


def _leap_days(y: int) -> int:
    if _leap_month(y):
        return 30 if (LUNAR_INFO[y - 1900] & 0x10000) else 29
    return 0


def _month_days(y: int, m: int) -> int:
    return 30 if (LUNAR_INFO[y - 1900] & (0x10000 >> m)) else 29


def _year_days(y: int) -> int:
    total = sum(_month_days(y, m) for m in range(1, 13))
    return total + _leap_days(y)


def lunar_to_solar(lunar_year: int, lunar_month: int, lunar_day: int,
                   is_leap: bool = False) -> date:
    """阴历日期 → 阳历日期（1900–2100）"""
    if not 1900 <= lunar_year <= 2100:
        raise ValueError("农历年份超出 1900–2100 范围")
    if not 1 <= lunar_month <= 12 or not 1 <= lunar_day <= 30:
        raise ValueError("农历月日不合法")
    days = 0
    for y in range(1900, lunar_year):
        days += _year_days(y)
    leap = _leap_month(lunar_year)
    for m in range(1, lunar_month):
        days += _month_days(lunar_year, m)
    if is_leap and leap == lunar_month:
        # 闰月排在同号普通月之后
        days += _month_days(lunar_year, lunar_month)
    elif leap and lunar_month > leap:
        days += _leap_days(lunar_year)
    days += lunar_day - 1
    return date(1900, 1, 31) + timedelta(days=days)


def solar_to_lunar(year: int, month: int, day: int):
    """阳历日期 → (农历年, 农历月, 农历日, 是否闰月)"""
    offset = (date(year, month, day) - date(1900, 1, 31)).days
    if offset < 0:
        raise ValueError("不支持 1900-01-31 之前的日期")
    lunar_year = 1900
    while lunar_year <= 2100:
        yd = _year_days(lunar_year)
        if offset < yd:
            break
        offset -= yd
        lunar_year += 1
    if lunar_year > 2100:
        raise ValueError("农历年份超出范围")
    leap = _leap_month(lunar_year)
    is_leap = False
    lunar_month = 1
    while lunar_month <= 12:
        if leap and lunar_month == leap + 1 and not is_leap:
            # 闰月排在普通月 leap 之后、普通月 leap+1 之前
            ld = _leap_days(lunar_year)
            if offset < ld:
                is_leap = True
                lunar_month = leap  # 闰月与普通月同号
                break
            offset -= ld
        md = _month_days(lunar_year, lunar_month)
        if offset < md:
            break
        offset -= md
        lunar_month += 1
    if lunar_month > 12:
        lunar_month = 12
    return lunar_year, lunar_month, offset + 1, is_leap


def lunar_text(year: int, month: int, day: int, is_leap: bool = False) -> str:
    """农历中文描述，如：甲辰年 正月初一（龙年）"""
    gz = _TIAN[(year - 4) % 10] + _DI[(year - 4) % 12]
    sx = _SHENGXIAO[(year - 4) % 12]
    m = ("闰" if is_leap else "") + _MONTH_CN[month]
    return f"{gz}年 {m}{_DAY_CN[day]}（{sx}年）"


def lunar_month_day_text(month: int, day: int) -> str:
    return f"农历{_MONTH_CN[month]}{_DAY_CN[day]}"


def _days_in_month(y: int, m: int) -> int:
    return calendar.monthrange(y, m)[1]


def _add_months(d: date, n: int) -> date:
    """日期加 n 个月，月底日自动收敛（如 1/31 加 1 个月 → 2/28）"""
    total = d.year * 12 + (d.month - 1) + n
    y, m0 = divmod(total, 12)
    m = m0 + 1
    day = min(d.day, _days_in_month(y, m))
    return date(y, m, day)


# ============================================================
#  数据存储
# ============================================================

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".ico"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".mid"}
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"}
TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".log", ".ini", ".py", ".html", ".htm", ".xml", ".yml", ".yaml"}
DOC_EXTS = {".docx", ".doc", ".pdf", ".rtf", ".xlsx", ".xls", ".pptx", ".ppt"}


def _safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n]+', "_", name).strip()
    return name or "file"


def _extract_docx_text(path: Path, limit: int = 1200) -> str:
    """纯标准库读取 docx 文本（zip + document.xml）"""
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", "ignore")
        xml = xml.replace("</w:p>", "\n")
        xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
        text = re.sub(r"<[^>]+>", "", xml)
        text = (text.replace("&amp;", "&").replace("&lt;", "<")
                    .replace("&gt;", ">").replace("&quot;", '"')
                    .replace("&apos;", "'"))
        lines = [ln.strip() for ln in text.split("\n")]
        lines = [ln for ln in lines if ln]
        return ("\n".join(lines))[:limit] or "(空文档)"
    except Exception:
        return ""


def _extract_text_preview(path: Path, limit: int = 1200) -> str:
    ext = path.suffix.lower()
    try:
        if ext == ".docx":
            return _extract_docx_text(path, limit)
        if ext in TEXT_EXTS:
            data = path.read_bytes()
            for enc in ("utf-8-sig", "utf-8", "gb18030"):
                try:
                    text = data.decode(enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    text = data.decode("utf-8", "ignore")
            return text.strip()[:limit]
    except Exception:
        return ""
    return ""


def _extract_text_full(path: Path, limit: int = 200000) -> str:
    """读取文档/文本的完整内容（预览用，不截断；仅 docx / 纯文本）"""
    ext = path.suffix.lower()
    try:
        if ext == ".docx":
            return _extract_docx_text(path, limit)
        if ext in TEXT_EXTS:
            data = path.read_bytes()
            for enc in ("utf-8-sig", "utf-8", "gb18030"):
                try:
                    return data.decode(enc)[:limit]
                except (UnicodeDecodeError, LookupError):
                    continue
            return data.decode("utf-8", "ignore")[:limit]
    except Exception:
        return ""
    return ""


def record_kind_for(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in VIDEO_EXTS:
        return "video"
    # 文本类也归为“文档”：上传后自动读取展示，点击可用默认程序打开
    return "document"


class AnniversaryStore:
    """Anniversary data store.

    Local store (encrypted zip, AES-256):
        local/anniversary_backup.zip  →  anniversaries.json
                                         <Name>_<date>/records/<id>.json
                                         <Name>_<date>/files/<attachment>
    Remote (synced, plain folders, INCREMENTAL per-file sync):
        remote/anniversary/anniversaries.json
        remote/anniversary/<Name>_<date>/records/<id>.json   (one file per record,
                                                              carries user/time)
        remote/anniversary/<Name>_<date>/files/<attachment>

    Working area (decrypted, SESSION ONLY — deleted on exit, re-extracted on open):
        remote/anniversary/...   (program reads/writes here; wiped at close)

    Sync is per-file: only changed/new records & attachments are pushed/pulled,
    so a single new message uploads one small JSON instead of the whole zip.
    """

    def __init__(self, config):
        self.config = config
        self.anniversaries = []
        self.records = []
        self.deleted_ids = set()
        self.work_dir = None
        self._dirty = False
        self.load()

    def is_dirty(self) -> bool:
        """是否有未推送的本地改动（关闭时据此决定要不要上传）"""
        return self._dirty

    def mark_clean(self):
        self._dirty = False

    def _mark_dirty(self):
        self._dirty = True

    # ---------- 读取 ----------

    def load(self):
        self.anniversaries = self._load_list(self.list_path)
        self.deleted_ids = set(self._load_list(self.deleted_list_path))
        self._migrate_legacy()
        # 记录在工作区打开后才加载（登录同步后由页面 refresh 调用）
        self.records = []

    @property
    def root(self) -> Path:
        return self.config.anniversary_dir

    @property
    def list_path(self) -> Path:
        return self.config.anniversaries_path

    @property
    def zip_path(self) -> Path:
        return self.config.anniversary_records_path

    @property
    def deleted_list_path(self) -> Path:
        return self.root / "deleted.json"

    def _password(self) -> bytes:
        return (self.config.anniversary_zip_password or "commemorate2026").encode()

    def _find_ann(self, aid):
        for a in self.anniversaries:
            if a.get("id") == aid:
                return a
        return None

    def _load_records_from_work(self) -> list:
        out = []
        if self.work_dir and self.work_dir.exists():
            for folder in sorted(self.work_dir.iterdir()):
                if folder.is_dir():
                    for r in self._load_list(folder / "records.json"):
                        fn = r.get("file", "")
                        # 旧数据可能是相对 data_dir 的全路径，统一改成工作区相对路径
                        if fn.startswith("anniversary/"):
                            r["file"] = fn[len("anniversary/"):]
                        out.append(r)
        return out

    def _migrate_legacy(self):
        """旧布局迁移：顶层 anniversaries.json / anniversary_records.json"""
        old_list = self.config.data_dir / "anniversaries.json"
        old_recs = self.config.data_dir / "anniversary_records.json"
        if not self.list_path.exists() and old_list.exists():
            try:
                self.list_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_list, self.list_path)
            except Exception:
                pass
        if not self.anniversaries:
            self.anniversaries = self._load_list(old_list)
        self._legacy_records = self._load_list(old_recs) if old_recs.exists() else []

    @staticmethod
    def _load_list(path: Path) -> list:
        try:
            if path and path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for key in ("anniversaries", "records"):
                        if isinstance(data.get(key), list):
                            return data[key]
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    # ---------- 写入 ----------

    def save_anniversaries(self):
        self.list_path.parent.mkdir(parents=True, exist_ok=True)
        self.list_path.write_text(
            json.dumps(self.anniversaries, ensure_ascii=False, indent=2),
            encoding="utf-8")
        if self.work_dir is not None:
            (self.work_dir / "anniversaries.json").write_text(
                json.dumps(self.anniversaries, ensure_ascii=False, indent=2),
                encoding="utf-8")

    # ---------- 工作区（系统临时目录） ----------

    def open_workspace(self):
        """登录同步后调用：把加密 zip 解压到 remote/anniversary 作为本次会话工作区；
        若远程刚拉取过内容则直接使用（远程优先），否则从本地 zip 解压"""
        self.close_workspace()
        self.work_dir = self.root
        # 只有远程（GitHub 拉取）确实有记录内容时才直接使用；
        # 仅有清单（可能是默认播种）时不阻止从本地 zip 解压
        has_pulled = self.work_dir.exists() and any(
            f.is_file() and f.name != "anniversaries.json"
            for f in self.work_dir.rglob("*"))
        if not has_pulled:
            # 远程没有内容（或刚被清理）：从本地加密 zip 解压
            self._extract_zip()
        self.deleted_ids = set(self._load_list(self.deleted_list_path))
        # 3) 迁移旧格式（content.zip / 散装 records.json）→ 单文件
        self._migrate_remote_content()
        # 4) 远程旧数据若属于已删除纪念日 → 移入 _deleted/ 备份
        self._reconcile_deleted()
        # 4) 加载记录
        self.records = self._load_records()
        # 清单以工作区为准（拉取或解压后的最新版）
        work_list = self.work_dir / "anniversaries.json"
        if work_list.exists():
            self.anniversaries = self._load_list(work_list)
        # 旧版 records（无 zip 的迁移数据）写入工作区
        legacy = getattr(self, "_legacy_records", [])
        if legacy and not self.records:
            self.records = legacy
            self._normalize_legacy_files()
            self.save_records()

    def close_workspace(self):
        """退出前：把工作区内容打包回加密 zip，并删除解密的工作目录"""
        if self.work_dir is None:
            return
        try:
            self.publish_content()
        finally:
            self.delete_workspace()

    def delete_workspace(self):
        """删除解密的工作目录（remote/anniversary），本地只保留加密 zip"""
        if self.work_dir is not None and self.work_dir.exists():
            try:
                shutil.rmtree(self.work_dir, ignore_errors=True)
            except Exception:
                pass
        self.work_dir = None
        self.records = []

    def _extract_zip(self):
        if not self.zip_path.exists() or self.work_dir is None:
            return
        try:
            with pyzipper.AESZipFile(self.zip_path) as z:
                z.setpassword(self._password())
                for name in z.namelist():
                    target = self.work_dir / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(name))
        except Exception:
            pass

    def _overlay_remote(self):
        """远程 individual 文件覆盖到工作区（跳过旧 content.zip）"""
        if not self.root.exists() or self.work_dir is None:
            return
        for folder in sorted(d for d in self.root.iterdir() if d.is_dir()):
            dest = self.work_dir / folder.name
            for f in folder.rglob("*"):
                if f.is_file() and f.name != "content.zip":
                    rel = f.relative_to(folder)
                    target = dest / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, target)
        if self.list_path.exists():
            shutil.copy2(self.list_path, self.work_dir / "anniversaries.json")
            self.anniversaries = self._load_list(self.list_path)

    def _migrate_remote_content(self):
        """旧 content.zip / 散装 records.json → 拆成每条记录一个文件"""
        if not self.root.exists() or self.work_dir is None:
            return
        for folder in sorted(d for d in self.root.iterdir() if d.is_dir()):
            dest = self.work_dir / folder.name
            dest.mkdir(parents=True, exist_ok=True)
            changed = False
            zp = folder / "content.zip"
            if zp.exists():
                try:
                    with pyzipper.AESZipFile(zp) as z:
                        z.setpassword(self._password())
                        for name in z.namelist():
                            target = dest / name
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(z.read(name))
                    zp.unlink(missing_ok=True)
                    changed = True
                except Exception:
                    pass
            old_rp = dest / "records.json"
            if old_rp.exists():
                for r in self._load_list(old_rp):
                    self._write_record_file(dest, r)
                old_rp.unlink(missing_ok=True)
                changed = True
            if changed:
                self._publish_folder(folder.name)

    def _write_record_file(self, folder, rec):
        rid = rec.get("id") or uuid.uuid4().hex[:12]
        rec["id"] = rid
        rd = folder / "records"
        rd.mkdir(parents=True, exist_ok=True)
        (rd / f"{rid}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_records(self):
        out = []
        if self.work_dir and self.work_dir.exists():
            for folder in sorted(d for d in self.work_dir.iterdir() if d.is_dir()):
                if folder.name == "_deleted":
                    continue
                rd = folder / "records"
                if not rd.exists():
                    continue
                for f in sorted(rd.glob("*.json")):
                    try:
                        r = json.loads(f.read_text(encoding="utf-8"))
                        if r.get("anniversary_id") in self.deleted_ids:
                            continue
                        fn = r.get("file", "")
                        if fn.startswith("anniversary/"):
                            fn = fn[len("anniversary/"):]
                        # 附件统一归入 <folder>/files/（旧数据可能在文件夹根）
                        if fn and "/" in fn:
                            parts = fn.split("/")
                            if len(parts) >= 2 and parts[-2] != "files":
                                src = self.work_dir / fn
                                if src.exists():
                                    fdir = self.work_dir / parts[0] / "files"
                                    fdir.mkdir(parents=True, exist_ok=True)
                                    try:
                                        shutil.move(str(src), str(fdir / parts[-1]))
                                        fn = f"{parts[0]}/files/{parts[-1]}"
                                    except Exception:
                                        pass
                                else:
                                    # 附件可能已在 files/ 下，只是记录路径是旧格式
                                    cand = self.work_dir / parts[0] / "files" / parts[-1]
                                    if cand.exists():
                                        fn = f"{parts[0]}/files/{parts[-1]}"
                        if fn != r.get("file", ""):
                            # 路径被规范化：回写记录文件，保证发布到远程的路径一致
                            r["file"] = fn
                            self._write_record_file(folder, r)
                        r["file"] = fn
                        out.append(r)
                    except Exception:
                        continue
        return out

    def _normalize_legacy_files(self):
        """旧版裸文件名附件（remote/records/）搬进工作区对应文件夹的 files/"""
        legacy_dir = self.config.data_dir / "records"
        for r in self.records:
            fn = r.get("file", "")
            if not fn or "/" in fn:
                continue
            src = legacy_dir / fn
            if not src.exists():
                continue
            ann = self._find_ann(r.get("anniversary_id"))
            name = ann.get("name", "Anniversary") if ann else "Anniversary"
            folder = self.work_dir / f"{_safe_filename(name) or 'Anniversary'}_{r.get('date', '')}"
            files_dir = folder / "files"
            files_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, files_dir / fn)
                r["file"] = f"{folder.name}/files/{fn}"
            except Exception:
                continue

    def publish_content(self):
        """工作区内容已在 remote/anniversary；只需更新本地加密 zip。
        （工作区与远程分离的旧逻辑保留：若分离则先复制单文件）"""
        if self.work_dir is None:
            return
        if self.work_dir != self.root:
            for folder in sorted(d for d in self.work_dir.iterdir() if d.is_dir()):
                self._publish_folder(folder.name)
        self._write_zip()

    def _publish_folder(self, folder_name):
        src = self.work_dir / folder_name
        if not src.exists():
            return
        remote_folder = self.root / folder_name
        remote_folder.mkdir(parents=True, exist_ok=True)
        for f in src.rglob("*"):
            if f.is_file():
                rel = f.relative_to(src)
                target = remote_folder / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
        # 清理远程文件夹根部的散装旧附件（已归入 files/）
        for f in remote_folder.iterdir():
            if f.is_file() and f.suffix.lower() != ".json":
                try:
                    f.unlink()
                except Exception:
                    pass

    def _write_zip(self):
        """把工作区整体打包成本地加密 zip（AES-256）"""
        zp = self.zip_path
        try:
            zp.parent.mkdir(parents=True, exist_ok=True)
            tmp = zp.with_suffix(".tmp.zip")
            with pyzipper.AESZipFile(
                    tmp, "w", compression=pyzipper.ZIP_DEFLATED,
                    encryption=pyzipper.WZ_AES) as z:
                z.setpassword(self._password())
                for f in sorted(self.work_dir.rglob("*")):
                    if f.is_file():
                        z.write(str(f), f.relative_to(self.work_dir).as_posix())
            tmp.replace(zp)
        except Exception:
            try:
                zp.with_suffix(".tmp.zip").unlink(missing_ok=True)
            except Exception:
                pass

    def save_records(self):
        """每条记录单独一个 JSON 写入工作区（自带用户/时间信息）；
        同时清理已不存在的记录文件"""
        if self.work_dir is None:
            self.open_workspace()
            return
        active = set()
        for r in self.records:
            ann = self._find_ann(r.get("anniversary_id"))
            name = ann.get("name", "Anniversary") if ann else "Anniversary"
            folder = self.work_dir / f"{_safe_filename(name) or 'Anniversary'}_{r.get('date', '')}"
            folder.mkdir(parents=True, exist_ok=True)
            self._write_record_file(folder, r)
            if r.get("id"):
                active.add(r.get("id"))
        # 删除工作区中已不存在的记录文件（记录被删除/移动时保持干净）
        if self.work_dir.exists():
            for rd in self.work_dir.rglob("records"):
                if rd.is_dir():
                    if "_deleted" in rd.parts:
                        continue   # _deleted/ 是备份区，不做清理
                    for f in rd.glob("*.json"):
                        if f.stem not in active:
                            try:
                                f.unlink()
                            except Exception:
                                pass

    def add_anniversary(self, item: dict):
        item.setdefault("id", uuid.uuid4().hex[:12])
        self.anniversaries.append(item)
        self._mark_dirty()
        self.save_anniversaries()

    def update_anniversary(self, item_id: str, item: dict):
        for i, a in enumerate(self.anniversaries):
            if a.get("id") == item_id:
                item["id"] = item_id
                self.anniversaries[i] = item
                break
        self._mark_dirty()
        self.save_anniversaries()

    def delete_anniversary(self, item_id: str):
        """删除纪念日：本地移除活动数据；内容移入 _deleted 备份（加密 zip 内，
        不参与同步）；deleted.json 记录删除，远程旧文件保留但不再激活"""
        recs = [r for r in self.records if r.get("anniversary_id") == item_id]
        # 已删除清单（参与同步，让其他设备也知道该纪念日已删）
        self.deleted_ids.add(item_id)
        self.save_deleted()
        # 从活动清单移除
        self.anniversaries = [a for a in self.anniversaries if a.get("id") != item_id]
        self.save_anniversaries()
        # 移除活动记录 + 把相关文件夹移入 _deleted/
        self.records = [r for r in self.records if r.get("anniversary_id") != item_id]
        self._move_to_deleted(item_id, recs)
        self.save_records()
        self._mark_dirty()

    def save_deleted(self):
        self.deleted_list_path.parent.mkdir(parents=True, exist_ok=True)
        self.deleted_list_path.write_text(
            json.dumps(sorted(self.deleted_ids), ensure_ascii=False, indent=2),
            encoding="utf-8")

    def _move_to_deleted(self, item_id, recs):
        """把已删除纪念日的文件夹从活动区移入工作区 _deleted/（zip 加密备份）"""
        if self.work_dir is None:
            return
        del_root = self.work_dir / "_deleted"
        del_root.mkdir(parents=True, exist_ok=True)
        for folder in sorted(d for d in self.work_dir.iterdir()
                             if d.is_dir() and d.name != "_deleted"):
            rd = folder / "records"
            belongs = False
            if rd.exists():
                for f in rd.glob("*.json"):
                    try:
                        if json.loads(f.read_text(encoding="utf-8")).get(
                                "anniversary_id") == item_id:
                            belongs = True
                            break
                    except Exception:
                        continue
            if belongs:
                dest = del_root / folder.name
                try:
                    if dest.exists():
                        shutil.rmtree(dest, ignore_errors=True)
                    shutil.move(str(folder), str(dest))
                except Exception:
                    pass

    def _reconcile_deleted(self):
        """远程拉回来的旧文件夹若属于已删除纪念日 → 移入 _deleted/，不重新激活"""
        if self.work_dir is None:
            return
        del_root = self.work_dir / "_deleted"
        for folder in sorted(d for d in self.work_dir.iterdir()
                             if d.is_dir() and d.name != "_deleted"):
            rd = folder / "records"
            if not rd.exists():
                continue
            aid = None
            try:
                for f in rd.glob("*.json"):
                    r = json.loads(f.read_text(encoding="utf-8"))
                    aid = r.get("anniversary_id")
                    if aid:
                        break
            except Exception:
                continue
            if aid and aid in self.deleted_ids:
                del_root.mkdir(parents=True, exist_ok=True)
                dest = del_root / folder.name
                try:
                    if dest.exists():
                        shutil.rmtree(dest, ignore_errors=True)
                    shutil.move(str(folder), str(dest))
                except Exception:
                    pass

    def add_record(self, rec: dict) -> dict:
        rec["id"] = uuid.uuid4().hex[:12]
        self.records.append(rec)
        self._mark_dirty()
        self.save_records()
        return rec

    def copy_file(self, src: Path, ann_name: str, occ_date: str) -> str:
        """复制到工作区 <Name>_<date>/files/，返回相对工作区的路径"""
        if self.work_dir is None:
            self.open_workspace()
        folder = self.work_dir / f"{_safe_filename(ann_name) or 'Anniversary'}_{occ_date}"
        files_dir = folder / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex[:8] + "_" + _safe_filename(src.name)
        dest = files_dir / name
        shutil.copy2(src, dest)
        self._mark_dirty()
        return f"{folder.name}/files/{name}"

    def record_path(self, rec: dict) -> Path:
        fn = rec.get("file", "")
        if not fn:
            return Path()
        p = Path(fn)
        if p.is_absolute():
            return p
        if self.work_dir is not None:
            return self.work_dir / fn
        return Path()


# ============================================================
#  弹窗
# ============================================================

_DARK_QSS = """
QDialog, QMenu, QMessageBox { background-color: #150a2a; color: #f0eaf5; }
QLineEdit, QTextEdit, QSpinBox, QDateEdit, QListWidget {
    background-color: #241238; color: #f0eaf5; border: 1px solid #6b4a86;
    border-radius: 6px; padding: 4px; selection-background-color: #8a4fae;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDateEdit:focus, QListWidget:focus {
    border: 1px solid #ff9dc0;
}
QPushButton {
    background-color: #4b2a68; color: #ffe3ee; border: 1px solid #8a5aa8;
    border-radius: 8px; padding: 6px 14px; min-width: 64px;
}
QPushButton:hover { background-color: #643987; }
QPushButton:pressed { background-color: #7d4ba0; }
QLabel { color: #f0eaf5; }
QRadioButton { color: #f0eaf5; spacing: 6px; }
QRadioButton::indicator { width: 14px; height: 14px; }
QListWidget::item { padding: 8px; border-radius: 6px; }
QListWidget::item:selected { background-color: #6d3f94; }
QListWidget::item:hover { background-color: #45265f; }
QCalendarWidget QWidget { background-color: #241238; color: #f0eaf5; }
QSlider::groove:horizontal { height: 4px; background: #4b2a68; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; background: #ff9dc0; border-radius: 6px; margin: -4px 0; }
QMenu::item { padding: 8px 22px; border-radius: 6px; }
QMenu::item:selected { background-color: #6d3f94; }
"""


class TextRecordDialog(QDialog):
    """放送文本：输入一段话作为当前纪念日的文本记录"""

    def __init__(self, parent=None, title="纪念日", user="我"):
        super().__init__(parent)
        self.setWindowTitle("放送文本")
        self.resize(440, 300)
        lay = QVBoxLayout(self)
        tip = QLabel(f"发送到「{title}」的时间线")
        tip.setStyleSheet("color:#cbb8dd;")
        lay.addWidget(tip)
        self.edit = QTextEdit(self)
        self.edit.setPlaceholderText(f"写点什么吧…（{user}）")
        lay.addWidget(self.edit, 1)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        btns.button(QDialogButtonBox.Ok).setText("发送")
        btns.button(QDialogButtonBox.Cancel).setText("取消")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self.setStyleSheet(_DARK_QSS)

    def text(self) -> str:
        return self.edit.toPlainText().strip()


class AnniversaryEditDialog(QDialog):
    """添加 / 编辑一个纪念日（支持阳历 / 阴历）"""

    def __init__(self, parent=None, item=None):
        super().__init__(parent)
        self._item = item or {}
        self.setWindowTitle("编辑纪念日" if item else "添加纪念日")
        self.resize(420, 380)
        form = QFormLayout(self)

        self.name_edit = QLineEdit(self._item.get("name", ""))
        self.name_edit.setPlaceholderText("例如：在一起的日子 / 她的生日")
        form.addRow("名称", self.name_edit)

        self.solar_radio = QRadioButton("阳历（公历）")
        self.lunar_radio = QRadioButton("阴历（农历）")
        self.cal_group = QButtonGroup(self)
        self.cal_group.addButton(self.solar_radio)
        self.cal_group.addButton(self.lunar_radio)
        cal_row = QHBoxLayout()
        cal_row.addWidget(self.solar_radio)
        cal_row.addWidget(self.lunar_radio)
        form.addRow("历法", cal_row)

        self.solar_date = QDateEdit()
        self.solar_date.setCalendarPopup(True)
        self.solar_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("阳历起始日", self.solar_date)

        lrow = QHBoxLayout()
        self.lunar_year = QSpinBox()
        self.lunar_year.setRange(1900, 2100)
        self.lunar_month = QSpinBox()
        self.lunar_month.setRange(1, 12)
        self.lunar_day = QSpinBox()
        self.lunar_day.setRange(1, 30)
        lrow.addWidget(QLabel("起始年"))
        lrow.addWidget(self.lunar_year)
        lrow.addWidget(QLabel("月"))
        lrow.addWidget(self.lunar_month)
        lrow.addWidget(QLabel("日"))
        lrow.addWidget(self.lunar_day)
        lrow.addStretch(1)
        form.addRow("阴历日期", lrow)

        # 重复方式：每年 / 每月 / 每 N 天
        self.repeat_combo = QComboBox()
        self.repeat_combo.addItem("每年", "year")
        self.repeat_combo.addItem("每月", "month")
        self.repeat_combo.addItem("每 N 天", "days")
        form.addRow("重复", self.repeat_combo)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 365)
        self.interval_lbl = QLabel("天")
        int_row = QHBoxLayout()
        int_row.addWidget(self.interval_spin)
        int_row.addWidget(self.interval_lbl)
        int_row.addStretch(1)
        form.addRow("间隔", int_row)

        # 生效次数：0 = 不限
        self.count_spin = QSpinBox()
        self.count_spin.setRange(0, 99999)
        self.count_spin.setSpecialValueText("不限")
        form.addRow("生效次数", self.count_spin)

        self.note_edit = QLineEdit(self._item.get("note", ""))
        self.note_edit.setPlaceholderText("备注（可选）")
        form.addRow("备注", self.note_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        btns.button(QDialogButtonBox.Ok).setText("保存")
        btns.button(QDialogButtonBox.Cancel).setText("取消")
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

        calendar = self._item.get("calendar", "solar")
        rep = self._item.get("repeat", "year") or "year"
        if calendar == "lunar":
            self.lunar_radio.setChecked(True)
            self.lunar_year.setValue(int(self._item.get("year") or date.today().year))
            self.lunar_month.setValue(int(self._item.get("month", 1)))
            self.lunar_day.setValue(int(self._item.get("day", 1)))
        else:
            self.solar_radio.setChecked(True)
            try:
                d = date.fromisoformat(self._item.get("date", "2021-06-15"))
                self.solar_date.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                pass
        idx = self.repeat_combo.findData(rep)
        if idx >= 0:
            self.repeat_combo.setCurrentIndex(idx)
        self.interval_spin.setValue(max(1, int(self._item.get("interval", 1) or 1)))
        self.count_spin.setValue(max(0, int(self._item.get("count", 0) or 0)))
        self.solar_radio.toggled.connect(self._sync_visibility)
        self.repeat_combo.currentIndexChanged.connect(self._sync_visibility)
        self._sync_visibility()
        self.setStyleSheet(_DARK_QSS)

    def _sync_visibility(self):
        solar = self.solar_radio.isChecked()
        self.solar_date.setVisible(solar)
        self.lunar_year.setVisible(not solar)
        self.lunar_month.setVisible(not solar)
        self.lunar_day.setVisible(not solar)
        # 阴历固定每年；阳历可选择每月 / 每 N 天
        self.repeat_combo.setVisible(solar)
        rep = self.repeat_combo.currentData() if solar else "year"
        self.interval_spin.setVisible(solar and rep in ("month", "days"))
        self.interval_lbl.setVisible(solar and rep in ("month", "days"))
        self.interval_lbl.setText("个月" if rep == "month" else "天")

    def _on_ok(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请填写纪念日名称")
            return
        self.accept()

    def value(self) -> dict:
        if self.solar_radio.isChecked():
            d = self.solar_date.date()
            rep = self.repeat_combo.currentData() or "year"
            return {
                "name": self.name_edit.text().strip(),
                "calendar": "solar",
                "date": f"{d.year():04d}-{d.month():02d}-{d.day():02d}",
                "repeat": rep,
                "interval": self.interval_spin.value() if rep in ("month", "days") else 1,
                "count": self.count_spin.value(),
                "note": self.note_edit.text().strip(),
            }
        return {
            "name": self.name_edit.text().strip(),
            "calendar": "lunar",
            "year": self.lunar_year.value(),
            "month": self.lunar_month.value(),
            "day": self.lunar_day.value(),
            "repeat": "year",
            "interval": 1,
            "count": self.count_spin.value(),
            "note": self.note_edit.text().strip(),
        }


class AnniversarySettingsDialog(QDialog):
    """纪念日管理：列表 + 添加 / 编辑 / 删除"""

    def __init__(self, store: AnniversaryStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("设置纪念日")
        self.resize(460, 420)
        lay = QVBoxLayout(self)
        self.list_widget = QListWidget(self)
        lay.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加")
        edit_btn = QPushButton("编辑")
        del_btn = QPushButton("删除")
        close_btn = QPushButton("关闭")
        for b in (add_btn, edit_btn, del_btn, close_btn):
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        add_btn.clicked.connect(self._add)
        edit_btn.clicked.connect(self._edit)
        del_btn.clicked.connect(self._delete)
        close_btn.clicked.connect(self.accept)
        self._refresh_list()
        self.setStyleSheet(_DARK_QSS)

    def _refresh_list(self):
        self.list_widget.clear()
        for a in self.store.anniversaries:
            rep = a.get("repeat", "year") or "year"
            interval = max(1, int(a.get("interval", 1) or 1))
            count = max(0, int(a.get("count", 0) or 0))
            if rep == "month":
                rep_txt = f"每月 ×{interval}" if interval > 1 else "每月"
            elif rep == "days":
                rep_txt = f"每 {interval} 天"
            else:
                rep_txt = "每年"
            if count:
                rep_txt += f" · 共 {count} 次"
            if a.get("calendar") == "lunar":
                label = (f"{a.get('name', '纪念日')}  ·  "
                         f"阴历 {a.get('month', 1)}月{a.get('day', 1)}日 · {rep_txt}"
                         + (f"（{a.get('note')}）" if a.get("note") else ""))
            else:
                label = (f"{a.get('name', '纪念日')}  ·  阳历 {a.get('date', '')}"
                         + f" · {rep_txt}"
                         + (f"（{a.get('note')}）" if a.get("note") else ""))
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, a.get("id", ""))
            self.list_widget.addItem(item)

    def _selected_id(self) -> str:
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item else ""

    def _find(self, item_id: str):
        for a in self.store.anniversaries:
            if a.get("id") == item_id:
                return a
        return None

    def _add(self):
        dlg = AnniversaryEditDialog(self, None)
        if dlg.exec_() == QDialog.Accepted:
            self.store.add_anniversary(dlg.value())
            self._refresh_list()

    def _edit(self):
        item_id = self._selected_id()
        item = self._find(item_id)
        if not item:
            QMessageBox.information(self, "提示", "请先选择一个纪念日")
            return
        dlg = AnniversaryEditDialog(self, item)
        if dlg.exec_() == QDialog.Accepted:
            self.store.update_anniversary(item_id, dlg.value())
            self._refresh_list()

    def _delete(self):
        item_id = self._selected_id()
        item = self._find(item_id)
        if not item:
            QMessageBox.information(self, "提示", "请先选择一个纪念日")
            return
        if QMessageBox.question(
                self, "删除", f"确定删除「{item.get('name')}」吗？"
        ) != QMessageBox.Yes:
            return
        self.store.delete_anniversary(item_id)
        self._refresh_list()


class MediaPlayerDialog(QDialog):
    """音视频播放器（内嵌 QMediaPlayer + QVideoWidget）"""

    def __init__(self, path: Path, is_video: bool, parent=None):
        super().__init__(parent)
        self.path = path
        self.is_video = is_video
        self.setWindowTitle(("播放视频：", "播放音乐：")[not is_video] + path.name)
        if is_video:
            self.resize(760, 520)
        else:
            self.resize(420, 130)
        lay = QVBoxLayout(self)

        self.player = QMediaPlayer(self)
        if is_video:
            self.video = QVideoWidget(self)
            self.player.setVideoOutput(self.video)
            lay.addWidget(self.video, 1)

        ctrl = QHBoxLayout()
        self.play_btn = QPushButton("播放")
        self.play_btn.clicked.connect(self._toggle)
        ctrl.addWidget(self.play_btn)
        open_btn = QPushButton("默认程序打开")
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path))))
        ctrl.addWidget(open_btn)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.sliderMoved.connect(self.player.setPosition)
        ctrl.addWidget(self.slider, 1)
        self.time_lbl = QLabel("00:00 / 00:00")
        ctrl.addWidget(self.time_lbl)
        lay.addLayout(ctrl)

        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.positionChanged.connect(self._on_pos)
        self.player.durationChanged.connect(self._on_duration)
        self.player.stateChanged.connect(self._on_state)
        self.player.error.connect(self._on_error)
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(str(path))))
        self.player.play()
        self.setStyleSheet(_DARK_QSS)

    def _toggle(self):
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _fmt(self, ms: int) -> str:
        s = max(0, int(ms / 1000))
        return f"{s // 60:02d}:{s % 60:02d}"

    def _on_pos(self, pos):
        if not self.slider.isSliderDown():
            self.slider.setValue(pos)
        dur = self.player.duration()
        self.time_lbl.setText(f"{self._fmt(pos)} / {self._fmt(dur)}")

    def _on_duration(self, dur):
        self.slider.setRange(0, max(1, dur))

    def _on_state(self, state):
        self.play_btn.setText("暂停" if state == QMediaPlayer.PlayingState else "播放")

    def _on_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.player.setPosition(0)
            self.player.pause()

    def _on_error(self, err):
        try:
            msg = self.player.errorString() or str(err)
        except Exception:
            msg = "未知错误"
        QMessageBox.warning(
            self, "无法播放",
            f"当前系统缺少该格式的解码器：\n{msg}\n\n将用默认程序打开。")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))
        self.close()

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)


class TextViewDialog(QDialog):
    """完整文本查看"""

    def __init__(self, text: str, title: str = "文本内容", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 420)
        lay = QVBoxLayout(self)
        edit = QTextEdit(self)
        edit.setReadOnly(True)
        edit.setPlainText(text)
        lay.addWidget(edit)
        self.setStyleSheet(_DARK_QSS)


# ============================================================
#  窗口内临时控件面板（替代弹窗：嵌在主窗口里，不弹出新窗口）
# ============================================================

_PANEL_QSS = """
QFrame#tempPanel {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(26,18,50,242), stop:1 rgba(17,11,36,242));
    border: 1px solid rgba(120,170,235,120);
    border-radius: 16px;
}
QLabel { color: #f0eaf5; font-family: "Microsoft YaHei"; }
QLineEdit, QTextEdit, QSpinBox, QDateEdit, QComboBox, QListWidget {
    background: rgba(30,22,58,230); color: #f0eaf5; font-family: "Microsoft YaHei";
    border: 1px solid rgba(120,170,235,90); border-radius: 8px; padding: 4px;
    selection-background-color: #5b6fae;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDateEdit:focus,
QComboBox:focus, QListWidget:focus { border: 1px solid rgba(150,200,255,200); }
QPushButton {
    background: rgba(72,94,168,190); color: #ffffff; font-family: "Microsoft YaHei";
    border: none; border-radius: 8px; padding: 6px 14px; min-width: 56px;
}
QPushButton:hover { background: rgba(98,124,210,230); }
QPushButton#danger { background: rgba(168,74,96,190); }
QPushButton#danger:hover { background: rgba(198,90,112,230); }
QRadioButton { color: #f0eaf5; spacing: 6px; }
QComboBox QAbstractItemView {
    background: #251b4a; color: #f0eaf5; selection-background-color: #5b6fae;
}
QListWidget::item { padding: 7px; border-radius: 6px; }
QListWidget::item:selected { background-color: #44579a; }
QListWidget::item:hover { background-color: #2e2455; }
QCalendarWidget QWidget { background-color: #251b4a; color: #f0eaf5; }
"""


class TempPanel(QFrame):
    """窗口内临时控件基类：嵌在主窗口中，淡入显示，点击外部关闭"""

    def __init__(self, parent, title, w, h):
        super().__init__(parent)
        self.setObjectName("tempPanel")
        self.setStyleSheet(_PANEL_QSS)
        self.setFixedSize(w, h)
        self._on_closed = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 16)
        head = QHBoxLayout()
        t = QLabel(title)
        t.setStyleSheet("font-size:16px; font-weight:bold; color:#cfe0ff;")
        head.addWidget(t)
        head.addStretch(1)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet(
            "background:transparent; color:#cfe0ff; font-size:17px;")
        close_btn.clicked.connect(self.close_panel)
        head.addWidget(close_btn)
        lay.addLayout(head)
        self._body = QVBoxLayout()
        lay.addLayout(self._body, 1)

    def set_on_closed(self, cb):
        self._on_closed = cb

    def close_panel(self):
        self.hide()
        if self._on_closed:
            cb = self._on_closed
            self._on_closed = None
            cb()

    def fade_in(self):
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeleteWhenStopped)


class TextPanel(TempPanel):
    """放送文本：内嵌输入框"""

    def __init__(self, parent, ann_name, user, on_send):
        super().__init__(parent, "放送文本", 480, 300)
        self._on_send = on_send
        tip = QLabel(f"发送到「{ann_name}」的时间线")
        tip.setStyleSheet("color:#b8c8e8; font-size:12px;")
        self._body.addWidget(tip)
        self.edit = QTextEdit()
        self.edit.setPlaceholderText(f"写点什么吧…（{user}）")
        self._body.addWidget(self.edit, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.close_panel)
        send = QPushButton("发送")

        def do_send():
            text = self.edit.toPlainText().strip()
            if text:
                self._on_send(text)
                self.close_panel()

        send.clicked.connect(do_send)
        row.addWidget(cancel)
        row.addWidget(send)
        self._body.addLayout(row)


class VideoPanel(TempPanel):
    """视频预览：内嵌播放器（不再弹窗）"""

    def __init__(self, parent, path):
        super().__init__(parent, "视频预览", 760, 520)
        self.path = path
        self.player = QMediaPlayer(self)
        self.video = QVideoWidget()
        self.player.setVideoOutput(self.video)
        self._body.addWidget(self.video, 1)

        ctrl = QHBoxLayout()
        self.play_btn = QPushButton("播放")
        self.play_btn.clicked.connect(self._toggle)
        ctrl.addWidget(self.play_btn)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.sliderMoved.connect(self.player.setPosition)
        ctrl.addWidget(self.slider, 1)
        open_btn = QPushButton("默认程序打开")
        open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))
        ctrl.addWidget(open_btn)
        self._body.addLayout(ctrl)

        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.positionChanged.connect(self._on_pos)
        self.player.durationChanged.connect(
            lambda d: self.slider.setRange(0, max(1, d)))
        self.player.stateChanged.connect(self._on_state)
        self.player.error.connect(self._on_error)
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(str(path))))
        self.player.play()

    def _toggle(self):
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_pos(self, pos):
        if not self.slider.isSliderDown():
            self.slider.setValue(pos)

    def _on_state(self, state):
        self.play_btn.setText("暂停" if state == QMediaPlayer.PlayingState else "播放")

    def _on_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.player.setPosition(0)
            self.player.pause()

    def _on_error(self, err):
        try:
            msg = self.player.errorString() or str(err)
        except Exception:
            msg = "未知错误"
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))
        self.close_panel()

    def close_panel(self):
        self.player.stop()
        super().close_panel()


class SettingsPanel(TempPanel):
    """设置纪念日：内嵌列表 + 表单（含阳历/阴历、重复方式、生效次数）"""

    def __init__(self, parent, store, on_done, notify=None):
        super().__init__(parent, "设置纪念日", 600, 480)
        self.store = store
        self._on_done = on_done
        self._notify = notify or (lambda text: None)
        self._editing_id = None
        self._delete_armed_at = 0

        self._stack = QStackedWidget()
        self._body.addWidget(self._stack, 1)
        self._build_list_page()
        self._build_edit_page()
        self._refresh_list()

    # ---------- 列表页 ----------

    def _build_list_page(self):
        page = QFrame()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        lay.addWidget(self.list_widget, 1)
        row = QHBoxLayout()
        add_btn = QPushButton("添加")
        edit_btn = QPushButton("编辑")
        self.del_btn = QPushButton("删除")
        self.del_btn.setObjectName("danger")
        done_btn = QPushButton("完成")
        add_btn.clicked.connect(self._start_add)
        edit_btn.clicked.connect(self._start_edit)
        self.del_btn.clicked.connect(self._delete)
        done_btn.clicked.connect(self.close_panel)
        for b in (add_btn, edit_btn, self.del_btn, done_btn):
            row.addWidget(b)
        lay.addLayout(row)
        self._stack.addWidget(page)

    def _refresh_list(self):
        self.list_widget.clear()
        for a in self.store.anniversaries:
            rep = a.get("repeat", "year") or "year"
            interval = max(1, int(a.get("interval", 1) or 1))
            count = max(0, int(a.get("count", 0) or 0))
            if rep == "month":
                rep_txt = f"每月 ×{interval}" if interval > 1 else "每月"
            elif rep == "days":
                rep_txt = f"每 {interval} 天"
            else:
                rep_txt = "每年"
            if count:
                rep_txt += f" · 共 {count} 次"
            if a.get("calendar") == "lunar":
                label = (f"{a.get('name', '纪念日')}  ·  阴历 "
                         f"{a.get('month', 1)}月{a.get('day', 1)}日 · {rep_txt}")
            else:
                label = (f"{a.get('name', '纪念日')}  ·  阳历 "
                         f"{a.get('date', '')} · {rep_txt}")
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, a.get("id", ""))
            self.list_widget.addItem(item)

    def _selected_id(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item else ""

    def _find(self, item_id):
        for a in self.store.anniversaries:
            if a.get("id") == item_id:
                return a
        return None

    def _start_add(self):
        self._editing_id = None
        self._reset_form({})
        self._stack.setCurrentIndex(1)

    def _start_edit(self):
        item_id = self._selected_id()
        item = self._find(item_id)
        if not item:
            self._flash_label("请先选择一个纪念日")
            return
        self._editing_id = item_id
        self._reset_form(item)
        self._stack.setCurrentIndex(1)

    def _delete(self):
        import time as _time
        now = _time.monotonic()
        if (now - self._delete_armed_at > 3
                or self.del_btn.text() != "Click again to confirm"):
            item_id = self._selected_id()
            if not self._find(item_id):
                self._flash_label("请先选择一个纪念日")
                return
            self._delete_armed_at = now
            self.del_btn.setText("Click again to confirm")
            return
        item_id = self._selected_id()
        self.store.delete_anniversary(item_id)
        self._delete_armed_at = 0
        self.del_btn.setText("删除")
        self._refresh_list()

    def _flash_label(self, text):
        self._notify(text)

    # ---------- 表单页 ----------

    def _build_edit_page(self):
        page = QFrame()
        form = QFormLayout(page)
        form.setContentsMargins(4, 4, 4, 0)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：在一起的日子 / 她的生日")
        form.addRow("名称", self.name_edit)

        self.solar_radio = QRadioButton("阳历（公历）")
        self.lunar_radio = QRadioButton("阴历（农历）")
        self.cal_group = QButtonGroup(self)
        self.cal_group.addButton(self.solar_radio)
        self.cal_group.addButton(self.lunar_radio)
        cal_row = QHBoxLayout()
        cal_row.addWidget(self.solar_radio)
        cal_row.addWidget(self.lunar_radio)
        form.addRow("历法", cal_row)

        self.solar_date = QDateEdit()
        self.solar_date.setCalendarPopup(True)
        self.solar_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("阳历起始日", self.solar_date)

        lrow = QHBoxLayout()
        self.lunar_year = QSpinBox()
        self.lunar_year.setRange(1900, 2100)
        self.lunar_month = QSpinBox()
        self.lunar_month.setRange(1, 12)
        self.lunar_day = QSpinBox()
        self.lunar_day.setRange(1, 30)
        lrow.addWidget(QLabel("起始年"))
        lrow.addWidget(self.lunar_year)
        lrow.addWidget(QLabel("月"))
        lrow.addWidget(self.lunar_month)
        lrow.addWidget(QLabel("日"))
        lrow.addWidget(self.lunar_day)
        form.addRow("阴历日期", lrow)

        self.repeat_combo = QComboBox()
        self.repeat_combo.addItem("每年", "year")
        self.repeat_combo.addItem("每月", "month")
        self.repeat_combo.addItem("每 N 天", "days")
        form.addRow("重复", self.repeat_combo)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 365)
        self.interval_lbl = QLabel("天")
        int_row = QHBoxLayout()
        int_row.addWidget(self.interval_spin)
        int_row.addWidget(self.interval_lbl)
        form.addRow("间隔", int_row)

        self.count_spin = QSpinBox()
        self.count_spin.setRange(0, 99999)
        self.count_spin.setSpecialValueText("不限")
        form.addRow("生效次数", self.count_spin)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("备注（可选）")
        form.addRow("备注", self.note_edit)

        row = QHBoxLayout()
        row.addStretch(1)
        back_btn = QPushButton("返回")
        save_btn = QPushButton("保存")
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        save_btn.clicked.connect(self._save_form)
        row.addWidget(back_btn)
        row.addWidget(save_btn)
        form.addRow(row)

        self.solar_radio.toggled.connect(self._sync_visibility)
        self.repeat_combo.currentIndexChanged.connect(self._sync_visibility)
        self._sync_visibility()
        self._stack.addWidget(page)

    def _sync_visibility(self):
        solar = self.solar_radio.isChecked()
        self.solar_date.setVisible(solar)
        self.lunar_year.setVisible(not solar)
        self.lunar_month.setVisible(not solar)
        self.lunar_day.setVisible(not solar)
        self.repeat_combo.setVisible(solar)
        rep = self.repeat_combo.currentData() if solar else "year"
        show_int = solar and rep in ("month", "days")
        self.interval_spin.setVisible(show_int)
        self.interval_lbl.setVisible(show_int)
        self.interval_lbl.setText("个月" if rep == "month" else "天")

    def _reset_form(self, item):
        item = item or {}
        self.name_edit.setText(item.get("name", ""))
        calendar = item.get("calendar", "solar")
        if calendar == "lunar":
            self.lunar_radio.setChecked(True)
            self.lunar_year.setValue(int(item.get("year") or date.today().year))
            self.lunar_month.setValue(int(item.get("month", 1)))
            self.lunar_day.setValue(int(item.get("day", 1)))
        else:
            self.solar_radio.setChecked(True)
            try:
                d = date.fromisoformat(item.get("date", "2021-06-15"))
                self.solar_date.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                self.solar_date.setDate(QDate.currentDate())
        idx = self.repeat_combo.findData(item.get("repeat", "year"))
        if idx >= 0:
            self.repeat_combo.setCurrentIndex(idx)
        self.interval_spin.setValue(max(1, int(item.get("interval", 1) or 1)))
        self.count_spin.setValue(max(0, int(item.get("count", 0) or 0)))
        self.note_edit.setText(item.get("note", ""))
        self._sync_visibility()

    def _save_form(self):
        name = self.name_edit.text().strip()
        if not name:
            self._flash_label("请填写纪念日名称")
            return
        if self.solar_radio.isChecked():
            d = self.solar_date.date()
            rep = self.repeat_combo.currentData() or "year"
            item = {
                "name": name,
                "calendar": "solar",
                "date": f"{d.year():04d}-{d.month():02d}-{d.day():02d}",
                "repeat": rep,
                "interval": self.interval_spin.value() if rep in ("month", "days") else 1,
                "count": self.count_spin.value(),
                "note": self.note_edit.text().strip(),
            }
        else:
            item = {
                "name": name,
                "calendar": "lunar",
                "year": self.lunar_year.value(),
                "month": self.lunar_month.value(),
                "day": self.lunar_day.value(),
                "repeat": "year",
                "interval": 1,
                "count": self.count_spin.value(),
                "note": self.note_edit.text().strip(),
            }
        if self._editing_id:
            self.store.update_anniversary(self._editing_id, item)
        else:
            self.store.add_anniversary(item)
        self._stack.setCurrentIndex(0)
        self._refresh_list()


# ============================================================
#  页面模式视图（仿登录/注册切换：背景不变，内容整页切换 + 返回）
# ============================================================

_MODE_QSS = """
QLabel { color: #f0eaf5; font-family: "Microsoft YaHei"; }
QLineEdit, QTextEdit, QSpinBox, QDateEdit, QComboBox, QListWidget {
    background: rgba(30,22,58,225); color: #f0eaf5; font-family: "Microsoft YaHei";
    border: 1px solid rgba(120,170,235,100); border-radius: 8px; padding: 5px;
    selection-background-color: #5b6fae;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDateEdit:focus,
QComboBox:focus, QListWidget:focus { border: 1px solid rgba(150,200,255,210); }
QPushButton {
    background: rgba(72,94,168,190); color: #ffffff; font-family: "Microsoft YaHei";
    border: none; border-radius: 8px; padding: 7px 16px; min-width: 64px;
}
QPushButton:hover { background: rgba(98,124,210,235); }
QPushButton#danger { background: rgba(168,74,96,190); }
QPushButton#danger:hover { background: rgba(198,90,112,235); }
QPushButton#back {
    background: rgba(42,52,98,150); color: #cfe0ff; font-size: 13px;
    border-radius: 10px; padding: 6px 14px; min-width: 0;
}
QPushButton#back:hover { background: rgba(68,86,152,215); }
QRadioButton { color: #f0eaf5; spacing: 6px; }
QComboBox QAbstractItemView {
    background: #251b4a; color: #f0eaf5; selection-background-color: #5b6fae;
}
QListWidget::item { padding: 8px; border-radius: 6px; }
QListWidget::item:selected { background-color: #44579a; }
QListWidget::item:hover { background-color: #2e2455; }
QCalendarWidget QWidget { background-color: #251b4a; color: #f0eaf5; }
"""


class ModeView(QWidget):
    """页面模式容器：透明、背景透出；左上角 ‹ 返回 退回时间线"""

    def __init__(self, parent, title):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(_MODE_QSS)
        self._on_back = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 20)
        head = QHBoxLayout()
        self.back_btn = QPushButton("\u2039 Back")
        self.back_btn.setObjectName("back")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.go_back)
        head.addWidget(self.back_btn)
        t = QLabel(title)
        t.setStyleSheet("font-size:18px; font-weight:bold; color:#dbeaff;")
        head.addWidget(t)
        head.addStretch(1)
        lay.addLayout(head)
        self._body = QVBoxLayout()
        lay.addLayout(self._body, 1)

    def set_on_back(self, cb):
        self._on_back = cb

    def go_back(self):
        if self._on_back:
            self._on_back()


class TextModeView(ModeView):
    """Send Text: full-page input view"""

    def __init__(self, parent, ann_name, user, on_send):
        super().__init__(parent, "Send Text")
        self._on_send = on_send
        tip = QLabel(f"Send to the timeline of {ann_name}")
        tip.setStyleSheet("color:#b8c8e8; font-size:12px;")
        self._body.addWidget(tip)
        self.edit = QTextEdit()
        self.edit.setPlaceholderText(f"Write something… ({user})")
        self._body.addWidget(self.edit, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.go_back)
        send = QPushButton("Send")

        def do_send():
            text = self.edit.toPlainText().strip()
            if text:
                self._on_send(text)
                self.go_back()

        send.clicked.connect(do_send)
        row.addWidget(cancel)
        row.addWidget(send)
        self._body.addLayout(row)
        self.edit.setFocus()


class SettingsModeView(ModeView):
    """Set Anniversaries: full-page list + form view"""

    def __init__(self, parent, store, on_done, notify=None):
        super().__init__(parent, "Set Anniversaries")
        self.store = store
        self._on_done = on_done
        self._notify = notify or (lambda text: None)
        self._editing_id = None
        self._delete_armed_at = 0

        self._stack = QStackedWidget()
        self._body.addWidget(self._stack, 1)
        self._build_list_page()
        self._build_edit_page()
        self._refresh_list()

    def _build_list_page(self):
        page = QFrame()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        lay.addWidget(self.list_widget, 1)
        row = QHBoxLayout()
        add_btn = QPushButton("Add")
        edit_btn = QPushButton("Edit")
        self.del_btn = QPushButton("Delete")
        self.del_btn.setObjectName("danger")
        done_btn = QPushButton("Done")
        add_btn.clicked.connect(self._start_add)
        edit_btn.clicked.connect(self._start_edit)
        self.del_btn.clicked.connect(self._delete)

        def finish():
            if self._on_done:
                self._on_done()
            self.go_back()

        done_btn.clicked.connect(finish)
        for b in (add_btn, edit_btn, self.del_btn, done_btn):
            row.addWidget(b)
        lay.addLayout(row)
        self._stack.addWidget(page)

    def _refresh_list(self):
        self.list_widget.clear()
        for a in self.store.anniversaries:
            rep = a.get("repeat", "year") or "year"
            interval = max(1, int(a.get("interval", 1) or 1))
            count = max(0, int(a.get("count", 0) or 0))
            if rep == "month":
                rep_txt = f"Monthly x{interval}" if interval > 1 else "Monthly"
            elif rep == "days":
                rep_txt = f"Every {interval} day(s)"
            else:
                rep_txt = "Yearly"
            if count:
                rep_txt += f" · {count} times"
            if a.get("calendar") == "lunar":
                label = (f"{a.get('name', 'Anniversary')}  ·  Lunar "
                         f"{a.get('month', 1)}/{a.get('day', 1)} · {rep_txt}")
            else:
                label = (f"{a.get('name', 'Anniversary')}  ·  Solar "
                         f"{a.get('date', '')} · {rep_txt}")
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, a.get("id", ""))
            self.list_widget.addItem(item)

    def _selected_id(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item else ""

    def _find(self, item_id):
        for a in self.store.anniversaries:
            if a.get("id") == item_id:
                return a
        return None

    def _start_add(self):
        self._editing_id = None
        self._reset_form({})
        self._stack.setCurrentIndex(1)

    def _start_edit(self):
        item_id = self._selected_id()
        item = self._find(item_id)
        if not item:
            self._notify("Please select an anniversary")
            return
        self._editing_id = item_id
        self._reset_form(item)
        self._stack.setCurrentIndex(1)

    def _delete(self):
        import time as _time
        now = _time.monotonic()
        if (now - self._delete_armed_at > 3
                or self.del_btn.text() != "Click again to confirm"):
            item_id = self._selected_id()
            if not self._find(item_id):
                self._notify("Please select an anniversary")
                return
            self._delete_armed_at = now
            self.del_btn.setText("Click again to confirm")
            return
        item_id = self._selected_id()
        self.store.delete_anniversary(item_id)
        self._delete_armed_at = 0
        self.del_btn.setText("Delete")
        self._refresh_list()

    def _build_edit_page(self):
        page = QFrame()
        form = QFormLayout(page)
        form.setContentsMargins(4, 4, 4, 0)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. The day we met / Her birthday")
        form.addRow("Name", self.name_edit)

        self.solar_radio = QRadioButton("Solar (Gregorian)")
        self.lunar_radio = QRadioButton("Lunar (Chinese)")
        self.cal_group = QButtonGroup(self)
        self.cal_group.addButton(self.solar_radio)
        self.cal_group.addButton(self.lunar_radio)
        cal_row = QHBoxLayout()
        cal_row.addWidget(self.solar_radio)
        cal_row.addWidget(self.lunar_radio)
        form.addRow("Calendar", cal_row)

        self.solar_date = QDateEdit()
        self.solar_date.setCalendarPopup(True)
        self.solar_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Solar start date", self.solar_date)

        lrow = QHBoxLayout()
        self.lunar_year = QSpinBox()
        self.lunar_year.setRange(1900, 2100)
        self.lunar_month = QSpinBox()
        self.lunar_month.setRange(1, 12)
        self.lunar_day = QSpinBox()
        self.lunar_day.setRange(1, 30)
        lrow.addWidget(QLabel("Year"))
        lrow.addWidget(self.lunar_year)
        lrow.addWidget(QLabel("Mon"))
        lrow.addWidget(self.lunar_month)
        lrow.addWidget(QLabel("Day"))
        lrow.addWidget(self.lunar_day)
        form.addRow("Lunar date", lrow)

        self.repeat_combo = QComboBox()
        self.repeat_combo.addItem("Yearly", "year")
        self.repeat_combo.addItem("Monthly", "month")
        self.repeat_combo.addItem("Every N days", "days")
        form.addRow("Repeat", self.repeat_combo)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 365)
        self.interval_lbl = QLabel("day(s)")
        int_row = QHBoxLayout()
        int_row.addWidget(self.interval_spin)
        int_row.addWidget(self.interval_lbl)
        form.addRow("Interval", int_row)

        self.count_spin = QSpinBox()
        self.count_spin.setRange(0, 99999)
        self.count_spin.setSpecialValueText("Unlimited")
        form.addRow("Occurrences", self.count_spin)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Note (optional)")
        form.addRow("Note", self.note_edit)

        row = QHBoxLayout()
        row.addStretch(1)
        back_btn = QPushButton("Back")
        save_btn = QPushButton("Save")
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        save_btn.clicked.connect(self._save_form)
        row.addWidget(back_btn)
        row.addWidget(save_btn)
        form.addRow(row)

        self.solar_radio.toggled.connect(self._sync_visibility)
        self.repeat_combo.currentIndexChanged.connect(self._sync_visibility)
        self._sync_visibility()
        self._stack.addWidget(page)

    def _sync_visibility(self):
        solar = self.solar_radio.isChecked()
        self.solar_date.setVisible(solar)
        self.lunar_year.setVisible(not solar)
        self.lunar_month.setVisible(not solar)
        self.lunar_day.setVisible(not solar)
        self.repeat_combo.setVisible(solar)
        rep = self.repeat_combo.currentData() if solar else "year"
        show_int = solar and rep in ("month", "days")
        self.interval_spin.setVisible(show_int)
        self.interval_lbl.setVisible(show_int)
        self.interval_lbl.setText("month(s)" if rep == "month" else "day(s)")

    def _reset_form(self, item):
        item = item or {}
        self.name_edit.setText(item.get("name", ""))
        calendar = item.get("calendar", "solar")
        if calendar == "lunar":
            self.lunar_radio.setChecked(True)
            self.lunar_year.setValue(int(item.get("year") or date.today().year))
            self.lunar_month.setValue(int(item.get("month", 1)))
            self.lunar_day.setValue(int(item.get("day", 1)))
        else:
            self.solar_radio.setChecked(True)
            try:
                d = date.fromisoformat(item.get("date", "2021-06-15"))
                self.solar_date.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                self.solar_date.setDate(QDate.currentDate())
        idx = self.repeat_combo.findData(item.get("repeat", "year"))
        if idx >= 0:
            self.repeat_combo.setCurrentIndex(idx)
        self.interval_spin.setValue(max(1, int(item.get("interval", 1) or 1)))
        self.count_spin.setValue(max(0, int(item.get("count", 0) or 0)))
        self.note_edit.setText(item.get("note", ""))
        self._sync_visibility()

    def _save_form(self):
        name = self.name_edit.text().strip()
        if not name:
            self._notify("Please enter a name")
            return
        if self.solar_radio.isChecked():
            d = self.solar_date.date()
            rep = self.repeat_combo.currentData() or "year"
            item = {
                "name": name,
                "calendar": "solar",
                "date": f"{d.year():04d}-{d.month():02d}-{d.day():02d}",
                "repeat": rep,
                "interval": self.interval_spin.value() if rep in ("month", "days") else 1,
                "count": self.count_spin.value(),
                "note": self.note_edit.text().strip(),
            }
        else:
            item = {
                "name": name,
                "calendar": "lunar",
                "year": self.lunar_year.value(),
                "month": self.lunar_month.value(),
                "day": self.lunar_day.value(),
                "repeat": "year",
                "interval": 1,
                "count": self.count_spin.value(),
                "note": self.note_edit.text().strip(),
            }
        if self._editing_id:
            self.store.update_anniversary(self._editing_id, item)
        else:
            self.store.add_anniversary(item)
        self._stack.setCurrentIndex(0)
        self._refresh_list()


# ============================================================
#  页面
# ============================================================

class AnniversaryRecordsPage:
    """纪念日记录页：背景沿用原有页面风格（渐变 + 流星场景），内容叠加其上

    独立实现，不依赖 main.py，便于被单独导入 / 测试。
    """

    name = "Anniversary"
    bg_colors = ((6, 10, 28), (14, 30, 58), (26, 52, 86))
    accent = (150, 200, 255)
    EDGE_FADE = 64.0   # 内容上下边缘渐隐高度（px）
    store_class = AnniversaryStore

    def __init__(self, config):
        self.config = config
        self.fade_in = 1.0
        self.frame = 0
        self.w = 0
        self.h = 0
        self.store = self.store_class(config)
        self.current_user = "Me"
        self.push_callback = None
        self._host = None

        self._occurrences = []
        self._records_by_key = {}
        self._current = 0
        self._fade = 1.0
        self._scroll = 0.0
        self._layout_sig = None

        # 底部内容切换器（可复用组件：竖线样式，跟随页面主色，高度紧凑）
        self._selector = BarSelector(accent=self.accent, on_change=self._jump_to,
                                     near_margin=30)
        # 右下角三个图标按钮（文本 / 上传 / 设置）
        self._actions_opacity = 0.0
        self._actions_hover = -1
        # 交互
        self._hit_rects = []
        self._mouse_pos = None
        self._sb_rect = QRectF()
        self._sb_thumb = QRectF()
        # 其他
        self._toast = ("", 0)
        self._pix_cache = {}
        self._preview_cache = {}
        self._player_dialog = None
        # 全窗预览（图片 / 文本 / 文档）
        self._preview = None
        self._preview_lines = []
        self._preview_scroll = 0.0
        self._preview_header = ""
        self._pending_preview = None
        self._preview_exit_at = -100
        self._ignore_release_until = -100
        self._preview_sb_rect = QRectF()
        self._preview_sb_thumb = QRectF()
        self._preview_sb_drag = None
        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._do_preview)
        # 页面模式（仿登录/注册切换）：timeline / text / settings / video
        self._mode = "timeline"
        self._mode_view = None
        # 音频内嵌播放（三角 + 进度条）
        self._audio_player = None
        self._audio_rec = None
        self._audio_drag = None
        self._pending_seek = None
        self._init_scene()
        self._rebuild()

    # ---------- 背景场景（与原 GalleryPage 相同的流星） ----------

    def _init_scene(self):
        self.meteors = [self._new_meteor() for _ in range(14)]

    def _new_meteor(self):
        return {
            "x": random.uniform(-100, self.w),
            "y": random.uniform(-100, self.h),
            "vx": random.uniform(5, 10),
            "vy": random.uniform(3, 7),
            "len": random.uniform(70, 150),
            "alpha": random.uniform(0.35, 0.8),
        }

    def _tick_scene(self):
        for m in self.meteors:
            m["x"] += m["vx"]
            m["y"] += m["vy"]
            if m["x"] > self.w + 160 or m["y"] > self.h + 160:
                m.update(self._new_meteor())

    def _paint_scene(self, painter, w, h):
        accent = QColor(*self.accent)
        for m in self.meteors:
            x0 = m["x"] - m["len"]
            y0 = m["y"] - m["len"] * m["vy"] / m["vx"]
            grad = QLinearGradient(x0, y0, m["x"], m["y"])
            grad.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
            grad.setColorAt(1.0, QColor(255, 255, 255, int(255 * m["alpha"])))
            pen = QPen(QBrush(grad), 2)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(x0, y0), QPointF(m["x"], m["y"]))

    # ---------- 页面接口 ----------

    def show_time(self):
        pass

    def resize(self, w, h):
        self.w = w
        self.h = h
        self._init_scene()
        self._layout_sig = None

    # ---------- 对外接口（被 main.py 调用） ----------

    def set_host(self, host):
        self._host = host

    def set_current_user(self, name: str):
        self.current_user = name or self.current_user

    def set_push_callback(self, cb):
        self.push_callback = cb

    def refresh(self):
        """同步完成后打开工作区并重新读取数据（保持当前所在纪念日）"""
        old_key = self._current_key()
        self.store.load()
        self.store.open_workspace()   # 解压到临时目录，作为本次会话的工作区
        self._rebuild()
        if old_key:
            for i, o in enumerate(self._occurrences):
                if o["key"] == old_key:
                    self._current = i
                    break
        self._selector.set_current(self._current)

    # ---------- 事件（由 main.py 路由进来） ----------

    def on_wheel(self, dx: int, dy: int, pos) -> bool:
        if self._mode != "timeline":
            return True  # 模式视图中滚轮交给视图内控件
        if self._preview is not None:
            # 全窗预览中：滚轮滚动文本/文档，单击退出
            if self._preview.get("kind") == "text" and dy:
                self._preview_scroll -= dy / 120.0 * 90.0
                self._clamp_preview_scroll()
            return True
        if not self._occurrences:
            return False
        if dx:
            # 横向滚轮 / 触控板横滑 → 滚动时间线
            self._scroll -= dx / 120.0 * 70.0
            self._clamp_scroll()
            return True
        # 仅底部内容控制激活（鼠标靠近）时，滚轮切换纪念日
        on_actions = any(r.contains(pos) for r in self._action_rects())
        if not on_actions and self._selector.on_wheel(dy, pos):
            return True
        if self._sb_rect.isValid() and self._sb_rect.contains(pos):
            self._scroll -= dy / 120.0 * 70.0
            self._clamp_scroll()
            return True
        if dy:
            # 平时滚轮 → 上下滚动内容
            self._scroll -= dy / 120.0 * 70.0
            self._clamp_scroll()
            return True
        return False

    def on_press(self, pos, button) -> bool:
        if button != Qt.LeftButton:
            return False
        if self._mode != "timeline":
            return True
        if self._preview is not None:
            # 预览中：文本/文档滚动条可拖动；其余点击由 release 处理（退出）
            if (self._preview.get("kind") == "text"
                    and self._preview_sb_rect.isValid()
                    and self._preview_sb_rect.contains(pos)):
                self._preview_sb_drag = {"last": pos.y()}
                if not self._preview_sb_thumb.contains(pos):
                    max_scroll = self._clamp_preview_scroll()
                    if max_scroll > 0:
                        ratio = ((pos.y() - self._preview_sb_rect.top())
                                 / max(1.0, self._preview_sb_rect.height()))
                        self._preview_scroll = ratio * max_scroll
            return True
        if not self._occurrences:
            return False
        if self._selector.on_press(pos):
            return True
        # 音频进度条：按下开始拖动跳转
        for rect, action, rec in self._hit_rects:
            if action == "seek" and rect.translated(0, -self._scroll).contains(pos):
                self._audio_drag = {"rec": rec}
                self._mute_audio(True)   # 拖动跳转时静音，避免杂音
                self._seek_audio(rec, pos.x())
                return True
        return False

    def on_move(self, pos, buttons) -> bool:
        if self._preview_sb_drag is not None and (buttons & Qt.LeftButton):
            dy = pos.y() - self._preview_sb_drag["last"]
            self._preview_sb_drag["last"] = pos.y()
            self._preview_scroll -= dy
            self._clamp_preview_scroll()
            return True
        if self._preview is not None:
            return True
        if self._selector.on_move(pos, buttons):
            return True
        if self._audio_drag is not None and (buttons & Qt.LeftButton):
            self._seek_audio(self._audio_drag["rec"], pos.x())
            return True
        return False

    def on_release(self, pos, button) -> bool:
        if button != Qt.LeftButton:
            return False
        if self._mode != "timeline":
            # 模式视图中点击交给子控件（返回按钮 / 表单）
            return True
        if self._preview_sb_drag is not None:
            self._preview_sb_drag = None
            return True
        if self._audio_drag is not None:
            self._audio_drag = None
            self._mute_audio(False)
            return True
        if self._preview is not None:
            # 单击退出全窗预览
            self._preview = None
            self._preview_lines = []
            self._preview_exit_at = self.frame
            self._cancel_pending_preview()
            return True
        if self.frame < self._ignore_release_until:
            # 双击序列的第二次按下释放，忽略，避免误触发
            return True
        # 右下角三个图标按钮（即使没有纪念日，“设置纪念日”也应可用）
        if self._actions_opacity > 0.2:
            for i, r in enumerate(self._action_rects()):
                if r.contains(pos):
                    if i == 0:
                        self._send_text()
                    elif i == 1:
                        self._upload_files()
                    else:
                        self._open_settings()
                    return True
        if not self._occurrences:
            return False
        # 底部竖线切换器（点击 / 箭头）
        if self._selector.on_release(pos):
            return True
        # 音频进度条：单击跳转（优先于卡片动作）
        for rect, action, rec in self._hit_rects:
            if action == "seek" and rect.translated(0, -self._scroll).contains(pos):
                self._seek_audio(rec, pos.x())
                return True
        # 记录卡片：播放 / 打开
        for rect, action, rec in self._hit_rects:
            if action != "seek" and rect.translated(0, -self._scroll).contains(pos):
                if action == "preview":
                    # 单击 → 稍等片刻进入全窗预览（避免误触发双击）
                    self._pending_preview = (rect, action, rec)
                    self._preview_timer.start(240)
                elif action == "audio":
                    self._toggle_audio(rec)
                else:
                    self._open_external(rec)
                return True
        return False

    def on_double_click(self, pos, button) -> bool:
        if button != Qt.LeftButton:
            return False
        self._cancel_pending_preview()
        if (self._preview is not None
                or self.frame - self._preview_exit_at < 30):
            # 预览中 / 刚退出预览：双击不触发打开
            self._ignore_release_until = self.frame + 25
            return True
        if not self._occurrences:
            return False
        for rect, action, rec in self._hit_rects:
            if rect.translated(0, -self._scroll).contains(pos):
                # 双击内容块 → 默认程序打开
                self._ignore_release_until = self.frame + 25
                self._open_external(rec)
                return True
        return False

    def on_key(self, key) -> bool:
        if self._mode != "timeline":
            if key == Qt.Key_Escape:
                self._back_to_timeline()
                return True
            return False  # 其它按键交给模式视图内的焦点控件
        if self._preview is not None:
            if key == Qt.Key_Escape:
                self._preview = None
                self._preview_lines = []
            return True
        if not self._occurrences:
            return False
        if key in (Qt.Key_Left,):
            self._step_occurrence(-1)
            return True
        if key in (Qt.Key_Right,):
            self._step_occurrence(1)
            return True
        if key in (Qt.Key_Up, Qt.Key_Down):
            self._scroll += (-70 if key == Qt.Key_Up else 70)
            self._clamp_scroll()
            return True
        return False

    # ---------- 数据构建 ----------

    def _rebuild(self):
        self._occurrences = self._build_occurrences()
        self._records_by_key = {}
        for r in self.store.records:
            key = f"{r.get('anniversary_id', '')}:{r.get('date', '')}"
            self._records_by_key.setdefault(key, []).append(r)
        self._current = self._default_index()
        self._selector.set_items(
            [{"key": o["key"], "label": self._selector_label(o)}
             for o in self._occurrences],
            self._current)
        self._scroll = 0.0
        self._layout_sig = None
        self._pix_cache.clear()

    def _selector_label(self, o) -> str:
        """Hover label: date + name + days info"""
        try:
            diff = (date.fromisoformat(o["date"]) - date.today()).days
        except Exception:
            diff = 0
        if diff == 0:
            extra = "Today"
        elif diff > 0:
            extra = f"In {diff} days"
        else:
            extra = f"{-diff} days ago"
        return f"{o['date'][5:]} {o['name']} · {extra}"

    def _build_occurrences(self) -> list:
        """生成所有纪念日条目：支持 每年 / 每月 / 每 N 天，从起始日算起"""
        today = date.today()
        max_future = today + timedelta(days=365 * 2)
        out = []
        for a in self.store.anniversaries:
            out.extend(self._occurrences_for(a, today, max_future))
        out.sort(key=lambda o: o["date"])
        # 同一纪念日同一天只保留一个
        seen = set()
        uniq = []
        for o in out:
            if o["key"] not in seen:
                seen.add(o["key"])
                uniq.append(o)
        return uniq

    def _mk_occ(self, aid, name, sd, calendar_name, lunar_text):
        return {
            "key": f"{aid}:{sd.isoformat()}",
            "anniversary_id": aid,
            "date": sd.isoformat(),
            "name": name,
            "calendar": calendar_name,
            "lunar": lunar_text,
        }

    def _occurrences_for(self, a, today, max_future) -> list:
        aid = a.get("id", "")
        name = a.get("name") or "Anniversary"
        limit = max(0, int(a.get("count") or 0))  # 生效次数，0 = 不限
        out = []
        if a.get("calendar") == "lunar":
            m = int(a.get("month", 1))
            d = int(a.get("day", 1))
            y0 = max(1900, int(a.get("year") or today.year))
            for yy in range(y0, today.year + 3):
                try:
                    # 若该年恰好把此月设为闰月，则按闰月日过（与阴历生日习惯一致）
                    if _leap_month(yy) == m:
                        sd = lunar_to_solar(yy, m, d, True)
                    else:
                        sd = lunar_to_solar(yy, m, d, False)
                except Exception:
                    continue
                out.append(self._mk_occ(aid, name, sd, "lunar",
                                        lunar_month_day_text(m, d)))
                if limit and len(out) >= limit:
                    break
            self._add_record_dates(out, aid, name)
            return out

        try:
            start = date.fromisoformat(a.get("date", ""))
        except Exception:
            return []
        rep = a.get("repeat", "year") or "year"
        interval = max(1, int(a.get("interval", 1) or 1))
        # 短周期（每月 / 每 N 天）只看最近一年 + 未来两年，避免条目爆炸
        window_start = today - timedelta(days=365)
        if rep == "days":
            k = 0
            count = 0
            while count < (limit if limit else 800):
                sd = start + timedelta(days=k * interval)
                if sd > max_future:
                    break
                if limit or sd >= window_start:
                    out.append(self._mk_occ(aid, name, sd, "solar", ""))
                    count += 1
                k += 1
        elif rep == "month":
            k = 0
            count = 0
            while count < (limit if limit else 600):
                sd = _add_months(start, k * interval)
                if sd > max_future:
                    break
                if limit or sd >= window_start:
                    out.append(self._mk_occ(aid, name, sd, "solar", ""))
                    count += 1
                k += 1
        else:
            # 每年：起始日期的月日（2/29 平年顺延到下一天）
            y_end = start.year + limit if limit else today.year + 3
            for yy in range(start.year, y_end):
                try:
                    sd = date(yy, start.month, start.day)
                except ValueError:
                    sd = date(yy, 3, 1)
                out.append(self._mk_occ(aid, name, sd, "solar", ""))
        self._add_record_dates(out, aid, name)
        return out

    def _add_record_dates(self, out, aid, name):
        """保证已经上传过记录的纪念日一定出现在列表里（无论周期长短）"""
        existing = {o["date"] for o in out}
        for r in self.store.records:
            if r.get("anniversary_id") != aid:
                continue
            rd = str(r.get("date", ""))
            if rd and rd not in existing:
                try:
                    sd = date.fromisoformat(rd)
                except Exception:
                    continue
                out.append(self._mk_occ(aid, name, sd, "solar", ""))
                existing.add(rd)

    def _default_index(self) -> int:
        today = date.today().isoformat()
        idx = 0
        for i, o in enumerate(self._occurrences):
            if o["date"] <= today:
                idx = i
            else:
                break
        return idx

    def _current_key(self):
        if 0 <= self._current < len(self._occurrences):
            return self._occurrences[self._current]["key"]
        return None

    def _current_occurrence(self):
        if not self._occurrences:
            return None
        return self._occurrences[min(self._current, len(self._occurrences) - 1)]

    def _records_for(self, occ) -> list:
        recs = list(self._records_by_key.get(occ["key"], []))
        recs.sort(key=lambda r: r.get("time", ""))
        return recs

    def _step_occurrence(self, delta):
        if not self._occurrences:
            return
        n = len(self._occurrences)
        self._jump_to((self._current + delta) % n)

    def _jump_to(self, idx):
        n = len(self._occurrences)
        idx = max(0, min(n - 1, idx))
        if idx == self._current:
            return
        self._cancel_pending_preview()
        self._stop_audio()
        self._current = idx
        self._selector.set_current(idx)
        self._scroll = 0.0
        self._fade = 0.35
        self._layout_sig = None

    def _clamp_scroll(self):
        max_scroll = self._max_scroll()
        self._scroll = max(0.0, min(max_scroll, self._scroll))

    def _is_upload_open(self, occ) -> bool:
        try:
            return abs((date.today() - date.fromisoformat(occ["date"])).days) <= 3
        except Exception:
            return False

    # ---------- 主绘制 ----------

    def paint(self, painter: QPainter, w, h):
        self.w = w
        self.h = h
        # 背景（沿用 ScenePage/GalleryPage 的渐变 + 流星场景，不做修改）
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(*self.bg_colors[0]))
        bg.setColorAt(0.5, QColor(*self.bg_colors[1]))
        bg.setColorAt(1.0, QColor(*self.bg_colors[2]))
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(0, 0, w, h), 20, 20)
        self._paint_scene(painter, w, h)

        # 模式切换（放送文本 / 设置 / 视频）：背景不变，内容由 ModeView 子控件显示
        if self._mode != "timeline":
            return

        # 全窗预览：图片用黑灰全屏覆盖；文本/文档直接在页面上预览
        if self._preview is not None:
            if self._preview.get("kind") == "text":
                self._paint_text_preview(painter, w, h)
            else:
                self._paint_preview(painter, w, h)
            return

        if not self._occurrences:
            self._paint_empty(painter, w, h)
            self._paint_bottom_actions(painter, w, h)
            self._paint_toast(painter, w, h)
            return

        self._ensure_layout(w, h)
        self._paint_title(painter, w, h)
        self._paint_timeline(painter, w, h)
        # 底部竖线切换器（上层、更紧凑；三个操作按钮在下方一层）
        strip_w = min(1300, w - 160)
        self._selector.set_rect(QRectF((w - strip_w) / 2, h - 120, strip_w, 40))
        self._selector.paint(painter)
        self._paint_bottom_actions(painter, w, h)
        self._paint_toast(painter, w, h)

    # ---------- 布局 ----------

    def _geo(self):
        w, h = self.w, self.h
        # 布局：左右各留 1/8；上下为标题区 / 内容区 / 两层控件区
        x0 = int(w * 0.125)
        x1 = int(w * 0.875)
        # 上下边距相等（对称）：标题在顶边距内，选择器 + 按钮在底边距内
        top = int(h * 0.17)
        bottom = int(h * 0.83)
        line_x = x0 + 24
        card_x = line_x + 46
        card_w = x1 - card_x - 16
        return {
            "line_x": line_x,
            "card_x": card_x,
            "card_w": max(card_w, 320),
            "x0": x0,
            "x1": x1,
            "top": top,
            "bottom": bottom,
        }

    def _ensure_layout(self, w, h):
        occ = self._current_occurrence()
        recs = self._records_for(occ)
        sig = (w, h, len(recs), self._current)
        if sig == self._layout_sig:
            return
        self._layout_sig = sig
        self._hit_rects = []
        g = self._geo()
        content = QRectF(g["x0"], g["top"], g["x1"] - g["x0"], g["bottom"] - g["top"])
        self._content_rect = content

        # 逐条测量卡片高度（文本换行只在数据变化时计算一次，避免每帧重复）
        cards = []
        total = 0.0
        body_fm = QFontMetrics(QFont("Microsoft YaHei", 10))
        body_w = g["card_w"] - 42
        for r in recs:
            body_h, meta = self._measure_body(r, g["card_w"] - 28)
            card_h = 46 + body_h
            lines = None
            if meta == "text":
                lines = _wrap_text(r.get("text", ""), body_fm, body_w)
            elif meta == "doc":
                preview = self._preview_for(r)
                lines = _wrap_text(preview, body_fm, body_w) if preview else []
            cards.append((r, body_h, meta, lines))
            total += card_h + 12
        # “桥上的火车”：中间为完整展示区，两端渐隐；滚动时首尾都能完全显示
        self._max_scroll_val = max(
            0.0, total - (content.height() - 2 * self.EDGE_FADE - 24))
        self._scroll = max(0.0, min(self._max_scroll_val, self._scroll))
        self._total_content_h = total

        # 卡片位置以“未滚动”为基准，绘制/命中时再按 _scroll 平移
        self._cards_data = []
        self._hit_rects = []
        y = content.top() + self.EDGE_FADE + 12
        for r, body_h, meta, lines in cards:
            card_h = 46 + body_h
            rect = QRectF(g["card_x"], y, g["card_w"], card_h)
            self._cards_data.append((r, rect, body_h, meta, lines))
            y += card_h + 12
            # 命中区：图片/文本/文档 → 单击预览、双击打开；音频 → 内嵌播放；
            # 视频 → 播放器预览；其余 → 直接打开
            if meta in ("image", "text", "doc"):
                action = "preview"
            elif meta == "audio":
                action = "audio"
            else:
                action = "open"
            self._hit_rects.append((rect, action, r))
            if meta == "audio":
                # 进度条子区域（按实际绘制的 body 位置计算）：单击/拖动可跳转
                body_rect = QRectF(rect.left() + 14, rect.top() + 30,
                                   rect.width() - 28, body_h)
                _tri, bar, _t = self._audio_layout(body_rect)
                self._hit_rects.append((bar.adjusted(-4, -6, 4, 6), "seek", r))

        # 滚动条
        self._sb_rect = QRectF()
        if self._max_scroll_val > 0:
            # 位置固定（细条，离内容区右侧有一点距离）；滑块位置每帧实时计算
            sb_x = content.right() + 14
            self._sb_rect = QRectF(sb_x - 2, content.top() + 4, 5, content.height() - 8)

    def _max_scroll(self) -> float:
        return getattr(self, "_max_scroll_val", 0.0)

    def _measure_body(self, rec, width) -> tuple:
        kind = rec.get("kind", "text")
        fm = QFontMetrics(QFont("Microsoft YaHei", 10))
        line_h = fm.height() + 3
        if kind == "image":
            pix = self._load_pix(rec)
            if pix is None:
                return 64, "image"
            max_h = int(self.h * 0.26)
            return min(max_h, int(pix.height() * width / max(1, pix.width()))), "image"
        if kind == "audio" or kind == "video":
            return 54, kind
        if kind == "text":
            text = rec.get("text", "")
            lines = _wrap_text(text, fm, width)
            return min(12, len(lines)) * line_h + 6, "text"
        if kind == "document":
            preview = self._preview_for(rec)
            if preview:
                lines = _wrap_text(preview, fm, width)
                return min(8, len(lines)) * line_h + 28, "doc"
            return 46, "doc"
        return 40, "file"

    # ---------- 绘制：标题（中上，名称 + 日期/状态） ----------

    def _paint_title(self, painter, w, h):
        occ = self._current_occurrence()
        if occ is None:
            return
        g = self._geo()
        top = g["top"]
        painter.setOpacity(self._fade)

        # 第一行：纪念日名称
        name_font = QFont("Microsoft YaHei", 26, QFont.Bold)
        painter.setFont(name_font)
        painter.setPen(QColor(255, 240, 246, 245))
        painter.drawText(QRectF(0, top - 104, w, 52), Qt.AlignCenter, occ["name"])

        # 第二行小字：日期信息 + 状态（过去 / 今天 / 未来）
        try:
            d = date.fromisoformat(occ["date"])
            diff = (d - date.today()).days
            wd = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[d.weekday()]
        except Exception:
            diff, wd = 0, "?"
        if diff == 0:
            status, status_col = "Today", QColor(255, 215, 130)
        elif diff > 0:
            status, status_col = f"In {diff} days", QColor(150, 200, 255)
        else:
            years, days = divmod(-diff, 365)
            status = (f"{years}y {days}d ago" if years else f"{days} days ago")
            status_col = QColor(190, 200, 220)
        sub_font = QFont("Microsoft YaHei", 12)
        painter.setFont(sub_font)
        fm = QFontMetrics(sub_font)
        base = f"{occ['date']}  {wd}"
        total_w = fm.horizontalAdvance(base) + 22 + fm.horizontalAdvance(status)
        x0 = (w - total_w) / 2
        painter.setPen(QColor(205, 200, 220, 230))
        painter.drawText(QRectF(x0, top - 50, fm.horizontalAdvance(base) + 8, 30),
                         Qt.AlignLeft | Qt.AlignVCenter, base)
        painter.setPen(status_col)
        painter.drawText(QRectF(x0 + fm.horizontalAdvance(base) + 18, top - 50,
                                fm.horizontalAdvance(status) + 8, 30),
                         Qt.AlignLeft | Qt.AlignVCenter, status)
        painter.setOpacity(1.0)

    # ---------- 绘制：时间线（无面板，上下边缘渐隐遮罩） ----------

    def _paint_timeline(self, painter, w, h):
        if not hasattr(self, "_content_rect"):
            return
        occ = self._current_occurrence()
        recs = self._records_for(occ)
        g = self._geo()
        content = self._content_rect
        line_x = g["line_x"]

        painter.save()
        painter.setOpacity(self._fade)

        if not recs:
            painter.setFont(QFont("Microsoft YaHei", 13))
            painter.setPen(QColor(210, 200, 225, 220))
            painter.drawText(content.adjusted(20, 30, -20, -30), Qt.AlignCenter,
                             "No records for this day\nWithin 3 days of the anniversary, "
                             "send text or upload files from the bottom-right")
            painter.restore()
            return

        painter.setClipRect(content)
        # 竖线：整条实线（上下渐隐由遮罩统一完成）
        pen = QPen(QColor(150, 200, 255, 215), 2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(line_x, content.top()), QPointF(line_x, content.bottom()))

        card_font = QFont("Microsoft YaHei", 10)
        head_font = QFont("Microsoft YaHei", 9)
        for r, base_rect, body_h, meta, lines in self._cards_data:
            rect = base_rect.translated(0, -self._scroll)
            # 圆点 + 横线（与卡片一起随滚动移动，顶部与竖线同步渐隐）
            dot_y = rect.top() + 20
            painter.setBrush(QBrush(QColor(150, 200, 255)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(line_x, dot_y), 5, 5)
            painter.setPen(QPen(QColor(150, 200, 255, 190), 2))
            painter.drawLine(QPointF(line_x + 5, dot_y), QPointF(rect.left() - 8, dot_y))

            # 卡片：无边框，更透明、偏蓝
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(38, 48, 104, 150)))
            painter.drawRoundedRect(rect, 12, 12)

            # 表头：用户 + 时间 / 类型
            painter.setFont(head_font)
            painter.setPen(QColor(180, 218, 255, 235))
            kind_cn = {"text": "Text", "image": "Image", "audio": "Music",
                       "video": "Video", "document": "Document", "file": "File"
                       }.get(r.get("kind"), "Record")
            painter.drawText(QRectF(rect.left() + 14, rect.top() + 7, rect.width() - 130, 18),
                             Qt.AlignLeft | Qt.AlignVCenter,
                             f"{r.get('user', '')}  ·  {r.get('time', '')}")
            painter.setPen(QColor(205, 180, 215, 200))
            painter.drawText(QRectF(rect.right() - 110, rect.top() + 7, 96, 18),
                             Qt.AlignRight | Qt.AlignVCenter, kind_cn)

            body_rect = QRectF(rect.left() + 14, rect.top() + 30, rect.width() - 28, body_h)
            self._draw_card_body(painter, r, body_rect, meta, card_font, lines)

            # 底部提示
            if meta not in ("text",):
                painter.setFont(head_font)
                painter.setPen(QColor(170, 160, 190, 200))
                if meta == "audio":
                    hint = "Click to play · Double-click to open"
                elif meta in ("doc", "image"):
                    hint = "Click to preview · Double-click to open"
                else:
                    hint = "Click to open"
                painter.drawText(QRectF(rect.left() + 14, rect.bottom() - 21, rect.width() - 28, 16),
                                 Qt.AlignRight | Qt.AlignVCenter, hint)
        painter.restore()
        # 上下边缘渐隐遮罩（画在最上层，滚动后内容到中间即完全可见）
        self._paint_edge_fade(painter, content)
        self._draw_scrollbar(painter, content)

    def _paint_edge_fade(self, painter, content):
        """内容区上下两侧逐渐隐入背景（遮罩方式，不改变内容本身透明度）"""
        fade = self.EDGE_FADE
        top_col = self._bg_color_at(content.top())
        bot_col = self._bg_color_at(content.bottom())
        painter.save()
        painter.setClipRect(content)
        g1 = QLinearGradient(0, content.top(), 0, content.top() + fade)
        g1.setColorAt(0.0, QColor(top_col[0], top_col[1], top_col[2], 235))
        g1.setColorAt(1.0, QColor(top_col[0], top_col[1], top_col[2], 0))
        painter.fillRect(QRectF(content.left(), content.top(), content.width(), fade), QBrush(g1))
        g2 = QLinearGradient(0, content.bottom() - fade, 0, content.bottom())
        g2.setColorAt(0.0, QColor(bot_col[0], bot_col[1], bot_col[2], 0))
        g2.setColorAt(1.0, QColor(bot_col[0], bot_col[1], bot_col[2], 235))
        painter.fillRect(QRectF(content.left(), content.bottom() - fade, content.width(), fade), QBrush(g2))
        painter.restore()

    def _bg_color_at(self, y) -> tuple:
        """页面渐变背景在 y 处的颜色（用于边缘遮罩，隐入背景不穿帮）"""
        h = max(1, self.h)
        t = min(1.0, max(0.0, y / h))
        c0, c1, c2 = self.bg_colors
        if t <= 0.5:
            a, b, tt = c0, c1, t / 0.5
        else:
            a, b, tt = c1, c2, (t - 0.5) / 0.5
        return tuple(int(a[i] + (b[i] - a[i]) * tt) for i in range(3))

    def _draw_scrollbar(self, painter, content):
        if not self._sb_rect.isValid():
            return
        # 滑块位置实时跟随 _scroll（只展示当前位置，不绑定拖动）
        sb = self._sb_rect
        total = getattr(self, "_total_content_h", 1.0) or 1.0
        th_h = max(24.0, sb.height() * (content.height() / total))
        if self._max_scroll_val > 0:
            ratio = self._scroll / self._max_scroll_val
        else:
            ratio = 0.0
        th_y = sb.top() + ratio * (sb.height() - th_h)
        thumb = QRectF(sb.left(), th_y, sb.width(), th_h)
        # 只画滑块（无槽），滑块上下两端渐隐
        grad = QLinearGradient(0, thumb.top(), 0, thumb.bottom())
        grad.setColorAt(0.0, QColor(150, 200, 255, 0))
        grad.setColorAt(0.3, QColor(150, 200, 255, 210))
        grad.setColorAt(0.7, QColor(150, 200, 255, 210))
        grad.setColorAt(1.0, QColor(150, 200, 255, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawRoundedRect(thumb, 2, 2)

    def _audio_layout(self, rect):
        """音频卡片内部布局：三角、进度条、时间（绘制与命中共用）"""
        tri = QRectF(rect.left(), rect.top() + 4, 26, 28)
        time_rect = QRectF(rect.right() - 104, rect.top() + 8, 92, 18)
        bar = QRectF(tri.right() + 10, rect.top() + 16,
                     time_rect.left() - tri.right() - 18, 6)
        return tri, bar, time_rect

    def _draw_card_body(self, painter, rec, rect, meta, font, lines=None):
        painter.save()
        painter.setFont(font)
        fm = QFontMetrics(font)
        if meta == "image":
            pix = self._load_pix(rec, rect.width(), rect.height())
            if pix is not None:
                x = rect.left() + (rect.width() - pix.width()) / 2
                y = rect.top() + (rect.height() - pix.height()) / 2
                painter.drawPixmap(QPointF(x, y), pix)
            else:
                painter.setPen(QColor(200, 190, 215))
                painter.drawText(rect, Qt.AlignCenter,
                                 "Image preview unavailable, click to open")
        elif meta == "text":
            y = rect.top()
            for ln in (lines or [])[:12]:
                painter.setPen(QColor(240, 234, 246))
                painter.drawText(QRectF(rect.left(), y, rect.width(), fm.height()),
                                 Qt.AlignLeft | Qt.AlignTop, ln)
                y += fm.height() + 3
            if len(lines or []) > 12:
                painter.setPen(QColor(150, 200, 255))
                painter.drawText(QRectF(rect.left(), y, rect.width(), fm.height()),
                                 Qt.AlignLeft | Qt.AlignTop,
                                 "… Click to view full text")
        elif meta == "doc":
            # 文件名
            painter.setPen(QColor(190, 222, 255))
            painter.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
            name = rec.get("file_name") or rec.get("file", "")
            name = name[:42] + ("…" if len(name) > 42 else "")
            painter.drawText(QRectF(rect.left(), rect.top(), rect.width(), 20),
                             Qt.AlignLeft | Qt.AlignVCenter, f"Document: {name}")
            painter.setFont(font)
            preview = self._preview_for(rec)
            if preview:
                y = rect.top() + 24
                for ln in (lines or [])[:8]:
                    painter.setPen(QColor(228, 222, 238, 230))
                    painter.drawText(QRectF(rect.left(), y, rect.width(), fm.height()),
                                     Qt.AlignLeft | Qt.AlignTop, ln)
                    y += fm.height() + 3
                if len(lines or []) > 8:
                    painter.setPen(QColor(150, 200, 255))
                    painter.drawText(QRectF(rect.left(), y, rect.width(), fm.height()),
                                     Qt.AlignLeft | Qt.AlignTop,
                                     "… Click to open full content")
            else:
                painter.setPen(QColor(205, 195, 220))
                painter.drawText(QRectF(rect.left(), rect.top() + 24, rect.width(), 20),
                                 Qt.AlignLeft | Qt.AlignVCenter,
                                 "(Inline preview not supported, click to open)")
        elif meta == "audio":
            # 音频：三角播放/暂停 + 进度条，直接内嵌预览
            playing = (self._audio_rec == rec.get("id")
                       and self._audio_player is not None
                       and self._audio_player.state() == QMediaPlayer.PlayingState)
            tri, bar, time_rect = self._audio_layout(rect)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(150, 200, 255, 235)))
            if playing:
                painter.drawRect(QRectF(tri.left() + 7, tri.top() + 8, 4, 16))
                painter.drawRect(QRectF(tri.left() + 16, tri.top() + 8, 4, 16))
            else:
                path = QPainterPath()
                path.moveTo(tri.left() + 8, tri.top() + 5)
                path.lineTo(tri.left() + 8, tri.bottom() - 5)
                path.lineTo(tri.right() - 3, tri.center().y())
                path.closeSubpath()
                painter.drawPath(path)
            # 进度条
            painter.setBrush(QBrush(QColor(70, 55, 100, 190)))
            painter.drawRoundedRect(bar, 3, 3)
            ratio = 0.0
            dur = pos = 0
            if self._audio_rec == rec.get("id") and self._audio_player is not None:
                dur = self._audio_player.duration()
                pos = self._audio_player.position()
                if dur > 0:
                    ratio = max(0.0, min(1.0, pos / dur))
            if ratio > 0:
                fill = QRectF(bar.left(), bar.top(), bar.width() * ratio, bar.height())
                painter.setBrush(QBrush(QColor(150, 200, 255, 230)))
                painter.drawRoundedRect(fill, 3, 3)
                # 小圆点（可拖动滑块）
                knob_x = fill.right()
                painter.setBrush(QBrush(QColor(235, 246, 255)))
                painter.setPen(QPen(QColor(150, 200, 255, 235), 1.5))
                painter.drawEllipse(QPointF(knob_x, bar.center().y()), 5, 5)
                painter.setPen(Qt.NoPen)
            elif self._audio_rec == rec.get("id") and self._audio_player is not None:
                # 已加载但未播放：在起点画一个小圆点
                painter.setBrush(QBrush(QColor(235, 246, 255, 220)))
                painter.setPen(QPen(QColor(150, 200, 255, 200), 1.5))
                painter.drawEllipse(QPointF(bar.left(), bar.center().y()), 5, 5)
                painter.setPen(Qt.NoPen)
            # 时间（固定在内容框内，不会溢出）
            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.setPen(QColor(200, 210, 228))
            painter.drawText(time_rect, Qt.AlignRight | Qt.AlignVCenter,
                             f"{_fmt_ms(pos)} / {_fmt_ms(dur)}")
            # 文件名
            painter.setFont(font)
            painter.setPen(QColor(235, 228, 242))
            name = rec.get("file_name") or rec.get("file", "")
            name = name[:40] + ("…" if len(name) > 40 else "")
            painter.drawText(QRectF(rect.left() + 2, rect.top() + 34, rect.width() - 24, 20),
                             Qt.AlignLeft | Qt.AlignVCenter, name)
        elif meta == "video":
            play_rect = QRectF(rect.left(), rect.top() + 6, 64, 30)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(150, 200, 255, 230)))
            painter.drawRoundedRect(play_rect, 8, 8)
            painter.setPen(QColor(40, 12, 40))
            painter.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
            painter.drawText(play_rect, Qt.AlignCenter, "Open")
            painter.setFont(font)
            painter.setPen(QColor(235, 228, 242))
            name = rec.get("file_name") or rec.get("file", "")
            name = name[:40] + ("…" if len(name) > 40 else "")
            painter.drawText(QRectF(play_rect.right() + 12, rect.top(), rect.width() - 88, 40),
                             Qt.AlignLeft | Qt.AlignVCenter, name)
        else:
            painter.setPen(QColor(235, 228, 242))
            name = rec.get("file_name") or rec.get("file", "")
            name = name[:46] + ("…" if len(name) > 46 else "")
            painter.drawText(QRectF(rect.left(), rect.top(), rect.width(), 22),
                             Qt.AlignLeft | Qt.AlignVCenter, f"File: {name}")
            painter.setPen(QColor(190, 180, 210))
            painter.drawText(QRectF(rect.left(), rect.top() + 22, rect.width(), 18),
                             Qt.AlignLeft | Qt.AlignVCenter, "Click to open")
        painter.restore()

    # ---------- 绘制：右下角三个图标按钮 ----------

    ACTION_LABELS = ("Send Text", "Upload Files", "Set Anniversaries")

    def _action_rects(self):
        """三个按钮（最下方一层）：文本（左）、上传（中）、设置（右）"""
        s = 40
        gap = 10
        right = self.w - 16
        y = self.h - 56
        r3 = QRectF(right - s, y, s, s)                 # 设置
        r2 = QRectF(right - s * 2 - gap, y, s, s)       # 上传
        r1 = QRectF(right - s * 3 - gap * 2, y, s, s)   # 文本
        return [r1, r2, r3]

    def _paint_bottom_actions(self, painter, w, h):
        if self._actions_opacity <= 0.03:
            return
        alpha = int(255 * self._actions_opacity)
        for i, r in enumerate(self._action_rects()):
            hover = (i == self._actions_hover)
            # 无背景无边框，仅图标；悬停时更亮、变大
            self._draw_action_icon(
                painter, r, i,
                min(255, int(alpha * 1.25)) if hover else alpha,
                1.18 if hover else 1.0)

    def _draw_action_icon(self, painter, r, kind, alpha, scale=1.0):
        s = scale
        pen = QPen(QColor(255, 240, 245, alpha), max(1.5, 2 * s))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        cx, cy = r.center().x(), r.center().y()
        if kind == 0:
            # 文本输入：气泡 + 三个点
            painter.drawRoundedRect(
                QRectF(cx - 11 * s, cy - 9 * s, 22 * s, 16 * s), 6 * s, 6 * s)
            tail = QPainterPath()
            tail.moveTo(cx - 5 * s, cy + 7 * s)
            tail.lineTo(cx - 10 * s, cy + 12 * s)
            tail.lineTo(cx + 1 * s, cy + 7 * s)
            painter.drawPath(tail)
            painter.setBrush(QBrush(QColor(255, 240, 245, alpha)))
            for dx in (-5 * s, 0, 5 * s):
                painter.drawEllipse(QPointF(cx + dx, cy - 1 * s), 1.6 * s, 1.6 * s)
            painter.setBrush(Qt.NoBrush)
        elif kind == 1:
            # 上传文件：向上箭头 + 托盘
            painter.drawLine(QPointF(cx, cy + 7 * s), QPointF(cx, cy - 7 * s))
            painter.drawLine(QPointF(cx - 5 * s, cy - 2 * s), QPointF(cx, cy - 7 * s))
            painter.drawLine(QPointF(cx + 5 * s, cy - 2 * s), QPointF(cx, cy - 7 * s))
            painter.drawLine(QPointF(cx - 10 * s, cy + 7 * s),
                             QPointF(cx + 10 * s, cy + 7 * s))
        else:
            # 设置纪念日：三条调节滑杆
            for dy, kx in ((-7 * s, -4 * s), (0, 4 * s), (7 * s, -4 * s)):
                painter.drawLine(QPointF(cx - 9 * s, cy + dy),
                                 QPointF(cx + 9 * s, cy + dy))
                painter.setBrush(QBrush(QColor(255, 240, 245, alpha)))
                painter.drawEllipse(QPointF(cx + kx, cy + dy), 3 * s, 3 * s)
                painter.setBrush(Qt.NoBrush)

    # ---------- 绘制：空状态 / Toast ----------

    def _paint_empty(self, painter, w, h):
        painter.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        painter.setPen(QColor(255, 226, 238, 230))
        painter.drawText(QRectF(0, h * 0.34, w, 40), Qt.AlignCenter,
                         "No anniversaries yet")
        painter.setFont(QFont("Microsoft YaHei", 12))
        painter.setPen(QColor(200, 190, 220, 210))
        painter.drawText(QRectF(0, h * 0.34 + 44, w, 30), Qt.AlignCenter,
                         "Bottom-right buttons: Send Text · Upload Files · "
                         "Set Anniversaries (Solar / Lunar)")

    def _show_toast(self, text: str, frames: int = 180):
        self._toast = (text, self.frame + frames)

    def _paint_toast(self, painter, w, h):
        text, until = self._toast
        if not text:
            return
        remain = until - self.frame
        if remain <= 0:
            self._toast = ("", 0)
            return
        alpha = min(1.0, remain / 40.0)
        font = QFont("Microsoft YaHei", 11)
        painter.setFont(font)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(text) + 36
        rect = QRectF((w - tw) / 2, 14, tw, 34)
        painter.setOpacity(alpha)
        painter.setPen(QPen(QColor(150, 200, 255, 100), 1))
        painter.setBrush(QBrush(QColor(10, 7, 26, 230)))
        painter.drawRoundedRect(rect, 17, 17)
        painter.setPen(QColor(255, 226, 238))
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.setOpacity(1.0)

    # ---------- 内容读取 ----------

    def _load_pix(self, rec, need_w=0, need_h=0):
        path = self.store.record_path(rec)
        if not path.exists():
            return None
        key = str(path)
        pix = self._pix_cache.get(key)
        if pix is None:
            try:
                pix = QPixmap(str(path))
            except Exception:
                pix = QPixmap()
            if pix.isNull():
                return None
            self._pix_cache[key] = pix
            if len(self._pix_cache) > 30:
                self._pix_cache.pop(next(iter(self._pix_cache)))
        if need_w > 0 and need_h > 0:
            scaled = pix.scaled(int(need_w), int(need_h),
                                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            return scaled
        return pix

    def _preview_for(self, rec) -> str:
        cache_key = rec.get("id")
        if getattr(self, "_preview_cache", {}).get(cache_key) is None:
            path = self.store.record_path(rec)
            if path.exists() and path.suffix.lower() in DOC_EXTS | TEXT_EXTS:
                self._preview_cache[cache_key] = _extract_text_preview(path, 600)
            else:
                self._preview_cache[cache_key] = ""
        return self._preview_cache[cache_key]

    def _record_path(self, rec) -> Path:
        return self.store.record_path(rec)

    def _parent(self):
        return self._host

    # ---------- 操作 ----------

    def _open_external(self, rec):
        path = self._record_path(rec)
        if not path.exists():
            if rec.get("kind") == "text" and not rec.get("file"):
                self._show_toast("Text record has no file, click to preview")
            else:
                self._show_toast("File not found or moved")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self._parent(), "Open failed",
                                "Cannot open with the default program")

    # ---------- 全窗预览（单击进入，单击退出） ----------

    def _do_preview(self):
        if not self._pending_preview:
            return
        rect, action, rec = self._pending_preview
        self._pending_preview = None
        if rec.get("kind") == "image":
            path = self._record_path(rec)
            if not path.exists():
                self._show_toast("Image file not found or moved")
                return
            self._preview = {"kind": "image", "path": path, "rec": rec}
        else:
            # 文本 / 文档：读取完整内容（不截断），在本背景上预览
            text = (rec.get("text") or "").strip()
            if not text:
                path = self._record_path(rec)
                if path.exists():
                    text = _extract_text_full(path).strip()
            if not text:
                self._show_toast("Inline preview not supported, "
                                 "double-click to open with the default program")
                return
            self._preview = {"kind": "text", "text": text, "rec": rec}
            fname = rec.get("file_name") or rec.get("file", "")
            self._preview_header = (
                f"{fname} · {rec.get('user', '')} · {rec.get('time', '')}"
                if fname else f"{rec.get('user', '')} · {rec.get('time', '')}")
            # 字体略小，保证长文档能显示完整内容
            body_font = QFont("Microsoft YaHei", 13)
            fm = QFontMetrics(body_font)
            col_w = min(self.w * 0.6, 920)
            self._preview_lines = _wrap_text(text, fm, col_w)
        self._preview_scroll = 0.0

    def _cancel_pending_preview(self):
        self._pending_preview = None
        if self._preview_timer.isActive():
            self._preview_timer.stop()

    def _clamp_preview_scroll(self):
        fm = QFontMetrics(QFont("Microsoft YaHei", 13))
        line_h = fm.height() + 6
        content_top, content_bottom = 64, self.h - 44
        total = len(self._preview_lines) * line_h
        max_s = max(0, total - (content_bottom - content_top
                                - 2 * self.EDGE_FADE - 16))
        self._preview_scroll = max(0.0, min(float(max_s), self._preview_scroll))
        return max_s

    def _paint_preview(self, painter, w, h):
        pv = self._preview
        if pv is None:
            return
        # 全窗黑灰底
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(22, 22, 26)))
        painter.drawRect(QRectF(0, 0, w, h))
        pix = QPixmap(str(pv["path"]))
        if not pix.isNull():
            # 等比放大到占满窗口，不拉伸；覆盖不了的地方保持黑灰
            scaled = pix.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(QPointF((w - scaled.width()) / 2,
                                       (h - scaled.height()) / 2), scaled)
        else:
            painter.setFont(QFont("Microsoft YaHei", 14))
            painter.setPen(QColor(220, 215, 228))
            painter.drawText(QRectF(0, h / 2 - 20, w, 40), Qt.AlignCenter,
                             "Cannot load image")

    def _paint_text_preview(self, painter, w, h):
        """文本 / 文档：直接在页面背景上全窗预览，其他控件暂时隐藏"""
        font = QFont("Microsoft YaHei", 13)
        painter.setFont(font)
        fm = QFontMetrics(font)
        line_h = fm.height() + 6
        col_w = min(w * 0.6, 920)
        x0 = (w - col_w) / 2
        content_top, content_bottom = 64, h - 44
        max_scroll = self._clamp_preview_scroll()
        content = QRectF(x0 - 20, content_top, col_w + 40,
                         content_bottom - content_top)

        # 标题
        if self._preview_header:
            painter.setFont(QFont("Microsoft YaHei", 12))
            painter.setPen(QColor(190, 210, 235, 230))
            painter.drawText(QRectF(x0, 22, col_w, 26),
                             Qt.AlignLeft | Qt.AlignVCenter,
                             self._preview_header)

        # 正文（完整内容，可滚动；桥式渐隐，首尾都能完整展示）
        painter.save()
        painter.setClipRect(content)
        painter.setFont(font)
        y = content_top + self.EDGE_FADE + 8 - self._preview_scroll
        for ln in self._preview_lines:
            painter.setPen(QColor(240, 235, 246, 235))
            painter.drawText(QRectF(x0, y, col_w, line_h),
                             Qt.AlignLeft | Qt.AlignTop, ln)
            y += line_h
        painter.restore()

        # 标题下与底部渐隐（与时间线同款遮罩）
        self._paint_preview_edge_fade(painter, content)

        # 右侧可拖动滚动条（样式沿用时间线那条，但可拖动）
        if max_scroll > 0:
            sb_x = content.right() + 14
            self._preview_sb_rect = QRectF(sb_x - 2, content.top() + 4, 5,
                                           content.height() - 8)
            th_h = max(24.0, self._preview_sb_rect.height()
                       * (content.height()
                          / max(1.0, len(self._preview_lines) * line_h)))
            ratio = self._preview_scroll / max_scroll
            th_y = (self._preview_sb_rect.top()
                    + ratio * (self._preview_sb_rect.height() - th_h))
            self._preview_sb_thumb = QRectF(
                self._preview_sb_rect.left(), th_y,
                self._preview_sb_rect.width(), th_h)
            grad = QLinearGradient(0, th_y, 0, th_y + th_h)
            grad.setColorAt(0.0, QColor(150, 200, 255, 0))
            grad.setColorAt(0.3, QColor(150, 200, 255, 210))
            grad.setColorAt(0.7, QColor(150, 200, 255, 210))
            grad.setColorAt(1.0, QColor(150, 200, 255, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(self._preview_sb_thumb, 2, 2)
        else:
            self._preview_sb_rect = QRectF()

    def _paint_preview_edge_fade(self, painter, content):
        """预览文本上下两侧渐隐（隐入页面背景，不穿帮）"""
        fade = self.EDGE_FADE
        top_col = self._bg_color_at(content.top())
        bot_col = self._bg_color_at(content.bottom())
        painter.save()
        painter.setClipRect(content)
        g1 = QLinearGradient(0, content.top(), 0, content.top() + fade)
        g1.setColorAt(0.0, QColor(top_col[0], top_col[1], top_col[2], 235))
        g1.setColorAt(1.0, QColor(top_col[0], top_col[1], top_col[2], 0))
        painter.fillRect(QRectF(content.left(), content.top(),
                                content.width(), fade), QBrush(g1))
        g2 = QLinearGradient(0, content.bottom() - fade, 0, content.bottom())
        g2.setColorAt(0.0, QColor(bot_col[0], bot_col[1], bot_col[2], 0))
        g2.setColorAt(1.0, QColor(bot_col[0], bot_col[1], bot_col[2], 235))
        painter.fillRect(QRectF(content.left(), content.bottom() - fade,
                                content.width(), fade), QBrush(g2))
        painter.restore()

    # ---------- 音频内嵌播放（三角 + 进度条） ----------

    def _toggle_audio(self, rec):
        path = self._record_path(rec)
        if not path.exists():
            self._show_toast("Audio file not found or moved")
            return
        if self._audio_player is None:
            self._audio_player = QMediaPlayer(self._host)
        rid = rec.get("id")
        if (self._audio_rec == rid
                and self._audio_player.state() == QMediaPlayer.PlayingState):
            self._audio_player.pause()
            return
        self._audio_player.stop()
        self._audio_rec = rid
        self._audio_player.setMedia(QMediaContent(QUrl.fromLocalFile(str(path))))
        self._audio_player.play()

    def _seek_audio(self, rec, x):
        if self._audio_player is None or self._audio_rec != rec.get("id"):
            self._toggle_audio(rec)
        if self._audio_player is None or self._audio_rec != rec.get("id"):
            return
        dur = self._audio_player.duration()
        if dur <= 0:
            # 媒体还没加载完：记下目标比例，加载完成后立即跳转
            for br, action, r2 in self._hit_rects:
                if action == "seek" and r2.get("id") == rec.get("id"):
                    bar = br.translated(0, -self._scroll)
                    ratio = (x - bar.left()) / max(1.0, bar.width())
                    self._pending_seek = max(0.0, min(1.0, ratio))
                    return
            return
        self._pending_seek = None
        for br, action, r2 in self._hit_rects:
            if action == "seek" and r2.get("id") == rec.get("id"):
                bar = br.translated(0, -self._scroll)
                ratio = (x - bar.left()) / max(1.0, bar.width())
                ratio = max(0.0, min(1.0, ratio))
                self._audio_player.setPosition(int(dur * ratio))
                return

    def _stop_audio(self):
        if self._audio_player is not None:
            self._audio_player.stop()
        self._audio_rec = None

    def _mute_audio(self, muted: bool):
        if self._audio_player is not None:
            try:
                self._audio_player.setMuted(muted)
            except Exception:
                pass

    def _send_text(self):
        occ = self._current_occurrence()
        if occ is None:
            return
        if not self._is_upload_open(occ):
            self._show_toast("Text can only be sent within 3 days of the anniversary")
            return
        self._set_mode("text")

    def _submit_text(self, text):
        occ = self._current_occurrence()
        if occ is None:
            return
        rec = {
            "anniversary_id": occ["anniversary_id"],
            "date": occ["date"],
            "user": self.current_user,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "kind": "text",
            "text": text,
            "file": "",
            "file_name": "",
        }
        self.store.add_record(rec)
        self._after_change()
        self._show_toast("Sent")

    def _upload_files(self):
        occ = self._current_occurrence()
        if occ is None:
            return
        if not self._is_upload_open(occ):
            self._show_toast("Files can only be uploaded within 3 days of the anniversary")
            return
        files, _ = QFileDialog.getOpenFileNames(
            self._parent(), "Choose files to upload (document / image / audio / video)")
        if not files:
            return
        for f in files:
            src = Path(f)
            if not src.is_file():
                continue
            name = self.store.copy_file(src, occ["name"], occ["date"])
            rec = {
                "anniversary_id": occ["anniversary_id"],
                "date": occ["date"],
                "user": self.current_user,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "kind": record_kind_for(src),
                "text": "",
                "file": name,
                "file_name": src.name,
            }
            self.store.add_record(rec)
        self._after_change()
        self._show_toast(f"Uploaded {len(files)} file(s)")

    def _open_settings(self):
        self._set_mode("settings")

    # ---------- 页面模式切换（背景不变，内容整页切换 + 返回） ----------

    def _set_mode(self, mode, payload=None):
        self._clear_mode()
        self._mode = mode
        if mode == "timeline":
            return
        host = self._host
        if host is None:
            return
        if mode == "text":
            occ = self._current_occurrence()
            view = TextModeView(host, occ["name"], self.current_user,
                                self._submit_text)
        elif mode == "settings":
            def done():
                self._after_change()
                self._rebuild()
            view = SettingsModeView(host, self.store, done,
                                    notify=self._show_toast)
        else:
            self._mode = "timeline"
            return
        view.set_on_back(self._back_to_timeline)
        g = self._geo()
        view.setGeometry(int(g["x0"]), int(g["top"]),
                         int(g["x1"] - g["x0"]), int(g["bottom"] - g["top"]))
        view.show()
        view.raise_()
        self._mode_view = view

    def _back_to_timeline(self):
        self._clear_mode()
        self._mode = "timeline"

    def _clear_mode(self):
        if self._mode_view is not None:
            self._mode_view.hide()
            self._mode_view.deleteLater()
            self._mode_view = None

    def _after_change(self):
        self.store.publish_content()   # 先把工作区内容打包回加密 zip
        self._rebuild()
        self._layout_sig = None
        if self.push_callback:
            self.push_callback(self._anniversary_push_files(), self._on_push_done)

    def _on_app_close(self):
        """退出前：回写加密 zip；仅当有本地改动时触发最终推送（只传变化的文件）；
        解密目录（remote/anniversary）等推送完成后由主窗口删除"""
        self.store.publish_content()
        if self.store.is_dirty() and self.push_callback:
            self.push_callback(self._anniversary_push_files(), self._on_push_done)

    def delete_workspace(self):
        """推送完成后：删除解密的工作目录，本地只保留加密 zip"""
        self.store.delete_workspace()

    def _anniversary_push_files(self) -> list:
        """提交后要推送到远程的文件：remote/anniversary/ 下的全部内容"""
        files = []
        root = self.config.anniversary_dir
        if root.exists():
            for f in sorted(root.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(self.config.data_dir).as_posix()
                    if "/_deleted/" in rel:
                        continue   # 已删除纪念日的备份不再参与同步
                    files.append(rel)
        return files or ["anniversary/anniversaries.json"]

    def _on_push_done(self, errors):
        if errors:
            self._show_toast("Saved (remote sync failed, will retry later)")
        else:
            self.store.mark_clean()
            self._show_toast("Saved & synced")

    # ---------- 动画 ----------

    def tick(self, frame):
        self.frame = frame
        self._tick_scene()
        # 音频：媒体加载完成后应用等待中的跳转
        if (self._pending_seek is not None and self._audio_player is not None
                and self._audio_player.duration() > 0):
            self._audio_player.setPosition(
                int(self._audio_player.duration() * self._pending_seek))
            self._pending_seek = None
        if self._fade < 1.0:
            self._fade = min(1.0, self._fade + 0.06)
        # 右下角按钮浮现
        if self._host is not None:
            try:
                from PyQt5.QtGui import QCursor
                pos = self._host.mapFromGlobal(QCursor.pos())
            except Exception:
                pos = None
        else:
            pos = None
        if pos is None:
            pos = self._mouse_pos
        if pos is not None:
            near = pos.x() >= self.w - 220 and pos.y() >= self.h - 110
            self._actions_opacity = (
                min(1.0, self._actions_opacity + 0.08) if near
                else max(0.0, self._actions_opacity - 0.06))
            self._actions_hover = -1
            if self._actions_opacity > 0.2:
                for i, r in enumerate(self._action_rects()):
                    if r.contains(pos):
                        self._actions_hover = i
                        break
        # 底部竖线切换器动画
        self._selector.update_mouse(pos)
        if pos is not None:
            self._selector.update_hover(pos)
        self._selector.tick()

    def _update_hover(self, pos):
        """供主窗口鼠标移动时更新悬停状态（不消费事件）"""
        self._mouse_pos = pos
        self._selector.update_hover(pos)


# ============================================================
#  工具
# ============================================================

def _wrap_text(text: str, fm: QFontMetrics, width: float) -> list:
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        cur_w = 0.0
        for ch in para:
            ch_w = fm.horizontalAdvance(ch)
            if cur and cur_w + ch_w > width:
                lines.append(cur)
                cur = ch
                cur_w = ch_w
            else:
                cur += ch
                cur_w += ch_w
        lines.append(cur)
    return lines


def _fmt_ms(ms: int) -> str:
    s = max(0, int(ms / 1000))
    # 紧凑格式，避免长时长把时间文本挤出/遮住
    return f"{s // 60}:{s % 60:02d}"


if __name__ == "__main__":
    # 农历算法自测（不依赖 GUI）
    anchors = [
        (date(2024, 2, 10), (2024, 1, 1, False)),
        (date(2025, 1, 29), (2025, 1, 1, False)),
        (date(2026, 2, 17), (2026, 1, 1, False)),
        (date(2025, 10, 6), (2025, 8, 15, False)),
        (date(2026, 9, 25), (2026, 8, 15, False)),
        (date(2024, 2, 9), (2023, 12, 30, False)),
        (date(2023, 3, 22), (2023, 2, 1, True)),
        (date(2023, 2, 20), (2023, 2, 1, False)),
    ]
    for sd, want in anchors:
        got = solar_to_lunar(sd.year, sd.month, sd.day)
        assert got == want, f"{sd}: got {got}, want {want}"
        back = lunar_to_solar(*want[:3], want[3])
        assert back == sd, f"{want}: got {back}, want {sd}"
    # 往返一致性
    import random
    random.seed(42)
    d0 = date(1901, 1, 1)
    d1 = date(2099, 12, 31)
    span = (d1 - d0).days
    for _ in range(2000):
        sd = d0 + timedelta(days=random.randint(0, span))
        ly, lm, ld, lp = solar_to_lunar(sd.year, sd.month, sd.day)
        assert lunar_to_solar(ly, lm, ld, lp) == sd, f"roundtrip failed at {sd}"
    print("lunar tests passed")
    print(lunar_text(*solar_to_lunar(2026, 8, 5)))
