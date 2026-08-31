# -*- coding: utf-8 -*-
"""不受纪念日时间窗口限制的日常记录页。"""

from datetime import date, datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QPointF, QRectF, QDate
from PyQt5.QtGui import QColor, QFont, QPen
from PyQt5.QtWidgets import (
    QCalendarWidget, QDialog, QDialogButtonBox, QFileDialog, QVBoxLayout,
)

from anniversary_page import (
    AnniversaryRecordsPage, AnniversaryStore, record_kind_for,
)


class RecordStore(AnniversaryStore):
    """使用独立目录保存日常记录，同时复用纪念日的加密与媒体存储能力。"""

    RECORD_ID = "daily-record"
    RECORD_NAME = "记录"

    def load(self):
        """初始化固定的记录时间线；具体内容在工作区打开后加载。"""
        self.anniversaries = [{"id": self.RECORD_ID, "name": self.RECORD_NAME}]
        self.deleted_ids = set()
        self._legacy_records = []
        self.records = []

    @property
    def root(self) -> Path:
        """返回参与远程同步的独立记录目录。"""
        return self.config.record_dir

    @property
    def list_path(self) -> Path:
        """保留兼容接口；日常记录不需要单独的纪念日清单。"""
        return self.root / "index.json"

    @property
    def zip_path(self) -> Path:
        """返回仅保存在本地的加密备份路径。"""
        return self.config.record_backup_path

    @property
    def deleted_list_path(self) -> Path:
        """返回兼容纪念日存储协议的删除清单路径。"""
        return self.root / "deleted.json"

    def _password(self) -> bytes:
        """沿用应用现有的本地内容加密密码配置。"""
        return self.config.anniversary_zip_password.encode()


