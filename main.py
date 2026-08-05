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
    QPen, QBrush, QPainterPath, QFontMetrics, QCursor
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

MESSAGE_CSV_NAME = "TimerPageWords.csv"


def _load_random_message(config) -> str:
    """从计时页语 CSV 中随机选取一行话语（找不到文件时返回空串）"""
    candidates = []
    candidates.append(config.data_dir / MESSAGE_CSV_NAME)
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.append(meipass / MESSAGE_CSV_NAME)
    candidates.append(Path(__file__).resolve().parent / MESSAGE_CSV_NAME)

    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except Exception:
            continue
        messages = []
        for line in text.splitlines():
            line = line.strip().strip('"').strip("'").strip()
            if line and not line.startswith("#"):
                messages.append(line)
        if messages:
            return random.choice(messages)
    return ""


class CountdownPage:
    """纪念计时页：夜空粒子 + DHM 计时 + 随机话语"""

    name = "Countdown"

    def __init__(self, config):
        self.config = config
        self._comm_date = config.commemorative_date
        self._comm_time = config.commemorative_time
        self._comm_message = _load_random_message(config)
        self.frame = 0
        self.fade_in = 0.0
        self.time_displayed = False
        self.w = 0
        self.h = 0
        self.stars = []
        self.hearts = []
        self.fireflies = []

    def resize(self, w, h):
        """窗口尺寸变化时重新铺开粒子"""
        self.w = w
        self.h = h
        self.stars = [Star(w, h) for _ in range(120)]
        self.hearts = [Heart(w, h) for _ in range(45)]
        self.fireflies = [Firefly(w, h) for _ in range(18)]

    def refresh(self):
        """同步后刷新纪念信息与随机话语"""
        self._comm_date = self.config.commemorative_date
        self._comm_time = self.config.commemorative_time
        self._comm_message = _load_random_message(self.config)

    def show_time(self):
        self.time_displayed = True

    def _elapsed_dhm(self) -> str:
        """从开始时间到现在的间隔，格式：1877D 05H 32M"""
        try:
            past = datetime.strptime(
                f"{self._comm_date} {self._comm_time}", "%Y-%m-%d %H:%M"
            )
            elapsed = datetime.now() - past
            days = max(0, elapsed.days)
            hours = max(0, elapsed.seconds // 3600)
            minutes = max(0, (elapsed.seconds % 3600) // 60)
            return f"{days}D {hours:02d}H {minutes:02d}M"
        except ValueError:
            return "0D 00H 00M"

    def tick(self, frame):
        self.frame = frame
        if self.fade_in < 1.0:
            self.fade_in = min(1.0, self.fade_in + 0.008)
        for s in self.stars:
            s.update(frame)
        for h in self.hearts:
            h.update(frame, self.w, self.h)
        for f in self.fireflies:
            f.update(frame, self.w, self.h)

    def paint(self, painter, w, h):
        self.w = w
        self.h = h

        # ── 1. 夜空背景 ──────────────────────────────────
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(5, 2, 20))
        bg.setColorAt(0.4, QColor(18, 8, 40))
        bg.setColorAt(0.75, QColor(25, 10, 45))
        bg.setColorAt(1.0, QColor(40, 15, 55))
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.NoPen)
        painter.drawRect(QRectF(0, 0, w, h))

        # ── 2. 星星 ──────────────────────────────────────
        for s in self.stars:
            color = QColor(255, 255, 220, int(200 * s.brightness * self.fade_in))
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(s.x, s.y), s.size, s.size)

        # ── 3. 萤火虫光晕 ────────────────────────────────
        for f in self.fireflies:
            alpha = int(255 * f.opacity * self.fade_in)
            if alpha < 5:
                continue
            gradient = QRadialGradient(QPointF(f.x, f.y), f.size)
            gradient.setColorAt(0.0, QColor(255, 220, 140, alpha))
            gradient.setColorAt(0.4, QColor(255, 180, 100, alpha // 2))
            gradient.setColorAt(1.0, QColor(255, 220, 140, 0))
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

        # ── 5. 中央：DHM 计时 + 随机话语 ──
        cx = w / 2
        title_alpha = int(255 * self.fade_in)
        if title_alpha > 5:
            timer_y = int(h * 0.46)
            msg_y = timer_y + 90

            timer_text = self._elapsed_dhm()
            timer_font = QFont("Microsoft YaHei", 50, QFont.Bold)
            painter.setFont(timer_font)
            painter.setPen(QColor(255, 235, 245, title_alpha))
            fm = QFontMetrics(timer_font)
            tw = fm.horizontalAdvance(timer_text)
            painter.drawText(int(cx - tw / 2), timer_y, timer_text)

            if self._comm_message:
                msg_font = QFont("Microsoft YaHei", 20)
                msg_font.setItalic(True)
                painter.setFont(msg_font)
                painter.setPen(QColor(235, 205, 235, int(title_alpha * 0.9)))
                fm2 = QFontMetrics(msg_font)
                mw = fm2.horizontalAdvance(self._comm_message)
                painter.drawText(int(cx - mw / 2), msg_y, self._comm_message)

        # ── 6. 底部当前时间 ──────────────────────────────
        if self.time_displayed:
            bottom_alpha = min(1.0, (self.frame - 150) / 80.0)
            if bottom_alpha > 0.05:
                alpha = int(255 * bottom_alpha)
                bottom_font = QFont("Microsoft YaHei", 13)
                painter.setFont(bottom_font)
                painter.setPen(QColor(220, 200, 230, alpha))
                date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                fm3 = QFontMetrics(bottom_font)
                dw = fm3.horizontalAdvance(date_str)
                painter.drawText(int(cx - dw / 2), h - 90, date_str)
                painter.setPen(QPen(QColor(180, 140, 200, alpha), 1))
                painter.drawLine(int(cx - 120), h - 78, int(cx + 120), h - 78)

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


class ScenePage:
    """带场景动画的测试页基类：每页一套配色 + 一种背景场景"""

    name = "Scene"
    bg_colors = ((8, 4, 24), (22, 10, 42), (42, 18, 56))
    accent = (255, 170, 210)

    def __init__(self, config):
        self.config = config
        self.fade_in = 1.0
        self.frame = 0
        self.w = 0
        self.h = 0
        self._init_scene()

    def resize(self, w, h):
        self.w = w
        self.h = h
        self._init_scene()

    def refresh(self):
        pass

    def show_time(self):
        pass

    def tick(self, frame):
        self.frame = frame
        self._tick_scene()

    def paint(self, painter, w, h):
        self.w = w
        self.h = h
        # 渐变背景（圆角）
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(*self.bg_colors[0]))
        bg.setColorAt(0.5, QColor(*self.bg_colors[1]))
        bg.setColorAt(1.0, QColor(*self.bg_colors[2]))
        painter.setBrush(QBrush(bg))
        painter.drawRect(QRectF(0, 0, w, h))
        # 场景动画
        self._paint_scene(painter, w, h)
        # 页面名称
        painter.setFont(QFont("Microsoft YaHei", 36, QFont.Bold))
        painter.setPen(QColor(255, 235, 245, 220))
        fm = QFontMetrics(painter.font())
        tw = fm.horizontalAdvance(self.name)
        painter.drawText(int(w / 2 - tw / 2), int(h / 2), self.name)

    def _init_scene(self):
        pass

    def _tick_scene(self):
        pass

    def _paint_scene(self, painter, w, h):
        pass


class GalleryPage(ScenePage):
    """斜向流星场景"""

    name = "Gallery"
    bg_colors = ((6, 10, 28), (14, 30, 58), (26, 52, 86))
    accent = (150, 200, 255)

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


class MusicPage(ScenePage):
    """同心圆波纹场景"""

    name = "Music"
    bg_colors = ((24, 4, 30), (46, 12, 52), (74, 26, 70))
    accent = (255, 150, 220)

    def _init_scene(self):
        self.rings = [self._new_ring() for _ in range(6)]

    def _new_ring(self):
        return {
            "x": random.uniform(0.2, 0.8) * self.w,
            "y": random.uniform(0.2, 0.8) * self.h,
            "r": random.uniform(0, 40),
            "vr": random.uniform(1.4, 2.6),
            "alpha": random.uniform(0.25, 0.5),
        }

    def _tick_scene(self):
        for r in self.rings:
            r["r"] += r["vr"]
            r["alpha"] -= 0.006
        self.rings = [r for r in self.rings if r["alpha"] > 0.01]
        while len(self.rings) < 6:
            self.rings.append(self._new_ring())

    def _paint_scene(self, painter, w, h):
        accent = QColor(*self.accent)
        for r in self.rings:
            a = int(255 * r["alpha"])
            for ratio, fade in ((1.0, 1.0), (0.7, 0.55), (1.35, 0.35)):
                painter.setPen(
                    QPen(
                        QColor(accent.red(), accent.green(), accent.blue(), int(a * fade)),
                        1,
                    )
                )
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(r["x"], r["y"]), r["r"] * ratio, r["r"] * ratio)


