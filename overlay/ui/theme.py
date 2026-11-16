# -*- coding: utf-8 -*-
"""深色主题 QSS。"""
from __future__ import annotations

ACCENT = "#2dd4bf"
ACCENT_LIGHT = "#5eead4"
TEXT = "#e6edf3"
MUTED = "#8b98a5"
PANEL_BG = "rgba(13, 18, 24, 0.97)"

BASE_QSS = f"""
QWidget {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    color: {TEXT};
    font-size: 13px;
}}
#Panel {{
    background: {PANEL_BG};
    border: 1px solid rgba(94, 234, 212, 0.16);
    border-radius: 14px;
}}
#Header {{
    background: transparent;
}}
#Title {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT};
}}
#Subtitle {{
    font-size: 11px;
    color: {MUTED};
}}
QToolButton#HeaderBtn {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 5px 7px;
    color: #9aa7b4;
    font-size: 15px;
}}
QToolButton#HeaderBtn:hover {{
    background: rgba(255, 255, 255, 0.08);
    color: #ffffff;
}}
QToolButton#CloseBtn:hover {{
    background: #e5484d;
    color: #ffffff;
}}
QToolButton#PinBtn:checked {{
    background: rgba(45, 212, 191, 0.16);
    color: {ACCENT_LIGHT};
}}
#ChatScroll {{
    background: transparent;
    border: none;
}}
#ChatContainer {{
    background: transparent;
}}
#UserBubble {{
    background: #1f6feb;
    color: #ffffff;
    border-radius: 12px;
    padding: 9px 12px;
}}
#AssistantBubble {{
    background: #151c24;
    color: {TEXT};
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px;
    padding: 10px 12px;
}}
#Meta {{
    color: #6f7d8a;
    font-size: 10px;
}}
#Composer {{
    background: #0e151c;
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 12px;
}}
QPlainTextEdit#Input {{
    background: transparent;
    border: none;
    color: {TEXT};
    selection-background-color: #1f6feb;
    padding: 2px;
}}
QPushButton#SendBtn {{
    background: {ACCENT};
    color: #06251f;
    border: none;
    border-radius: 9px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton#SendBtn:hover {{
    background: {ACCENT_LIGHT};
}}
QPushButton#SendBtn:disabled {{
    background: #243039;
    color: #6b7784;
}}
QPushButton#StopBtn {{
    background: #7f1d1d;
    color: #fecaca;
    border: 1px solid rgba(248, 113, 113, 0.35);
    border-radius: 9px;
    padding: 7px 12px;
}}
QPushButton#StopBtn:hover {{
    background: #991b1b;
}}
QPushButton#Chip {{
    background: rgba(45, 212, 191, 0.08);
    border: 1px solid rgba(45, 212, 191, 0.22);
    border-radius: 10px;
    padding: 7px 10px;
    color: #a7f3d0;
    text-align: left;
}}
QPushButton#Chip:hover {{
    background: rgba(45, 212, 191, 0.16);
    border-color: rgba(45, 212, 191, 0.45);
}}
QPushButton#Ghost {{
    background: transparent;
    border: none;
    color: {MUTED};
    padding: 3px 6px;
}}
QPushButton#Ghost:hover {{
    color: {TEXT};
    background: rgba(255, 255, 255, 0.06);
    border-radius: 6px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.16);
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.28);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QTabWidget::pane {{
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    background: #0e151c;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 8px 14px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {ACCENT_LIGHT};
    border-bottom: 2px solid {ACCENT};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: #0a1016;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 7px;
    padding: 6px 8px;
    color: {TEXT};
    min-height: 18px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: rgba(45, 212, 191, 0.55);
}}
QComboBox QAbstractItemView {{
    background: #101820;
    border: 1px solid rgba(255, 255, 255, 0.12);
    selection-background-color: rgba(45, 212, 191, 0.18);
    color: {TEXT};
}}
QListWidget {{
    background: #0a1016;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 4px;
}}
QListWidget::item {{
    padding: 8px;
    border-radius: 6px;
}}
QListWidget::item:selected {{
    background: rgba(45, 212, 191, 0.14);
    color: {ACCENT_LIGHT};
}}
QPushButton#Primary {{
    background: {ACCENT};
    color: #06251f;
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton#Primary:hover {{
    background: {ACCENT_LIGHT};
}}
QPushButton#Secondary {{
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
    padding: 7px 12px;
    color: {TEXT};
}}
QPushButton#Secondary:hover {{
    background: rgba(255, 255, 255, 0.10);
}}
QPushButton#Danger {{
    background: rgba(229, 72, 77, 0.12);
    border: 1px solid rgba(229, 72, 77, 0.35);
    border-radius: 8px;
    padding: 7px 12px;
    color: #fca5a5;
}}
QPushButton#Danger:hover {{
    background: rgba(229, 72, 77, 0.22);
}}
QCheckBox {{
    spacing: 8px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: rgba(255, 255, 255, 0.12);
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: #eafffb;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QLabel#Hint {{
    color: {MUTED};
    font-size: 11px;
}}
QLabel#Section {{
    color: {ACCENT_LIGHT};
    font-size: 12px;
    font-weight: 600;
}}
QDialog {{
    background: #0b1117;
}}
"""


def chat_css(font_size: int = 14) -> str:
    return f"""
    QLabel {{
        color: #e6edf3;
        font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
        font-size: {font_size}px;
    }}
    """
