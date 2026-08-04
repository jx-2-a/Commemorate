"""
浪漫纪念动画窗口 — Romantic Commemorative Window
一个全屏无边框窗口，用流动的星光、漂浮的爱心和柔光粒子
来纪念生命中某个珍贵的时刻。

启动流程: 登录 → 版本检查 → 主窗口
"""
import sys
import math
import random
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QRadialGradient, QLinearGradient,
    QPen, QBrush, QPainterPath, QFontMetrics
)
from PyQt5.QtWidgets import QApplication, QWidget

from app_config import ConfigManager


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
            | Qt.Tool
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

    def _tick(self):
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
            self.close()
        elif event.key() == Qt.Key_F:
            if self.windowState() & Qt.WindowFullScreen:
                self.showNormal()
            else:
                self.showFullScreen()

    def mouseDoubleClickEvent(self, event):
        self.close()


# ============================================================
#  入口 — 由 login_window 和 update_manager 协同编排
# ============================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Commemorate")

    config = ConfigManager("config.json")
    args = sys.argv[1:]

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

    # ---- 登录阶段 ----
    from login_window import LoginWindow
    login = LoginWindow(config)
    if login.exec_() != LoginWindow.Accepted:
        sys.exit(0)

    # ---- 数据同步（私有仓库 → 本地 data/） ----
    if config.sync_auto_pull and "--skip-sync" not in args:
        from data_sync import DataSyncManager, run_sync
        sync_mgr = DataSyncManager(config)
        run_sync(sync_mgr, "pull", show_progress=True)

    # ---- 更新检查阶段 ----
    if config.update_auto_check and config.update_check_url:
        from update_manager import UpdateManager, show_update_dialog
        update_mgr = UpdateManager(config)
        action = show_update_dialog(update_mgr, config)
        if action == "install":
            sys.exit(0)  # 已安排更新，退出

    # ---- 主窗口 ----
    window = CommemorateWindow(config)
    window.show()
    sys.exit(app.exec_())