class NotesPage(ScenePage):
    """流动颜料场景"""

    name = "Notes"
    bg_colors = ((4, 24, 18), (10, 42, 34), (20, 66, 50))
    accent = (120, 230, 180)

    def _init_scene(self):
        self.blobs = []
        for _ in range(8):
            self.blobs.append({
                "x": random.uniform(0, self.w),
                "y": random.uniform(0, self.h),
                "vx": random.uniform(-0.5, 0.5),
                "vy": random.uniform(-0.4, 0.4),
                "r": random.uniform(70, 180),
                "hue": random.uniform(0, 1),
            })

    def _tick_scene(self):
        for b in self.blobs:
            b["vx"] = max(-1.2, min(1.2, b["vx"] + random.uniform(-0.06, 0.06)))
            b["vy"] = max(-1.0, min(1.0, b["vy"] + random.uniform(-0.06, 0.06)))
            b["x"] += b["vx"]
            b["y"] += b["vy"]
            if b["x"] < -b["r"]:
                b["x"] = self.w + b["r"]
            if b["x"] > self.w + b["r"]:
                b["x"] = -b["r"]
            if b["y"] < -b["r"]:
                b["y"] = self.h + b["r"]
            if b["y"] > self.h + b["r"]:
                b["y"] = -b["r"]

    def _paint_scene(self, painter, w, h):
        for b in self.blobs:
            col = QColor.fromHsvF(b["hue"], 0.5, 0.95, 0.16)
            grad = QRadialGradient(QPointF(b["x"], b["y"]), b["r"])
            grad.setColorAt(0.0, col)
            grad.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(b["x"], b["y"]), b["r"], b["r"])


