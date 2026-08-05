# -*- coding: utf-8 -*-
"""
可复用的条形切换器 — BarSelector
================================
一排高密度竖线（|||||||||||），每条竖线代表一个条目（如某个纪念日）：
- 当前项：高亮 + 加长，上方常显文字；
- 悬停项：变长并显示文字；
- 常态隐藏（透明度 0），鼠标靠近区域才浮现，浮出后才响应
  滚轮、左右拖动、点击竖线 等交互；
- 通过 on_change 回调通知外部，不依赖具体页面，可放在任意位置复用。

纯绘制 + 命中检测组件（不创建 QWidget），由宿主页面负责 paint / 事件路由。
"""

import math

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QBrush, QFontMetrics


class BarSelector:
    """竖线样式的内容切换器（高密度、常态隐藏、靠近浮现）"""

    def __init__(self, max_visible=13, spacing=30, base_len=14, current_len=26,
                 hover_len=40, bar_w=2, accent=(150, 200, 255), on_change=None,
                 near_margin=40):
        self.max_visible = max(3, max_visible)
        self.spacing = spacing
        self.base_len = base_len
        self.current_len = current_len
        self.hover_len = hover_len
        self.bar_w = bar_w
        self.accent = accent
        self.on_change = on_change
        self.near_margin = near_margin

        self.items = []              # [{"key": ..., "label": ...}, ...]
        self.current = 0
        self._hover = -1
        self._near = False           # 鼠标是否靠近区域
        self._opacity = 0.0
        self._lens = {}              # 条目序号 -> 当前竖线长度（平滑动画）
        self._rect = QRectF()        # 组件占用区域
        self._bar_rects = []         # [(条目序号, 命中矩形)]
        self._drag = None

    # ---------- 数据 ----------

    def set_items(self, items, current=0):
        """items: [{"key":..., "label":...}, ...]"""
        self.items = list(items or [])
        self._lens = {}
        self._hover = -1
        self.set_current(current)

    def set_current(self, idx):
        n = len(self.items)
        self.current = 0 if n == 0 else max(0, min(n - 1, idx))
        self._lens = {}

    def set_rect(self, rect):
        self._rect = QRectF(rect)

    def is_inside(self, pos) -> bool:
        return self._rect.contains(pos)

    # ---------- 鼠标靠近 / 悬停 ----------

    def update_mouse(self, pos):
        """宿主每帧把鼠标位置喂进来，控制浮现与隐藏"""
        if pos is None:
            self._near = False
        else:
            self._near = self._rect.adjusted(
                -self.near_margin, -self.near_margin,
                self.near_margin, self.near_margin).contains(pos)
        if not self._near:
            self._hover = -1

    def update_hover(self, pos):
        if not self._near:
            return
        self._hover = -1
        for idx, rect in self._hit_rects_now():
            if rect.contains(pos):
                self._hover = idx
                return

    def _hit_rects_now(self):
        """按当前布局实时计算每条竖线的命中矩形（不依赖绘制时机）"""
        yc = self._rect.center().y()
        out = []
        for idx, x, _ in self._bar_positions():
            out.append((idx, QRectF(x - 14, yc - 12, 28, 24)))
        return out

    # ---------- 布局 ----------

    def _visible_range(self):
        n = len(self.items)
        if n == 0:
            return []
        lo = max(0, self.current - self.max_visible // 2)
        lo = max(0, min(lo, n - self.max_visible))
        hi = min(n, lo + self.max_visible)
        return list(range(lo, hi))

    def _bar_positions(self):
        idxs = self._visible_range()
        cy = self._rect.center().y()
        total = (len(idxs) - 1) * self.spacing
        x0 = self._rect.center().x() - total / 2
        return [(idx, x0 + i * self.spacing, cy) for i, idx in enumerate(idxs)]

    # ---------- 事件（只有靠近时响应） ----------

    def on_wheel(self, dy, pos) -> bool:
        if not self._near or not self.items:
            return False
        if dy:
            self._step(1 if dy < 0 else -1)
        return True

    def on_press(self, pos) -> bool:
        if not self._near or not self.items or not self.is_inside(pos):
            return False
        self._drag = {"acc": 0.0, "last": pos.x(), "moved": False}
        return True

    def on_move(self, pos, buttons) -> bool:
        if self._drag is not None and (buttons & Qt.LeftButton):
            dx = pos.x() - self._drag["last"]
            self._drag["last"] = pos.x()
            self._drag["acc"] += dx
            if abs(self._drag["acc"]) > 6:
                self._drag["moved"] = True
            while self._drag["acc"] >= 50:
                self._step(1)
                self._drag["acc"] -= 50
            while self._drag["acc"] <= -50:
                self._step(-1)
                self._drag["acc"] += 50
            return True
        return False

    def on_release(self, pos) -> bool:
        if not self._near or not self.items:
            return False
        if self._drag is not None:
            drag = self._drag
            self._drag = None
            if drag["moved"]:
                return True  # 是拖动，不是点击
            # 按下后没有拖动 = 点击：命中竖线则切换
            for idx, rect in self._hit_rects_now():
                if rect.contains(pos):
                    self._jump(idx)
                    return True
            return True
        for idx, rect in self._hit_rects_now():
            if rect.contains(pos):
                self._jump(idx)
                return True
        return False

    def _step(self, delta):
        if not self.items:
            return
        self._jump((self.current + delta) % len(self.items))

    def _jump(self, idx):
        n = len(self.items)
        if n == 0:
            return
        idx = max(0, min(n - 1, idx))
        if idx == self.current:
            return
        self.current = idx
        self._lens = {}
        if self.on_change:
            self.on_change(idx)

    # ---------- 动画 ----------

    def tick(self):
        if not self.items:
            return
        if self._near:
            self._opacity = min(0.95, self._opacity + 0.08)
        else:
            self._opacity = max(0.0, self._opacity - 0.06)
        if self._opacity <= 0.02:
            self._lens = {}
            return
        hovered = self._hover
        for idx in self._visible_range():
            if hovered >= 0:
                factor = math.exp(-((idx - hovered) ** 2) / (2 * 1.15 * 1.15))
                target = self.base_len + (self.hover_len - self.base_len) * factor
            else:
                target = float(self.base_len)
            if idx == self.current:
                target = max(target, self.current_len)
            cur = self._lens.get(idx, float(self.base_len))
            self._lens[idx] = cur + (target - cur) * 0.16

    # ---------- 绘制 ----------

    def paint(self, painter: QPainter):
        if not self.items or self._opacity <= 0.02:
            return
        alpha = int(255 * self._opacity)
        positions = self._bar_positions()
        if not positions:
            return

        self._bar_rects = []
        ar, ag, ab = self.accent
        for idx, x, yc in positions:
            length = self._lens.get(idx, float(self.base_len))
            current = (idx == self.current)
            hover = (idx == self._hover)
            if current:
                col = QColor(ar, ag, ab, alpha)
            elif hover:
                col = QColor(min(255, ar + 45), min(255, ag + 45), min(255, ab + 45), alpha)
            else:
                col = QColor(205, 198, 220, int(alpha * 0.65))
            pen = QPen(col, self.bar_w)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(x, yc - length / 2), QPointF(x, yc + length / 2))
            self._bar_rects.append((idx, QRectF(x - 14, yc - 12, 28, 24)))

            # 仅悬停时上方显示文字（当前项不常显标题）
            if hover:
                label = (self.items[idx].get("label") or "").strip()
                if label:
                    font = QFont("Microsoft YaHei", 10, QFont.Bold if current else QFont.Normal)
                    painter.setFont(font)
                    fm = QFontMetrics(font)
                    lw = fm.horizontalAdvance(label) + 16
                    lrect = QRectF(x - lw / 2, yc - length / 2 - 24, lw, 20)
                    # 无背景无边框，仅文字 + 轻投影保证可读
                    painter.setPen(QColor(0, 0, 10, int(alpha * 0.9)))
                    painter.drawText(lrect.translated(1, 1), Qt.AlignCenter, label)
                    painter.setPen(QColor(235, 246, 255, alpha))
                    painter.drawText(lrect, Qt.AlignCenter, label)
