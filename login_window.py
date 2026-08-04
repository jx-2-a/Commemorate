"""
LoginWindow — 登录前置窗口
支持本地密码验证和远程 API 验证两种模式
"""
import sys
import math
import json

from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal, QUrl
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QRadialGradient, QLinearGradient,
    QPen, QBrush, QPainterPath, QFontMetrics, QIcon, QPixmap
)
from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QCheckBox, QPushButton,
    QLabel, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect,
    QApplication
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from app_config import ConfigManager, verify_password, hash_password


# ── 样式常量 ───────────────────────────────────────────────

BG_TOP = QColor(5, 2, 20)
BG_MID = QColor(18, 8, 40)
BG_BOT = QColor(30, 10, 50)
ACCENT_PINK = QColor(255, 140, 180)
TEXT_LIGHT = QColor(255, 240, 245)
TEXT_MUTED = QColor(200, 180, 210)
INPUT_BG = QColor(30, 15, 50, 200)
INPUT_BORDER = QColor(120, 80, 140)
INPUT_FOCUS = QColor(255, 140, 180)
BTN_GRAD_TOP = QColor(220, 80, 130)
BTN_GRAD_BOT = QColor(160, 40, 80)
ERROR_COLOR = QColor(255, 110, 130)


class ShakeableLineEdit(QLineEdit):
    """支持抖动动画的输入框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shake_offset = 0.0

    def _get_shake(self):
        return self._shake_offset

    def _set_shake(self, value):
        self._shake_offset = value

    shake_offset = pyqtProperty(float, _get_shake, _set_shake)

    def shake(self):
        """播放抖动动画"""
        self._anim = QPropertyAnimation(self, b"shake_offset")
        self._anim.setDuration(400)
        self._anim.setEasingCurve(QEasingCurve.OutElastic)
        self._anim.setStartValue(0.0)
        keys = [(0.1, -4.0), (0.2, 4.0), (0.3, -3.0), (0.4, 3.0),
                (0.5, -2.0), (0.6, 2.0), (0.7, -1.0), (0.8, 1.0),
                (0.9, -0.5), (1.0, 0.0)]
        for t, v in keys:
            self._anim.setKeyValueAt(t, v)
        self._anim.start()


class CircleIconButton(QPushButton):
    """圆形图标按钮：用 QPainter 绘制 ✕ / ↻，不受字体渲染影响，不会裁切"""

    def __init__(self, kind="close", parent=None):
        super().__init__(parent)
        self._kind = kind  # "close" 或 "refresh"
        self._hovered = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(34, 34)
        # 去掉 QPushButton 默认背景，只保留 QPainter 绘制的内容
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        if self._hovered:
            bg = QColor(230, 60, 80, 220) if self._kind == "close" else QColor(255, 140, 180, 210)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(bg))
            painter.drawEllipse(QPointF(cx, cy), w / 2 - 0.5, h / 2 - 0.5)

        color = QColor(255, 255, 255) if self._hovered else QColor(200, 180, 210, 150)
        pen = QPen(color, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if self._kind == "close":
            m = 9.5
            painter.drawLine(QPointF(m, m), QPointF(w - m, h - m))
            painter.drawLine(QPointF(w - m, m), QPointF(m, h - m))
        else:
            self._paint_refresh(painter, w, h)
        painter.end()

    def _paint_refresh(self, painter, w, h):
        cx, cy = w / 2, h / 2
        r = w / 2 - 6
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)
        # 顺时针弧（负跨度），留出顶部缺口放箭头
        painter.drawArc(rect, 390 * 16, -300 * 16)
        # 箭头在弧末端（顶部），指向顺时针方向（右侧）
        ex, ey = cx, cy - r
        L = 5.5
        for ang in (-0.6, 0.6):
            tip_x = ex + L * math.cos(ang)
            tip_y = ey + L * math.sin(ang)
            painter.drawLine(QPointF(ex, ey), QPointF(tip_x, tip_y))


class LoginWindow(QDialog):
    """登录前置窗口"""

    retry_sync = pyqtSignal()

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self._auth_result = False
        self._error_alpha = 0.0
        self._fade_in = 0.0
        self._error_timer = QTimer(self)
        self._error_timer.timeout.connect(self._fade_error)

        # 窗口属性
        self.setWindowTitle(f"{config.app_name} - Login")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Dialog
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(420, 520)
        self._center_on_screen()
        self._message_color = ERROR_COLOR
        self._sync_ready = False
        self._sync_status = "正在同步用户信息，请稍候…"

        self._setup_ui()
        self._apply_styles()

        # 登录前需要等待后台同步成功，按钮先禁用
        self.login_btn.setEnabled(False)
        self.register_btn.setEnabled(False)

        # 淡入动画
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._tick_fade)
        self._fade_timer.start(16)

        # 恢复"记住我"
        if config.remember_me and config.remembered_username:
            self.username_input.setText(config.remembered_username)
            self.remember_check.setChecked(True)

    # ── 窗口居中 ────────────────────────────────────────

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    # ── UI 构建 ─────────────────────────────────────────

    def _setup_ui(self):
        # 标题区域
        self.title_label = QLabel("✦  Commemorate  ✦", self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setGeometry(0, 60, 420, 50)

        self.subtitle_label = QLabel("— 珍藏每一刻 —", self)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setGeometry(0, 110, 420, 30)

        # 装饰分隔线
        self.divider_label = QLabel(self)
        self.divider_label.setGeometry(80, 150, 260, 2)

        # 用户名输入框
        self.username_input = ShakeableLineEdit(self)
        self.username_input.setPlaceholderText("用户名")
        self.username_input.setGeometry(70, 180, 280, 42)
        self.username_input.setAlignment(Qt.AlignCenter)
        self._add_shadow(self.username_input)

        # 密码输入框
        self.password_input = ShakeableLineEdit(self)
        self.password_input.setPlaceholderText("密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setGeometry(70, 235, 280, 42)
        self.password_input.setAlignment(Qt.AlignCenter)
        self.password_input.returnPressed.connect(self._attempt_login)
        self._add_shadow(self.password_input)

        # 记住我
        self.remember_check = QCheckBox("记住我", self)
        self.remember_check.setGeometry(75, 290, 100, 25)

        # 登录按钮
        self.login_btn = QPushButton("登  录", self)
        self.login_btn.setGeometry(70, 335, 280, 44)
        self.login_btn.clicked.connect(self._attempt_login)
        self._add_shadow(self.login_btn)

        # 错误提示标签
        self.error_label = QLabel(self)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setGeometry(70, 395, 280, 30)
        self.error_label.setVisible(False)

        # 注册新账号
        self.register_btn = QPushButton("注册新账号", self)
        self.register_btn.setGeometry(70, 430, 280, 34)
        self.register_btn.setCursor(Qt.PointingHandCursor)
        self.register_btn.clicked.connect(self._open_register)

        # 关闭按钮（右上角圆形 ×，悬停变红）
        self.close_btn = CircleIconButton("close", self)
        self.close_btn.setGeometry(378, 11, 34, 34)
        self.close_btn.clicked.connect(self.reject)

        # 刷新按钮（同步失败时出现，点击重试后台同步）
        self.refresh_btn = CircleIconButton("refresh", self)
        self.refresh_btn.setGeometry(338, 11, 34, 34)
        self.refresh_btn.setToolTip("重新同步")
        self.refresh_btn.clicked.connect(lambda: self.retry_sync.emit())
        self.refresh_btn.setVisible(False)

    # ── 阴影效果 ────────────────────────────────────────

    def _add_shadow(self, widget):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(255, 120, 180, 60))
        widget.setGraphicsEffect(shadow)

    # ── 样式 ────────────────────────────────────────────

    def _apply_styles(self):
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_LIGHT.name()};
                font-family: "Microsoft YaHei";
                font-size: 26px;
                font-weight: bold;
                background: transparent;
            }}
        """)
        self.subtitle_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_MUTED.name()};
                font-family: "Microsoft YaHei";
                font-size: 13px;
                background: transparent;
                font-style: italic;
            }}
        """)
        self.divider_label.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(120,80,140,0),
                    stop:0.3 rgba(255,140,180,100),
                    stop:0.5 rgba(255,140,180,160),
                    stop:0.7 rgba(255,140,180,100),
                    stop:1 rgba(120,80,140,0));
                border: none;
            }}
        """)
        input_style = f"""
            QLineEdit {{
                background: rgba(30, 15, 50, 180);
                color: {TEXT_LIGHT.name()};
                font-family: "Microsoft YaHei";
                font-size: 15px;
                border: 1.5px solid {INPUT_BORDER.name()};
                border-radius: 10px;
                padding: 6px 16px;
            }}
            QLineEdit:focus {{
                border-color: {INPUT_FOCUS.name()};
                background: rgba(40, 20, 60, 200);
            }}
            QLineEdit::placeholder {{
                color: rgba(200, 180, 210, 100);
            }}
        """
        self.username_input.setStyleSheet(input_style)
        self.password_input.setStyleSheet(input_style)

        self.remember_check.setStyleSheet(f"""
            QCheckBox {{
                color: {TEXT_MUTED.name()};
                font-family: "Microsoft YaHei";
                font-size: 12px;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1.5px solid {INPUT_BORDER.name()};
                border-radius: 4px;
                background: rgba(30, 15, 50, 150);
            }}
            QCheckBox::indicator:checked {{
                background: {ACCENT_PINK.name()};
                border-color: {ACCENT_PINK.name()};
            }}
        """)

        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                color: white;
                font-family: "Microsoft YaHei";
                font-size: 17px;
                font-weight: bold;
                border: none;
                border-radius: 22px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {BTN_GRAD_TOP.name()},
                    stop:1 {BTN_GRAD_BOT.name()});
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(240,100,150,255),
                    stop:1 rgba(180,50,90,255));
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(180,50,90,255),
                    stop:1 rgba(130,20,50,255));
            }}
        """)

        self.error_label.setStyleSheet(f"""
            QLabel {{
                color: {ERROR_COLOR.name()};
                font-family: "Microsoft YaHei";
                font-size: 12px;
                background: transparent;
            }}
        """)

        self.register_btn.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT_MUTED.name()};
                font-family: "Microsoft YaHei";
                font-size: 13px;
                border: 1.5px solid rgba(120, 80, 140, 160);
                border-radius: 17px;
                background: rgba(30, 15, 50, 140);
            }}
            QPushButton:hover {{
                color: {ACCENT_PINK.name()};
                border-color: {ACCENT_PINK.name()};
                background: rgba(60, 30, 80, 160);
            }}
        """)

    # ── 绘制背景 ────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # 背景渐变
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, BG_TOP)
        bg.setColorAt(0.4, BG_MID)
        bg.setColorAt(1.0, BG_BOT)
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(2, 2, w - 4, h - 4, 24, 24)

        # 顶部光晕
        glow = QRadialGradient(w / 2, 60, 200)
        gc = QColor(255, 140, 180, int(40 * self._fade_in))
        gc0 = QColor(255, 140, 180, 0)
        glow.setColorAt(0.0, gc)
        glow.setColorAt(1.0, gc0)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(w / 2, 60), 200, 120)

        # 边框微光
        border_c = QColor(180, 140, 200, int(60 * self._fade_in))
        painter.setPen(QPen(border_c, 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(3, 3, w - 6, h - 6, 23, 23)

        # 底部装饰线
        painter.setPen(QPen(QColor(180, 140, 200, int(30 * self._fade_in)), 1))
        painter.drawLine(100, 470, w - 100, 470)

        painter.end()

    # ── 淡入 ────────────────────────────────────────────

    def _tick_fade(self):
        if self._fade_in < 1.0:
            self._fade_in = min(1.0, self._fade_in + 0.04)
            self.update()
        else:
            self._fade_timer.stop()

    # ── 错误提示淡出 ────────────────────────────────────

    def _fade_error(self):
        if self._error_alpha > 0.01:
            self._error_alpha *= 0.85
            c = self._message_color
            self.error_label.setStyleSheet(f"""
                QLabel {{
                    color: rgba({c.red()}, {c.green()}, {c.blue()}, {int(255 * self._error_alpha)});
                    font-family: "Microsoft YaHei";
                    font-size: 12px;
                    background: transparent;
                }}
            """)
        else:
            self._error_alpha = 0.0
            self.error_label.setVisible(False)
            self._error_timer.stop()

    def _show_error(self, message):
        """显示错误消息并抖动输入框"""
        self._message_color = ERROR_COLOR
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self._error_alpha = 1.0
        self._error_timer.stop()
        self._error_timer.start(50)
        self.username_input.shake()
        self.password_input.shake()

    def _show_info(self, message):
        """显示成功提示（粉色，不抖动）"""
        self._message_color = ACCENT_PINK
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self._error_alpha = 1.0
        self._error_timer.stop()
        self._error_timer.start(50)

    # ── 登录逻辑 ────────────────────────────────────────

    def _open_register(self):
        if not self._sync_ready:
            # 保持同步状态提示，只抖动输入框，不触发淡出
            self._error_timer.stop()
            self.username_input.shake()
            return
        dlg = RegisterDialog(self.config, self)
        if dlg.exec_() == RegisterDialog.Accepted:
            self.username_input.setText(dlg.username())
            self.password_input.clear()
            self.password_input.setFocus()
            self._show_info("注册成功，请登录")

    def _attempt_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not self._sync_ready:
            # 保持“同步中 / 同步失败”的持久提示，只抖动输入框，不触发淡出
            self._error_timer.stop()
            self.username_input.shake()
            self.password_input.shake()
            return

        if not username or not password:
            self._show_error("请输入用户名和密码")
            return

        mode = self.config.auth_mode

        if mode == "local":
            self._local_auth(username, password)
        elif mode == "remote":
            self._remote_auth(username, password)
        else:
            self._show_error(f"未知的认证模式: {mode}")

    def _local_auth(self, username, password):
        """本地密码验证"""
        users = self.config.all_users()
        matched = None
        for u in users:
            if u.get("username") == username:
                matched = u
                break

        if matched is None:
            self._show_error("用户名或密码错误")
            return

        stored_hash = matched.get("password_hash", "")
        if verify_password(password, stored_hash):
            self._on_login_success(username)
        else:
            self._show_error("用户名或密码错误")

    def _remote_auth(self, username, password):
        """远程 API 验证"""
        url = self.config.auth_api_url
        if not url:
            self._show_error("未配置认证服务器地址")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("验证中...")

        manager = QNetworkAccessManager(self)
        request = QNetworkRequest()
        request.setUrl(QUrl(url))
        request.setHeader(request.ContentTypeHeader, "application/json")
        request.setTransferTimeout(self.config.auth_timeout * 1000)

        body = json.dumps({"username": username, "password": password}).encode("utf-8")
        reply = manager.post(request, body)

        def on_finished():
            self.login_btn.setEnabled(True)
            self.login_btn.setText("登  录")
            if reply.error() != QNetworkReply.NoError:
                self._show_error(f"网络错误: {reply.errorString()}")
                reply.deleteLater()
                return

            try:
                data = json.loads(reply.readAll().data().decode("utf-8"))
                if data.get("success"):
                    self._on_login_success(username)
                else:
                    self._show_error(data.get("message", "用户名或密码错误"))
            except Exception as e:
                self._show_error(f"服务器响应异常: {e}")
            reply.deleteLater()

        reply.finished.connect(on_finished)

    def _on_login_success(self, username):
        """登录成功"""
        self._auth_result = True
        self._login_username = username
        self._login_password = self.password_input.text()
        self.config.save_remember_me(username, self.remember_check.isChecked())
        self.accept()

    def username(self):
        """最近一次登录成功的用户名"""
        return getattr(self, "_login_username", "")

    def password(self):
        """最近一次登录成功的密码（用于更新重启后自动登录）"""
        return getattr(self, "_login_password", "")

    def update_sync_state(self, state):
        """登录前同步状态：syncing / ready / failed"""
        self._error_timer.stop()
        if state == "ready":
            self._sync_ready = True
            self.login_btn.setEnabled(True)
            self.register_btn.setEnabled(True)
            self.error_label.setVisible(False)
            self.refresh_btn.setVisible(False)
            return

        self._sync_ready = False
        self.login_btn.setEnabled(False)
        self.register_btn.setEnabled(False)
        if state == "syncing":
            self._sync_status = "正在同步用户信息，请稍候…"
            color = TEXT_MUTED
            self.refresh_btn.setVisible(False)
        else:  # failed
            self._sync_status = "用户信息同步失败，请检查网络后点击刷新重试"
            color = ERROR_COLOR
            self.refresh_btn.setVisible(True)
        self.error_label.setText(self._sync_status)
        self.error_label.setStyleSheet(f"""
            QLabel {{
                color: {color.name()};
                font-family: "Microsoft YaHei";
                font-size: 12px;
                background: transparent;
            }}
        """)
        self.error_label.setVisible(True)

    def auto_login(self, username, password):
        """更新重启后自动登录，直接进入主流程"""
        self._login_username = username
        self._login_password = password
        self._auth_result = True
        self.accept()

    # ── 鼠标事件（拖拽窗口 & 关闭按钮）──────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 点击输入框之外的区域：取消输入框焦点
            self.username_input.clearFocus()
            self.password_input.clearFocus()
            self._drag_start = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_start') and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_start)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


# ============================================================
#  RegisterDialog — 注册新账号
# ============================================================

class RegisterDialog(QDialog):
    """注册新账号（受远程设置 allow_register / max_users 控制）"""

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self._registered_username = ""
        self._error_alpha = 0.0
        self._fade_in = 0.0

        self.setWindowTitle("注册新账号")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Dialog
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(420, 460)
        self._center_on_screen()

        self._setup_ui()
        self._apply_styles()

        self._error_timer = QTimer(self)
        self._error_timer.timeout.connect(self._fade_error)
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._tick_fade)
        self._fade_timer.start(16)

    def username(self):
        return self._registered_username

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _setup_ui(self):
        self.title_label = QLabel("✦  注册新账号  ✦", self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setGeometry(0, 50, 420, 45)

        self.username_input = ShakeableLineEdit(self)
        self.username_input.setPlaceholderText("用户名")
        self.username_input.setGeometry(70, 135, 280, 42)
        self.username_input.setAlignment(Qt.AlignCenter)

        self.password_input = ShakeableLineEdit(self)
        self.password_input.setPlaceholderText("密码（至少 4 位）")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setGeometry(70, 190, 280, 42)
        self.password_input.setAlignment(Qt.AlignCenter)

        self.confirm_input = ShakeableLineEdit(self)
        self.confirm_input.setPlaceholderText("确认密码")
        self.confirm_input.setEchoMode(QLineEdit.Password)
        self.confirm_input.setGeometry(70, 245, 280, 42)
        self.confirm_input.setAlignment(Qt.AlignCenter)
        self.confirm_input.returnPressed.connect(self._do_register)

        self.register_btn = QPushButton("注  册", self)
        self.register_btn.setGeometry(70, 320, 280, 44)
        self.register_btn.setCursor(Qt.PointingHandCursor)
        self.register_btn.clicked.connect(self._do_register)

        self.error_label = QLabel(self)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setGeometry(70, 385, 280, 30)
        self.error_label.setVisible(False)

        self.close_btn = CircleIconButton("close", self)
        self.close_btn.setGeometry(378, 11, 34, 34)
        self.close_btn.clicked.connect(self.reject)

    def _apply_styles(self):
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_LIGHT.name()};
                font-family: "Microsoft YaHei";
                font-size: 22px;
                font-weight: bold;
                background: transparent;
            }}
        """)
        input_style = f"""
            QLineEdit {{
                background: rgba(30, 15, 50, 180);
                color: {TEXT_LIGHT.name()};
                font-family: "Microsoft YaHei";
                font-size: 15px;
                border: 1.5px solid {INPUT_BORDER.name()};
                border-radius: 10px;
                padding: 6px 16px;
            }}
            QLineEdit:focus {{
                border-color: {INPUT_FOCUS.name()};
                background: rgba(40, 20, 60, 200);
            }}
            QLineEdit::placeholder {{
                color: rgba(200, 180, 210, 100);
            }}
        """
        self.username_input.setStyleSheet(input_style)
        self.password_input.setStyleSheet(input_style)
        self.confirm_input.setStyleSheet(input_style)

        self.register_btn.setStyleSheet(f"""
            QPushButton {{
                color: white;
                font-family: "Microsoft YaHei";
                font-size: 17px;
                font-weight: bold;
                border: none;
                border-radius: 22px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {BTN_GRAD_TOP.name()},
                    stop:1 {BTN_GRAD_BOT.name()});
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(240,100,150,255),
                    stop:1 rgba(180,50,90,255));
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(180,50,90,255),
                    stop:1 rgba(130,20,50,255));
            }}
        """)

        self.error_label.setStyleSheet(f"""
            QLabel {{
                color: {ERROR_COLOR.name()};
                font-family: "Microsoft YaHei";
                font-size: 12px;
                background: transparent;
            }}
        """)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, BG_TOP)
        bg.setColorAt(0.4, BG_MID)
        bg.setColorAt(1.0, BG_BOT)
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(2, 2, w - 4, h - 4, 24, 24)

        glow = QRadialGradient(w / 2, 60, 200)
        gc = QColor(255, 140, 180, int(40 * self._fade_in))
        glow.setColorAt(0.0, gc)
        glow.setColorAt(1.0, QColor(255, 140, 180, 0))
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(w / 2, 60), 200, 120)

        border_c = QColor(180, 140, 200, int(60 * self._fade_in))
        painter.setPen(QPen(border_c, 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(3, 3, w - 6, h - 6, 23, 23)
        painter.end()

    def _tick_fade(self):
        if self._fade_in < 1.0:
            self._fade_in = min(1.0, self._fade_in + 0.04)
            self.update()
        else:
            self._fade_timer.stop()

    def _fade_error(self):
        if self._error_alpha > 0.01:
            self._error_alpha *= 0.85
            self.error_label.setStyleSheet(f"""
                QLabel {{
                    color: rgba(255, 110, 130, {int(255 * self._error_alpha)});
                    font-family: "Microsoft YaHei";
                    font-size: 12px;
                    background: transparent;
                }}
            """)
        else:
            self._error_alpha = 0.0
            self.error_label.setVisible(False)
            self._error_timer.stop()

    def _show_error(self, message):
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self._error_alpha = 1.0
        self._error_timer.stop()
        self._error_timer.start(50)
        self.username_input.shake()
        self.password_input.shake()
        self.confirm_input.shake()

    def _do_register(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()

        if not username or not password:
            self._show_error("请输入用户名和密码")
            return
        if len(password) < 4:
            self._show_error("密码至少需要 4 位")
            return
        if password != confirm:
            self._show_error("两次输入的密码不一致")
            return
        if not self.config.auth_allow_register:
            self._show_error("暂未开放注册")
            return

        users = self.config.all_users()
        if any(u.get("username") == username for u in users):
            self._show_error("该用户名已存在")
            return
        if len(users) >= self.config.auth_max_users:
            self._show_error(f"用户数量已达上限（{self.config.auth_max_users} 个）")
            return

        self.config.add_registered_user(username, hash_password(password))
        self._registered_username = username
        self.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 点击输入框之外的区域：取消输入框焦点
            self.username_input.clearFocus()
            self.password_input.clearFocus()
            self.confirm_input.clearFocus()
            self._drag_start = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_start') and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_start)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