class SettingsPage(ScenePage):
    """极光波浪场景"""

    name = "Settings"
    bg_colors = ((10, 10, 30), (20, 24, 52), (36, 44, 80))
    accent = (170, 160, 255)

    def _init_scene(self):
        self.bands = []
        for i in range(4):
            self.bands.append({
                "amp": random.uniform(22, 55),
                "freq": random.uniform(0.004, 0.009),
                "phase": random.uniform(0, math.pi * 2),
                "y0": random.uniform(0.15, 0.55) * self.h,
                "hue": random.uniform(-0.08, 0.18),
            })

    def _tick_scene(self):
        for b in self.bands:
            b["phase"] += 0.018

    def _paint_scene(self, painter, w, h):
        for b in self.bands:
            path = QPainterPath()
            path.moveTo(0, b["y0"] + math.sin(b["phase"]) * b["amp"])
            for x in range(0, w + 1, 12):
                y = b["y0"] + math.sin(x * b["freq"] + b["phase"]) * b["amp"]
                path.lineTo(x, y)
            path.lineTo(w, h)
            path.lineTo(0, h)
            path.closeSubpath()
            grad = QLinearGradient(0, 0, 0, h)
            col = QColor.fromHsvF(0.55 + b["hue"], 0.6, 0.95, 0.22)
            grad.setColorAt(0.0, col)
            grad.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)