class RecordPage(AnniversaryRecordsPage):
    """按日期整理想法和媒体文件的独立记录页。"""

    name = "Record"
    bg_colors = ((12, 10, 28), (34, 24, 56), (62, 38, 72))
    accent = (224, 170, 220)
    store_class = RecordStore

    def __init__(self, config):
        """创建记录页，默认定位到今天。"""
        self._selected_date = date.today().isoformat()
        super().__init__(config)

    def _build_occurrences(self) -> list:
        """从已有记录日期构造时间轴，并始终保留当前选中的日期。"""
        dates = {
            str(record.get("date", ""))
            for record in self.store.records
            if record.get("date")
        }
        dates.add(getattr(self, "_selected_date", date.today().isoformat()))
        occurrences = []
        for value in sorted(dates):
            try:
                date.fromisoformat(value)
            except ValueError:
                continue
            occurrences.append({
                "key": f"{RecordStore.RECORD_ID}:{value}",
                "anniversary_id": RecordStore.RECORD_ID,
                "date": value,
                "name": RecordStore.RECORD_NAME,
                "calendar": "solar",
                "lunar": "",
            })
        return occurrences

    def _selector_label(self, occurrence) -> str:
        """显示完整日期，方便在不限年份的记录之间切换。"""
        try:
            day = date.fromisoformat(occurrence["date"])
            weekdays = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
            return f"{occurrence['date']}  {weekdays[day.weekday()]}"
        except (KeyError, ValueError):
            return str(occurrence.get("date", ""))

    def _is_upload_open(self, occurrence) -> bool:
        """日常记录不设置纪念日前后三天的时间限制。"""
        return occurrence is not None

    def _default_index(self) -> int:
        """刷新或保存后仍停留在用户正在查看的日期。"""
        selected = getattr(self, "_selected_date", date.today().isoformat())
        for index, occurrence in enumerate(self._occurrences):
            if occurrence["date"] == selected:
                return index
        return super()._default_index()

    def _jump_to(self, index):
        """切换时间线日期，并记住它供后续保存和刷新使用。"""
        if 0 <= index < len(self._occurrences):
            self._selected_date = self._occurrences[index]["date"]
        super()._jump_to(index)

    def _open_settings(self):
        """用日期选择器切换到任意一天，允许补记过去或写下未来想法。"""
        dialog = QDialog(self._parent())
        dialog.setWindowTitle("选择记录日期")
        dialog.resize(420, 360)
        layout = QVBoxLayout(dialog)
        calendar = QCalendarWidget(dialog)
        calendar.setGridVisible(True)
        try:
            chosen = date.fromisoformat(self._current_occurrence()["date"])
        except (TypeError, KeyError, ValueError):
            chosen = date.today()
        calendar.setSelectedDate(QDate(chosen.year, chosen.month, chosen.day))
        layout.addWidget(calendar, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec_() != QDialog.Accepted:
            return
        selected = calendar.selectedDate()
        self._selected_date = date(
            selected.year(), selected.month(), selected.day()).isoformat()
        self._rebuild()
        for index, occurrence in enumerate(self._occurrences):
            if occurrence["date"] == self._selected_date:
                self._current = index
                self._selector.set_current(index)
                self._scroll = 0.0
                self._fade = 0.35
                self._layout_sig = None
                break

    def _submit_text(self, text):
        """把文本写入当前选中的日期。"""
        occurrence = self._current_occurrence()
        if occurrence is None:
            return
        self.store.add_record({
            "anniversary_id": RecordStore.RECORD_ID,
            "date": occurrence["date"],
            "user": self.current_user,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "kind": "text",
            "text": text,
            "file": "",
            "file_name": "",
        })
        self._after_change()
        self._show_toast("记录已保存")

    def _upload_files(self):
        """把图片、音频和视频等文件保存到当前选中的日期。"""
        occurrence = self._current_occurrence()
        if occurrence is None:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self._parent(),
            "选择图片、音频或视频",
            "",
            "媒体文件 (*.jpg *.jpeg *.png *.gif *.bmp *.webp *.mp3 *.wav *.ogg *.flac *.m4a *.aac *.wma *.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.ts);;所有文件 (*)",
        )
        saved = 0
        for filename in files:
            source = Path(filename)
            if not source.is_file():
                continue
            stored_name = self.store.copy_file(
                source, RecordStore.RECORD_NAME, occurrence["date"])
            self.store.add_record({
                "anniversary_id": RecordStore.RECORD_ID,
                "date": occurrence["date"],
                "user": self.current_user,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "kind": record_kind_for(source),
                "text": "",
                "file": stored_name,
                "file_name": source.name,
            })
            saved += 1
        if saved:
            self._after_change()
            self._show_toast(f"已保存 {saved} 个文件")

    def _paint_title(self, painter, w, h):
        """绘制记录页标题和当前日期。"""
        occurrence = self._current_occurrence()
        if occurrence is None:
            return
        top = self._geo()["top"]
        painter.setOpacity(self._fade)
        painter.setFont(QFont("Microsoft YaHei", 26, QFont.Bold))
        painter.setPen(QColor(255, 240, 248, 245))
        painter.drawText(QRectF(0, top - 104, w, 52), Qt.AlignCenter, "记录")
        try:
            day = date.fromisoformat(occurrence["date"])
            weekdays = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
            weekday = weekdays[day.weekday()]
        except ValueError:
            weekday = ""
        painter.setFont(QFont("Microsoft YaHei", 12))
        painter.setPen(QColor(220, 205, 226, 230))
        painter.drawText(
            QRectF(0, top - 50, w, 30), Qt.AlignCenter,
            f"{occurrence['date']}  {weekday}")
        painter.setOpacity(1.0)

    def _paint_timeline(self, painter, w, h):
        """为空日期显示记录引导，其余沿用完整媒体时间线。"""
        occurrence = self._current_occurrence()
        if occurrence is not None and not self._records_for(occurrence):
            content = getattr(self, "_content_rect", QRectF(0, 0, w, h))
            painter.setFont(QFont("Microsoft YaHei", 13))
            painter.setPen(QColor(220, 205, 228, 220))
            painter.drawText(
                content.adjusted(20, 30, -20, -30), Qt.AlignCenter,
                "这一天还没有记录\n从右下角写下想法，或添加图片、音频和视频")
            return
        super()._paint_timeline(painter, w, h)

    def _draw_action_icon(self, painter, rect, kind, alpha, scale=1.0):
        """将第三个操作按钮绘制为日期选择图标。"""
        if kind != 2:
            super()._draw_action_icon(painter, rect, kind, alpha, scale)
            return
        pen = QPen(QColor(255, 240, 245, alpha), max(1.5, 2 * scale))
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        cx, cy = rect.center().x(), rect.center().y()
        body = QRectF(
            cx - 10 * scale, cy - 8 * scale,
            20 * scale, 18 * scale)
        painter.drawRoundedRect(body, 3 * scale, 3 * scale)
        painter.drawLine(
            QPointF(body.left(), cy - 3 * scale),
            QPointF(body.right(), cy - 3 * scale))
        painter.drawLine(
            QPointF(cx - 5 * scale, cy - 11 * scale),
            QPointF(cx - 5 * scale, cy - 6 * scale))
        painter.drawLine(
            QPointF(cx + 5 * scale, cy - 11 * scale),
            QPointF(cx + 5 * scale, cy - 6 * scale))

    def _anniversary_push_files(self) -> list:
        """收集记录页需要同步的全部文件。"""
        files = []
        root = self.config.record_dir
        if root.exists():
            for item in sorted(root.rglob("*")):
                if item.is_file():
                    files.append(item.relative_to(self.config.data_dir).as_posix())
        return files
