"""
LoginWindow — 登录前置窗口
支持本地密码验证和远程 API 验证两种模式
"""
import sys
import math
import json
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QPointF, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal, QUrl
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QRadialGradient, QLinearGradient,
    QPen, QBrush, QPainterPath, QFontMetrics, QIcon, QPixmap
)
from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QCheckBox, QPushButton,
    QLabel, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect,
    QApplication, QProgressBar, QFileDialog
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


class LoginWindow(QDialog):
    """登录前置窗口"""

    retry_sync = pyqtSignal()
    login_ok = pyqtSignal(str, str)   # username, password
    update_action = pyqtSignal(str)   # "start" / "close"

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
        self._page = "login"   # "login" 或 "register"
        self._update_panel_visible = False
        self._update_active = False   # 正在下载/安装中
        self._hold_ticks = 0   # 提示保持全亮的时间（50ms 一帧）

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
        self.password_input.returnPressed.connect(self._on_submit)
        self._add_shadow(self.password_input)

        # 确认密码输入框（注册页使用，默认隐藏）
        self.confirm_input = ShakeableLineEdit(self)
        self.confirm_input.setPlaceholderText("确认密码")
        self.confirm_input.setEchoMode(QLineEdit.Password)
        self.confirm_input.setAlignment(Qt.AlignCenter)
        self.confirm_input.returnPressed.connect(self._do_register)
        self.confirm_input.setVisible(False)
        self._add_shadow(self.confirm_input)

        # 记住我
        self.remember_check = QCheckBox("记住我", self)
        self.remember_check.setGeometry(75, 290, 100, 25)

        # 登录按钮
        self.login_btn = QPushButton("登  录", self)
        self.login_btn.setGeometry(70, 335, 280, 44)
        self.login_btn.clicked.connect(self._on_submit)
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
        self.register_btn.clicked.connect(self._show_register_page)

        # 返回按钮（注册页左上角 ←，点击回到登录页）
        self.back_btn = QPushButton("❮", self)
        self.back_btn.setGeometry(12, 11, 34, 34)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setFocusPolicy(Qt.NoFocus)
        # self.back_btn.setToolTip("返回登录")
        self.back_btn.clicked.connect(self._show_login_page)
        self.back_btn.setVisible(False)

        # 关闭按钮（右上角圆形 ×，悬停变红）
        self.close_btn = QPushButton("✕", self)
        self.close_btn.setGeometry(378, 11, 34, 34)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFocusPolicy(Qt.NoFocus)
        self.close_btn.clicked.connect(self._on_close_clicked)

        # 刷新按钮（同步失败时出现，点击重试后台同步）
        self.refresh_btn = QPushButton("↻", self)
        self.refresh_btn.setGeometry(338, 11, 34, 34)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setFocusPolicy(Qt.NoFocus)
        self.refresh_btn.setToolTip("重新同步")
        self.refresh_btn.clicked.connect(lambda: self.retry_sync.emit())
        self.refresh_btn.setVisible(False)

        # ── 连接设置 ────────────────────────────────────
        # 登录页底部入口按钮
        self.settings_btn = QPushButton("⚙ 连接设置", self)
        self.settings_btn.setGeometry(70, 470, 280, 26)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setFocusPolicy(Qt.NoFocus)
        self.settings_btn.clicked.connect(self._show_settings_page)

        # 设置页输入项（token + 私有仓库，加密保存，不随远程同步）
        self.conn_owner_input = ShakeableLineEdit(self)
        self.conn_owner_input.setPlaceholderText("仓库所有者（GitHub 用户名）")
        self.conn_owner_input.setGeometry(70, 138, 280, 36)
        self.conn_owner_input.setAlignment(Qt.AlignCenter)
        self._add_shadow(self.conn_owner_input)

        self.conn_repo_input = ShakeableLineEdit(self)
        self.conn_repo_input.setPlaceholderText("数据仓库名")
        self.conn_repo_input.setGeometry(70, 180, 280, 36)
        self.conn_repo_input.setAlignment(Qt.AlignCenter)
        self._add_shadow(self.conn_repo_input)

        self.conn_branch_input = ShakeableLineEdit(self)
        self.conn_branch_input.setPlaceholderText("分支（默认 main）")
        self.conn_branch_input.setText("main")
        self.conn_branch_input.setGeometry(70, 222, 280, 36)
        self.conn_branch_input.setAlignment(Qt.AlignCenter)
        self._add_shadow(self.conn_branch_input)

        self.conn_token_input = ShakeableLineEdit(self)
        self.conn_token_input.setPlaceholderText("GitHub Token（仅本机加密保存）")
        self.conn_token_input.setEchoMode(QLineEdit.Password)
        self.conn_token_input.setGeometry(70, 264, 280, 36)
        self.conn_token_input.setAlignment(Qt.AlignCenter)
        self._add_shadow(self.conn_token_input)

        self.conn_pwd_input = ShakeableLineEdit(self)
        self.conn_pwd_input.setPlaceholderText("加密密码（发给好友时需告知）")
        self.conn_pwd_input.setEchoMode(QLineEdit.Password)
        self.conn_pwd_input.setGeometry(70, 306, 280, 36)
        self.conn_pwd_input.setAlignment(Qt.AlignCenter)
        self._add_shadow(self.conn_pwd_input)

        self.conn_status = QLabel("", self)
        self.conn_status.setAlignment(Qt.AlignCenter)
        self.conn_status.setGeometry(70, 348, 280, 24)

        self.save_conn_btn = QPushButton("保  存", self)
        self.save_conn_btn.setGeometry(70, 390, 88, 34)
        self.save_conn_btn.clicked.connect(self._save_connection)

        self.import_conn_btn = QPushButton("导入文件", self)
        self.import_conn_btn.setGeometry(166, 390, 88, 34)
        self.import_conn_btn.clicked.connect(self._import_connection)

        self.export_conn_btn = QPushButton("导出文件", self)
        self.export_conn_btn.setGeometry(262, 390, 88, 34)
        self.export_conn_btn.clicked.connect(self._export_connection)

        for w in (self.conn_owner_input, self.conn_repo_input,
                  self.conn_branch_input, self.conn_token_input,
                  self.conn_pwd_input, self.conn_status,
                  self.save_conn_btn, self.import_conn_btn,
                  self.export_conn_btn):
            w.setVisible(False)

        # ---- 更新面板（登录成功发现新版本时，替换登录表单显示在同一窗口）----
        self.upd_title = QLabel("发现新版本", self)
        self.upd_title.setAlignment(Qt.AlignCenter)
        self.upd_title.setGeometry(0, 165, 420, 34)

        self.upd_version = QLabel("", self)
        self.upd_version.setAlignment(Qt.AlignCenter)
        self.upd_version.setGeometry(0, 205, 420, 26)

        self.upd_changelog = QLabel("", self)
        self.upd_changelog.setAlignment(Qt.AlignCenter)
        self.upd_changelog.setWordWrap(True)
        self.upd_changelog.setGeometry(60, 238, 300, 60)

        self.update_btn = QPushButton("立即更新", self)
        self.update_btn.setGeometry(70, 315, 280, 44)
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setFocusPolicy(Qt.NoFocus)
        self.update_btn.clicked.connect(lambda: self.update_action.emit("start"))
        self._add_shadow(self.update_btn)

        self.upd_progress = QProgressBar(self)
        self.upd_progress.setGeometry(70, 375, 280, 16)
        self.upd_progress.setRange(0, 100)
        self.upd_progress.setValue(0)
        self.upd_progress.setTextVisible(True)

        self.upd_status = QLabel("", self)
        self.upd_status.setAlignment(Qt.AlignCenter)
        self.upd_status.setGeometry(60, 400, 300, 30)

        # 更新完成后的重启提示（按钮下方红色小字）
        self.upd_restart_hint = QLabel("", self)
        self.upd_restart_hint.setAlignment(Qt.AlignCenter)
        self.upd_restart_hint.setGeometry(60, 363, 300, 24)
        self.upd_restart_hint.setStyleSheet(f"""
            QLabel {{
                color: {ERROR_COLOR.name()};
                font-family: "Microsoft YaHei";
                font-size: 12px;
                background: transparent;
            }}
        """)

        self.cancel_update_btn = QPushButton("取消下载", self)
        self.cancel_update_btn.setGeometry(70, 435, 280, 32)
        self.cancel_update_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_update_btn.setFocusPolicy(Qt.NoFocus)
        self.cancel_update_btn.clicked.connect(lambda: self.update_action.emit("cancel"))

        self.skip_update_btn = QPushButton("本次跳过", self)
        self.skip_update_btn.setGeometry(70, 435, 280, 32)
        self.skip_update_btn.setCursor(Qt.PointingHandCursor)
        self.skip_update_btn.setFocusPolicy(Qt.NoFocus)
        self.skip_update_btn.clicked.connect(lambda: self.update_action.emit("skip"))

        self._hide_update_panel()

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
        self.confirm_input.setStyleSheet(input_style)
        self.conn_owner_input.setStyleSheet(input_style)
        self.conn_repo_input.setStyleSheet(input_style)
        self.conn_branch_input.setStyleSheet(input_style)
        self.conn_token_input.setStyleSheet(input_style)
        self.conn_pwd_input.setStyleSheet(input_style)

        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT_MUTED.name()};
                font-family: "Microsoft YaHei";
                font-size: 12px;
                border: none;
                background: transparent;
            }}
            QPushButton:hover {{ color: {ACCENT_PINK.name()}; }}
        """)
        conn_btn_style = f"""
            QPushButton {{
                color: {TEXT_LIGHT.name()};
                font-family: "Microsoft YaHei";
                font-size: 13px;
                border: 1.5px solid {INPUT_BORDER.name()};
                border-radius: 10px;
                background: rgba(40, 20, 60, 180);
            }}
            QPushButton:hover {{ border-color: {ACCENT_PINK.name()}; }}
        """
        self.save_conn_btn.setStyleSheet(conn_btn_style)
        self.import_conn_btn.setStyleSheet(conn_btn_style)
        self.export_conn_btn.setStyleSheet(conn_btn_style)
        self.conn_status.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_MUTED.name()};
                font-family: "Microsoft YaHei";
                font-size: 12px;
                background: transparent;
            }}
        """)

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

        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                color: rgba(200, 180, 210, 140);
                font-family: "Microsoft YaHei";
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 17px;
                padding: 0;
                background: transparent;
            }}
            QPushButton:hover {{
                color: white;
                background: rgba(230, 60, 80, 220);
            }}
            QPushButton:pressed {{
                background: rgba(190, 40, 60, 255);
            }}
        """)

        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                color: rgba(200, 180, 210, 140);
                font-family: "Microsoft YaHei";
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 17px;
                padding: 0;
                background: transparent;
            }}
            QPushButton:hover {{
                color: white;
                background: rgba(255, 140, 180, 210);
            }}
            QPushButton:pressed {{
                background: rgba(220, 90, 140, 255);
            }}
        """)

        self.back_btn.setStyleSheet(f"""
            QPushButton {{
                color: rgba(200, 180, 210, 140);
                font-family: "Microsoft YaHei";
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 17px;
                padding: 0;
                background: transparent;
            }}
            QPushButton:hover {{
                color: white;
                background: rgba(255, 140, 180, 210);
            }}
            QPushButton:pressed {{
                background: rgba(220, 90, 140, 255);
            }}
        """)

        self.upd_title.setStyleSheet(f"""
            QLabel {{
                color: {ACCENT_PINK.name()};
                font-family: "Microsoft YaHei";
                font-size: 20px;
                font-weight: bold;
                background: transparent;
            }}
        """)

        self.upd_version.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_LIGHT.name()};
                font-family: "Microsoft YaHei";
                font-size: 14px;
                background: transparent;
            }}
        """)

        self.upd_changelog.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_MUTED.name()};
                font-family: "Microsoft YaHei";
                font-size: 12px;
                background: transparent;
            }}
        """)

        self.update_btn.setStyleSheet(f"""
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
            QPushButton:disabled {{
                color: rgba(255, 240, 245, 160);
                background: rgba(120, 80, 140, 120);
            }}
        """)

        self.upd_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {INPUT_BORDER.name()};
                border-radius: 8px;
                background: rgba(30, 15, 50, 200);
                color: {TEXT_LIGHT.name()};
                font-family: "Microsoft YaHei";
                font-size: 10px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {BTN_GRAD_BOT.name()},
                    stop:1 {ACCENT_PINK.name()});
                border-radius: 7px;
            }}
        """)

        self.upd_status.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_MUTED.name()};
                font-family: "Microsoft YaHei";
                font-size: 12px;
                background: transparent;
            }}
        """)

        self.cancel_update_btn.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT_MUTED.name()};
                font-family: "Microsoft YaHei";
                font-size: 13px;
                border: 1.5px solid rgba(120, 80, 140, 160);
                border-radius: 15px;
                background: rgba(30, 15, 50, 140);
            }}
            QPushButton:hover {{
                color: {ACCENT_PINK.name()};
                border-color: {ACCENT_PINK.name()};
                background: rgba(60, 30, 80, 160);
            }}
        """)

        self.skip_update_btn.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT_MUTED.name()};
                font-family: "Microsoft YaHei";
                font-size: 13px;
                border: 1.5px solid rgba(120, 80, 140, 160);
                border-radius: 15px;
                background: rgba(30, 15, 50, 140);
            }}
            QPushButton:hover {{
                color: {ERROR_COLOR.name()};
                border-color: {ERROR_COLOR.name()};
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
        if self._hold_ticks > 0:
            self._hold_ticks -= 1
            return
        if self._error_alpha > 0.01:
            self._error_alpha *= 0.90
            self._style_message(self._error_alpha)
        else:
            self._error_alpha = 0.0
            self.error_label.setVisible(False)
            self._error_timer.stop()

    def _style_message(self, alpha):
        """按透明度重绘提示文字样式"""
        c = self._message_color
        self.error_label.setStyleSheet(f"""
            QLabel {{
                color: rgba({c.red()}, {c.green()}, {c.blue()}, {int(255 * alpha)});
                font-family: "Microsoft YaHei";
                font-size: 12px;
                background: transparent;
            }}
        """)

    def _show_error(self, message):
        """显示错误消息并抖动输入框"""
        self._message_color = ERROR_COLOR
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self._error_alpha = 1.0
        self._hold_ticks = 20  # 保持约 1 秒再开始淡出
        self._style_message(1.0)  # 立即刷新为全亮
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
        self._hold_ticks = 20
        self._style_message(1.0)
        self._error_timer.stop()
        self._error_timer.start(50)

    # ── 登录逻辑 ────────────────────────────────────────

    def _on_submit(self):
        """登录页 = 登录，注册页 = 注册，其他页面（更新/设置）忽略回车"""
        if self._page == "login":
            self._attempt_login()
        elif self._page == "register":
            self._do_register()

    def _show_login_page(self):
        """回到登录页"""
        self._page = "login"
        self.title_label.setText("✦  Commemorate  ✦")
        self.subtitle_label.setVisible(True)
        self.divider_label.setVisible(True)
        self.username_input.setGeometry(70, 180, 280, 42)
        self.password_input.setGeometry(70, 235, 280, 42)
        self.confirm_input.setVisible(False)
        self.username_input.setVisible(True)
        self.password_input.setVisible(True)
        self.remember_check.setVisible(True)
        self.login_btn.setText("登  录")
        self.login_btn.setGeometry(70, 335, 280, 44)
        self.login_btn.setVisible(True)
        self.register_btn.setVisible(True)
        self.settings_btn.setVisible(True)
        self.back_btn.setVisible(False)
        self.error_label.setVisible(False)
        self._error_timer.stop()
        for w in (self.conn_owner_input, self.conn_repo_input,
                  self.conn_branch_input, self.conn_token_input,
                  self.conn_pwd_input, self.conn_status,
                  self.save_conn_btn, self.import_conn_btn,
                  self.export_conn_btn):
            w.setVisible(False)

    def _show_register_page(self):
        """切换到注册页"""
        if not self._sync_ready:
            self._error_timer.stop()
            self.username_input.shake()
            return
        self._page = "register"
        self.title_label.setText("✦  注册新账号  ✦")
        self.subtitle_label.setVisible(False)
        self.divider_label.setVisible(False)
        self.username_input.setGeometry(70, 150, 280, 42)
        self.password_input.setGeometry(70, 205, 280, 42)
        self.confirm_input.setGeometry(70, 260, 280, 42)
        self.confirm_input.setVisible(True)
        self.username_input.setVisible(True)
        self.password_input.setVisible(True)
        self.remember_check.setVisible(False)
        self.login_btn.setText("注  册")
        self.login_btn.setGeometry(70, 330, 280, 44)
        self.login_btn.setVisible(True)
        self.register_btn.setVisible(False)
        self.settings_btn.setVisible(False)
        self.back_btn.setVisible(True)
        self.error_label.setVisible(False)
        self._error_timer.stop()
        for w in (self.conn_owner_input, self.conn_repo_input,
                  self.conn_branch_input, self.conn_token_input,
                  self.conn_pwd_input, self.conn_status,
                  self.save_conn_btn, self.import_conn_btn,
                  self.export_conn_btn):
            w.setVisible(False)
        self.username_input.clear()
        self.password_input.clear()
        self.confirm_input.clear()
        self.username_input.setFocus()

    def _show_settings_page(self):
        """切换到连接设置页（token + 私有仓库，加密保存）"""
        self._page = "settings"
        self.title_label.setText("✦  连接设置  ✦")
        self.subtitle_label.setVisible(False)
        self.divider_label.setVisible(False)
        for w in (self.username_input, self.password_input, self.confirm_input,
                  self.remember_check, self.login_btn, self.register_btn,
                  self.error_label, self.settings_btn):
            w.setVisible(False)
        self._error_timer.stop()

        prof = self.config.connection_profile
        self.conn_owner_input.setText(prof.get("repo_owner", ""))
        self.conn_repo_input.setText(prof.get("repo_name", ""))
        self.conn_branch_input.setText(prof.get("branch", "main"))
        self.conn_token_input.setText(prof.get("token", ""))
        self.conn_pwd_input.clear()
        self.conn_status.setText("")
        for w in (self.conn_owner_input, self.conn_repo_input,
                  self.conn_branch_input, self.conn_token_input,
                  self.conn_pwd_input, self.conn_status,
                  self.save_conn_btn, self.import_conn_btn,
                  self.export_conn_btn):
            w.setVisible(True)
        self.back_btn.setVisible(True)

    def _save_connection(self):
        """保存连接配置（加密到本地，不随远程同步）"""
        owner = self.conn_owner_input.text().strip()
        repo = self.conn_repo_input.text().strip()
        password = self.conn_pwd_input.text()
        if not owner or not repo:
            self.conn_status.setText("请填写仓库所有者与仓库名")
            return
        if not password:
            self.conn_status.setText("请设置加密密码")
            return
        data = {
            "repo_owner": owner,
            "repo_name": repo,
            "branch": self.conn_branch_input.text().strip() or "main",
            "token": self.conn_token_input.text().strip(),
        }
        try:
            self.config.save_connection(data, password)
        except Exception as e:
            self.conn_status.setText(f"保存失败：{e}")
            return
        self.conn_status.setText("已保存，同步将使用该仓库")
        self.retry_sync.emit()

    def _import_connection(self):
        """导入好友分享的加密连接配置"""
        password = self.conn_pwd_input.text()
        if not password:
            self.conn_status.setText("导入前请先填写加密密码")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择加密的连接配置文件", "", "连接配置 (*.dat);;所有文件 (*)"
        )
        if not path:
            return
        try:
            from connection import import_profile
            data = import_profile(
                self.config, Path(path).read_text(encoding="ascii"), password
            )
        except Exception as e:
            self.conn_status.setText(f"导入失败：{e}")
            return
        self.conn_owner_input.setText(data.get("repo_owner", ""))
        self.conn_repo_input.setText(data.get("repo_name", ""))
        self.conn_branch_input.setText(data.get("branch", "main"))
        self.conn_token_input.setText(data.get("token", ""))
        self.conn_status.setText("导入成功，已使用该仓库")
        self.retry_sync.emit()

    def _export_connection(self):
        """导出当前连接配置为加密文件（发给好友）"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出连接配置", "connection.dat", "连接配置 (*.dat)"
        )
        if not path:
            return
        try:
            from connection import export_profile
            blob = export_profile(self.config, "")
            if not blob:
                self.conn_status.setText("尚未保存连接配置，无法导出")
                return
            Path(path).write_text(blob, encoding="ascii")
        except Exception as e:
            self.conn_status.setText(f"导出失败：{e}")
            return
        self.conn_status.setText("已导出，发送给好友并告知加密密码")

    def _do_register(self):
        """注册新账号（与登录同一窗口）"""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()

        if not self._sync_ready:
            self._error_timer.stop()
            self.username_input.shake()
            self.password_input.shake()
            self.confirm_input.shake()
            return

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

        # 账号信息只存远程：注册即推送远程 config.json，成功才算注册成功
        self.login_btn.setEnabled(False)
        self.login_btn.setText("注册中...")
        self._show_info("正在注册并同步远程…")
        self._start_remote_register_sync(username, hash_password(password))

    def _start_remote_register_sync(self, username, password_hash):
        """把新注册用户写入远程 config.json（异步，不阻塞界面）"""
        from data_sync import DataSyncManager
        self._reg_sync_mgr = DataSyncManager(self.config, self)
        self._reg_sync_mgr.remote_config_done.connect(
            lambda ok, msg, uname=username: self._on_register_synced(ok, msg, uname)
        )
        self._reg_sync_mgr.push_registered_user(username, password_hash)

    def _on_register_synced(self, ok, msg, username):
        """注册结果：成功切回登录页，失败留在注册页"""
        self.login_btn.setEnabled(True)
        if ok:
            self.config.reload()
            self._show_login_page()
            self.username_input.setText(username)
            self.password_input.clear()
            self.password_input.setFocus()
            self._show_info("注册成功，账号已同步到远程")
        else:
            self.login_btn.setText("注  册")
            self._show_error(f"注册失败：{msg}")

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
        if self._auth_result:
            return
        self._auth_result = True
        self._login_username = username
        self._login_password = self.password_input.text()
        self.login_btn.setEnabled(False)
        self.config.save_remember_me(username, self.remember_check.isChecked())
        self.login_ok.emit(username, self.password())

    def username(self):
        """最近一次登录成功的用户名"""
        return getattr(self, "_login_username", "")

    def password(self):
        """最近一次登录成功的密码（用于更新重启后自动登录）"""
        return getattr(self, "_login_password", "")

    def update_sync_state(self, state, detail=None):
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
            if detail:
                d = str(detail).strip()
                if len(d) > 40:
                    d = d[:40] + "…"
                self._sync_status += f"（{d}）"
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
        # 同步提示只在登录/注册页显示，避免覆盖连接设置页的按钮
        if self._page in ("login", "register"):
            self.error_label.setVisible(True)

    # ---- 更新面板（登录成功后，发现新版本时替换登录表单显示）----

    def _on_close_clicked(self):
        """右上角关闭按钮：更新面板中发出 update_action，否则直接关闭窗口"""
        if self._update_panel_visible:
            self.update_action.emit("close")
        else:
            self.reject()

    def _hide_update_panel(self):
        for w in (self.upd_title, self.upd_version, self.upd_changelog,
                  self.update_btn, self.upd_progress, self.upd_status,
                  self.upd_restart_hint, self.cancel_update_btn,
                  self.skip_update_btn):
            w.setVisible(False)

    def show_update_panel(self, latest, current, changelog=""):
        """把登录窗口切换为更新界面：显示新版本信息与更新按钮"""
        self._update_panel_visible = True
        self._page = "update"
        self.title_label.setText("♡ Commemorate ♡")
        self.subtitle_label.setVisible(False)
        self.divider_label.setVisible(False)
        self.username_input.setVisible(False)
        self.password_input.setVisible(False)
        self.confirm_input.setVisible(False)
        self.remember_check.setVisible(False)
        self.login_btn.setVisible(False)
        self.register_btn.setVisible(False)
        self.settings_btn.setVisible(False)
        self.back_btn.setVisible(False)
        self.error_label.setVisible(False)
        self._error_timer.stop()

        self.upd_title.setText("发现新版本")
        self.upd_version.setText(f"v{current}  →  v{latest}")
        text = (changelog or "").strip()
        self.upd_changelog.setText(text if text else "有新版本可用，点击下方按钮开始更新。")
        self.upd_progress.setValue(0)
        self.upd_status.setText("")
        self.upd_restart_hint.setText("")
        self.upd_restart_hint.setVisible(False)
        self.update_btn.setEnabled(True)
        self.update_btn.setText("立即更新")
        self.cancel_update_btn.setVisible(False)
        self.skip_update_btn.setVisible(True)
        self.upd_title.setVisible(True)
        self.upd_version.setVisible(True)
        self.upd_changelog.setVisible(True)
        self.update_btn.setVisible(True)
        self.skip_update_btn.setVisible(True)
        self._update_active = False

    def set_update_state(self, state, data=None):
        """更新流程状态：start / downloading / error / installing"""
        data = data or {}
        # 默认隐藏重启提示，仅在 installing 状态显示
        self.upd_restart_hint.setVisible(False)
        if state == "start":
            self._update_active = True
            self.update_btn.setEnabled(False)
            self.update_btn.setText("更新中...")
            self.upd_progress.setRange(0, 100)
            self.upd_progress.setValue(0)
            self.upd_progress.setVisible(True)
            self.cancel_update_btn.setVisible(True)
            self.skip_update_btn.setVisible(False)
            self.upd_status.setText("正在下载更新包...")
            self.upd_status.setStyleSheet(f"""
                QLabel {{
                    color: {TEXT_MUTED.name()};
                    font-family: "Microsoft YaHei";
                    font-size: 12px;
                    background: transparent;
                }}
            """)
        elif state == "downloading":
            pct = int(data.get("percent", 0) or 0)
            if pct < 0:
                # 未知总大小：进度条进入忙碌动画，不显示具体百分比
                self.upd_progress.setRange(0, 0)
                self.upd_progress.setValue(0)
                self.upd_status.setText("正在下载更新包...")
            else:
                if self.upd_progress.maximum() == 0:
                    self.upd_progress.setRange(0, 100)
                self.upd_progress.setValue(min(100, pct))
                self.upd_status.setText(f"正在下载更新包... {pct}%")
            # 强制立即重绘，避免嵌套事件循环中进度条不刷新
            self.upd_progress.repaint()
            self.upd_status.repaint()
            QApplication.processEvents()
        elif state == "error":
            self._update_active = False
            self.update_btn.setEnabled(True)
            self.update_btn.setText("重试更新")
            self.upd_progress.setVisible(False)
            self.cancel_update_btn.setVisible(False)
            self.skip_update_btn.setVisible(True)
            self.upd_status.setText(str(data.get("message", "更新失败，请重试")))
            self.upd_status.setStyleSheet(f"""
                QLabel {{
                    color: {ERROR_COLOR.name()};
                    font-family: "Microsoft YaHei";
                    font-size: 12px;
                    background: transparent;
                }}
            """)
        elif state == "installing":
            self._update_active = True
            self.update_btn.setEnabled(False)
            self.update_btn.setText("更新完成")
            self.upd_progress.setVisible(False)
            self.cancel_update_btn.setVisible(False)
            self.skip_update_btn.setVisible(False)
            self.upd_status.setText("")
            self.upd_restart_hint.setText("更新完成，请关闭并重新打开程序")
            self.upd_restart_hint.setVisible(True)

    # ── 鼠标事件（拖拽窗口 & 关闭按钮）──────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._update_panel_visible:
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
            if self._update_panel_visible:
                self.update_action.emit("close")
            else:
                self.reject()
        else:
            super().keyPressEvent(event)