class DiaryPage(ScenePage):
    """暖色余烬飘升场景"""

    name = "Diary"
    bg_colors = ((30, 12, 6), (56, 24, 12), (86, 42, 22))
    accent = (255, 190, 130)

    def _init_scene(self):
        self.embers = []
        for _ in range(40):
            self.embers.append({
                "x": random.uniform(0, self.w),
                "y": random.uniform(0, self.h),
                "vx": random.uniform(-0.3, 0.3),
                "vy": random.uniform(-0.9, -0.25),
                "size": random.uniform(1.5, 4),
                "tw": random.uniform(0, math.pi * 2),
            })

    def _tick_scene(self):
        for p in self.embers:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["tw"] += 0.08
            if p["y"] < -20:
                p["y"] = self.h + 20
                p["x"] = random.uniform(0, self.w)

    def _paint_scene(self, painter, w, h):
        for p in self.embers:
            a = int(110 + 110 * math.sin(p["tw"]))
            a = max(20, min(210, a))
            painter.setBrush(QBrush(QColor(255, 200, 140, a)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(p["x"], p["y"]), p["size"], p["size"])


# 页面注册表：以后新增功能页时，把页面类加进这个列表即可。
# 目前除 Countdown 外均为测试用占位页，便于验证多页面目录。
PAGE_CLASSES = [
    CountdownPage,
    GalleryPage,
    MusicPage,
    NotesPage,
    SettingsPage,
    DiaryPage,
]


class CommemorateWindow(QWidget):
    """主窗口容器：右上角控制按钮 + 左侧页面目录（圆弧排列、可滚轮/拖动切换）"""

    def __init__(self, config: ConfigManager):
        super().__init__()
        self.config = config
        self.pages = [cls(config) for cls in PAGE_CLASSES]
        self.current_index = 0
        self._trans_old = None
        self._trans_progress = 1.0

        self.setWindowTitle(f"💖 {config.app_name}")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        # 获取屏幕尺寸，窗口覆盖 70% 中心区域
        screen = QApplication.primaryScreen().availableGeometry()
        self.win_w = int(screen.width() * 0.7)
        self.win_h = int(screen.height() * 0.7)
        self.resize(self.win_w, self.win_h)
        self.move((screen.width() - self.win_w) // 2, (screen.height() - self.win_h) // 2)
        for page in self.pages:
            page.resize(self.win_w, self.win_h)

        self.frame = 0

        # 右上角悬浮控制按钮（鼠标靠近时渐变浮现）
        self.controls_opacity = 0.0
        self.controls_hover = -1
        self._btn_w, self._btn_h, self._btn_gap = 34, 34, 10
        self._btn_top, self._btn_right = 14, 16

        # 左侧页面目录（鼠标靠近时渐变浮现）
        self.sidebar_opacity = 0.0
        self.sidebar_hover = -1
        self.sidebar_hover_alpha = 0.0
        self._sidebar_lens = {}
        self._drag_active = False
        self._drag_acc = 0.0
        self._drag_last_y = 0

        # 主循环
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)  # ~60 FPS

        # 3 秒后显示底部时间
        QTimer.singleShot(2500, self._show_time)

    def _current_page(self):
        return self.pages[self.current_index % len(self.pages)]

    def _show_time(self):
        self._current_page().show_time()

    def _switch_page(self, delta):
        """切换页面（滚轮 / 拖动），可扩展：页面来自 PAGE_CLASSES"""
        n = len(self.pages)
        if n < 2:
            return
        self._jump_to_page((self.current_index + delta) % n)

    def _jump_to_page(self, idx):
        """跳转到指定页面，并启动交叉淡入淡出过渡"""
        n = len(self.pages)
        if not (0 <= idx < n) or idx == self.current_index:
            return
        self._trans_old = self._current_page()
        self.current_index = idx
        self._trans_progress = 0.0
        self._current_page().show_time()
        self.update()

    def refresh_from_config(self):
        """数据同步后刷新各页面信息"""
        for page in self.pages:
            if hasattr(page, "refresh"):
                page.refresh()
        self.update()

    def _button_rects(self):
        """最小化 / 最大化 / 关闭三个按钮的区域（右上角）"""
        right = self.win_w - self._btn_right
        close = QRectF(
            right - self._btn_w, self._btn_top, self._btn_w, self._btn_h
        )
        maxi = QRectF(
            right - self._btn_w * 2 - self._btn_gap,
            self._btn_top, self._btn_w, self._btn_h,
        )
        mini = QRectF(
            right - self._btn_w * 3 - self._btn_gap * 2,
            self._btn_top, self._btn_w, self._btn_h,
        )
        return (mini, maxi, close)

    def _sidebar_layout(self):
        """左侧页面目录：纵向列表，最多 5 项，当前页恒在中间（slot 2）

        返回 [(页面索引, slot, x, y)]；slot 0..4 对应列表从上到下。
        """
        n = len(self.pages)
        if n == 0:
            return []
        x0 = 22
        y0 = self.win_h * 0.35
        y1 = self.win_h * 0.65
        out = []
        for idx in range(max(0, self.current_index - 2), min(n, self.current_index + 3)):
            slot = idx - self.current_index + 2
            t = slot / 4
            x = x0
            y = y0 + t * (y1 - y0)
            out.append((idx, slot, x, y))
        return out

    def _tick(self):
        try:
            self.frame += 1
            self._current_page().tick(self.frame)
            mouse_pos = self.mapFromGlobal(QCursor.pos())

            # 右上角控制按钮：鼠标靠近时渐变浮现，远离时渐变消失
            near_controls = (
                mouse_pos.x() >= self.win_w - 260
                and 0 <= mouse_pos.y() <= 120
            )
            if near_controls:
                self.controls_opacity = min(1.0, self.controls_opacity + 0.08)
            else:
                self.controls_opacity = max(0.0, self.controls_opacity - 0.06)
            self.controls_hover = -1
            if self.controls_opacity > 0.2:
                for i, r in enumerate(self._button_rects()):
                    if r.contains(mouse_pos):
                        self.controls_hover = i
                        break

            # 左侧页面目录：鼠标靠近左边缘时浮现，远离时消失
            near_sidebar = (
                mouse_pos.x() <= 110
                and 0 <= mouse_pos.y() <= self.win_h
            )
            if near_sidebar:
                self.sidebar_opacity = min(1.0, self.sidebar_opacity + 0.08)
            else:
                self.sidebar_opacity = max(0.0, self.sidebar_opacity - 0.06)
            self.sidebar_hover = -1
            if self.sidebar_opacity > 0.2:
                for idx, slot, x, y in self._sidebar_layout():
                    if QRectF(x - 6, y - 14, 130, 28).contains(mouse_pos):
                        self.sidebar_hover = idx
                        break
            # 悬停展开的平滑过渡（0..1）
            if self.sidebar_hover >= 0:
                self.sidebar_hover_alpha = min(1.0, self.sidebar_hover_alpha + 0.10)
            else:
                self.sidebar_hover_alpha = max(0.0, self.sidebar_hover_alpha - 0.08)

            # 页面切换过渡进度（交叉淡入淡出）
            if self._trans_progress < 1.0:
                self._trans_progress = min(1.0, self._trans_progress + 0.035)
                if self._trans_progress >= 1.0:
                    self._trans_old = None

            # 每根短横线的长度平滑过渡（避免恢复时与当前页横线冲突闪烁）
            hovered = self.sidebar_hover
            ha = self.sidebar_hover_alpha
            for idx, slot, x, y in self._sidebar_layout():
                if hovered >= 0 and ha > 0.02:
                    d = abs(idx - hovered)
                    factor = math.exp(-(d * d) / (2 * 1.15 * 1.15))
                else:
                    factor = 0.0
                target = 14 + 28 * factor * ha
                if idx == self.current_index:
                    target = max(target, 22)
                cur = self._sidebar_lens.get(idx, 14.0)
                self._sidebar_lens[idx] = cur + (target - cur) * 0.18

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

        # 0. 不透明底色（直角窗口，内部完全覆盖）
        painter.fillRect(QRectF(0, 0, w, h), QColor(8, 3, 22))

        # 1. 当前页面内容（切换时交叉淡入淡出）
        page = self._current_page()
        if self._trans_old is not None and self._trans_progress < 1.0:
            p = self._trans_progress
            painter.setOpacity(1.0 - p)
            self._trans_old.paint(painter, w, h)
            painter.setOpacity(p)
            page.paint(painter, w, h)
            painter.setOpacity(1.0)
        else:
            page.paint(painter, w, h)

        # 2. 左侧页面目录
        self._paint_sidebar(painter, w, h)

        # 3. 右上角悬浮控制按钮
        self._paint_controls(painter, w, h)

        painter.end()

    def _paint_sidebar(self, painter, w, h):
        if self.sidebar_opacity <= 0.02:
            return
        alpha = int(255 * self.sidebar_opacity)

        hovered = self.sidebar_hover
        ha = self.sidebar_hover_alpha
        items = self._sidebar_layout()

        for idx, slot, x, y in items:
            current = (idx == self.current_index)

            # 长度已在 _tick 中平滑过渡，这里直接取用
            length = self._sidebar_lens.get(idx, 14.0)
            grow = min(1.0, max(0.0, (length - 14) / 28))

            # 短横线
            if current:
                line_color = QColor(255, 190, 220, int(alpha * 0.95))
            else:
                line_color = QColor(
                    215, 210, 225, int(alpha * (0.4 + 0.45 * grow))
                )
            painter.setPen(QPen(line_color, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(QPointF(x - length / 2, y), QPointF(x + length / 2, y))

            # 悬停项显示页面名称（淡入淡出，垂直中点与横线对齐）
            if hovered == idx and ha > 0.02:
                font = QFont("Microsoft YaHei", 12)
                painter.setFont(font)
                fm = QFontMetrics(font)
                text = self.pages[idx].name
                painter.setPen(QColor(240, 238, 245, int(alpha * ha)))
                painter.drawText(
                    int(x + length / 2 + 10),
                    int(y + (fm.ascent() - fm.descent()) / 2),
                    text,
                )

    def _paint_controls(self, painter, w, h):
        if self.controls_opacity <= 0.02:
            return
        alpha = int(255 * self.controls_opacity)
        for i, r in enumerate(self._button_rects()):
            hover = (i == self.controls_hover)
            if hover:
                if i == 2:
                    bg = QColor(255, 80, 110, int(alpha * 0.9))
                else:
                    bg = QColor(90, 45, 120, int(alpha * 0.92))
            else:
                bg = QColor(15, 8, 32, int(alpha * 0.72))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(bg))
            painter.drawRoundedRect(r, 9, 9)

            pen = QPen(QColor(255, 240, 245, alpha), 2)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            cx = r.center().x()
            cy = r.center().y()
            if i == 0:
                # 最小化：横线
                painter.drawLine(QPointF(cx - 8, cy), QPointF(cx + 8, cy))
            elif i == 1:
                maxed = self.windowState() & (
                    Qt.WindowMaximized | Qt.WindowFullScreen
                )
                if maxed:
                    # 已最大化/全屏：显示“还原”图标（两个相同方框错开，
                    # 上方的方框用底色遮住下方的）
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(QRectF(cx - 4, cy - 2, 16, 14))
                    painter.setBrush(QBrush(bg))
                    painter.drawRect(QRectF(cx - 9, cy - 8, 16, 14))
                    painter.setBrush(Qt.NoBrush)
                else:
                    # 最大化：单个方框
                    painter.drawRect(QRectF(cx - 8, cy - 7, 16, 14))
            else:
                # 关闭：叉
                painter.drawLine(QPointF(cx - 7, cy - 7), QPointF(cx + 7, cy + 7))
                painter.drawLine(QPointF(cx - 7, cy + 7), QPointF(cx + 7, cy - 7))

    def wheelEvent(self, event):
        """滚轮切换页面（目录浮现时生效）"""
        if self.sidebar_opacity > 0.3:
            dy = event.angleDelta().y()
            if dy:
                self._switch_page(1 if dy < 0 else -1)
                event.accept()
                return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        """左键按住左边缘区域开始上下拖动切换页面"""
        if (
            event.button() == Qt.LeftButton
            and self.sidebar_opacity > 0.3
            and event.pos().x() <= 180
        ):
            self._drag_active = True
            self._drag_acc = 0.0
            self._drag_last_y = event.pos().y()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_active and event.buttons() & Qt.LeftButton:
            dy = event.pos().y() - self._drag_last_y
            self._drag_last_y = event.pos().y()
            self._drag_acc += dy
            threshold = 55.0
            while self._drag_acc >= threshold:
                self._switch_page(1)
                self._drag_acc -= threshold
            while self._drag_acc <= -threshold:
                self._switch_page(-1)
                self._drag_acc += threshold
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """点击目录项切换页面；点击右上角按钮执行窗口操作"""
        if event.button() == Qt.LeftButton:
            self._drag_active = False
            pos = event.pos()

            if self.sidebar_opacity > 0.4:
                for idx, slot, x, y in self._sidebar_layout():
                    if QRectF(x - 6, y - 14, 130, 28).contains(pos):
                        self._jump_to_page(idx)
                        event.accept()
                        return

            if self.controls_opacity > 0.4:
                rects = self._button_rects()
                for i, r in enumerate(rects):
                    if r.contains(pos):
                        if i == 0:
                            self.showMinimized()
                        elif i == 1:
                            if self.windowState() & (
                                Qt.WindowMaximized | Qt.WindowFullScreen
                            ):
                                self.showNormal()
                            else:
                                self.showMaximized()
                        else:
                            self._shutdown()
                        event.accept()
                        return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        self.win_w = self.width()
        self.win_h = self.height()
        for page in self.pages:
            page.resize(self.win_w, self.win_h)
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Q):
            self._shutdown()
        elif event.key() == Qt.Key_F:
            if self.windowState() & Qt.WindowFullScreen:
                self.showNormal()
            else:
                self.showFullScreen()

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

    # 清理上次更新替换后遗留的备份 exe（Commemorate.exe.old）
    try:
        old_backup = Path(sys.executable).with_name(
            Path(sys.executable).name + ".old"
        )
        if old_backup.exists():
            old_backup.unlink()
    except Exception:
        pass

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
                    update_mgr.install_update(filepath)
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
                # 更新已替换完成：本地版本号同步为新版本，避免重启后重复提示；
                # 不自动退出，面板底部红色提示由用户手动关闭应用后重新打开
                config.app_version = preflight["latest"]
                config.save()
            # 失败/取消：面板显示错误，用户可点击“重试更新”或关闭退出

    login.login_ok.connect(on_login_ok)

    # ---- 后台线程同步（不阻塞 UI） ----
    debug_mode = "--debug" in args
    if debug_mode:
        # 调试模式：跳过登录与同步，直接进入主窗口
        finalize_sync({"success": True, "sync_errors": [], "preflight": None})
    elif config.sync_auto_pull and "--skip-sync" not in args:
        # 等登录窗口出现后再启动同步，避免启动过早导致网络请求失败
        QTimer.singleShot(500, start_sync_thread)
    else:
        # 跳过同步：使用本地缓存，直接视为同步成功
        finalize_sync({"success": True, "sync_errors": [], "preflight": None})

    # ---- 登录（必须等待同步成功；同步期间按钮禁用） ----
    if not debug_mode and login.exec_() != LoginWindow.Accepted:
        stop_sync_thread()
        window._shutdown()
        sys.exit(0)

    # ---- 主窗口正式显示 ----
    window.refresh_from_config()
    window.show()
    window.raise_()
    sys.exit(app.exec_())
