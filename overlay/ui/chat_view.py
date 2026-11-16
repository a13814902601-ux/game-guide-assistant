# -*- coding: utf-8 -*-
"""聊天区：欢迎页 + 消息气泡 + 流式渲染（QLabel 富文本）。"""
from __future__ import annotations

import html
import re

import markdown
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme

_MD = markdown.Markdown(extensions=["fenced_code", "tables", "sane_lists", "nl2br"])

_URL_RE = re.compile(r"https?://[^\s<>\"'）】》，。；：！？]+", re.I)
_URL_TRAILING = ".,;:!?)]}\u3001\u3002\uff0c\uff1b\uff1a\uff01\uff1f"


def _linkify_html(html_text: str) -> str:
    """把 Markdown 渲染后仍是纯文本的 http(s) 网址包成可点击链接。

    只处理标签外、且不在 <a> 正文里的片段，避免把已有链接二次嵌套。
    """
    parts = re.split(r"(<[^>]+>)", html_text)
    out: list[str] = []
    in_anchor = False
    for part in parts:
        if part.startswith("<"):
            if re.match(r"<a\b", part, re.I):
                in_anchor = True
            elif re.match(r"</a\s*>", part, re.I):
                in_anchor = False
            out.append(part)
            continue
        if not part or in_anchor:
            out.append(part)
            continue

        def repl(match: re.Match) -> str:
            url = match.group(0)
            tail = ""
            while url and url[-1] in _URL_TRAILING:
                tail = url[-1] + tail
                url = url[:-1]
            if not url:
                return match.group(0)
            return f'<a href="{url}">{url}</a>' + tail

        out.append(_URL_RE.sub(repl, part))
    return "".join(out)


def md_to_html(text: str) -> str:
    _MD.reset()
    out = _MD.convert(text or "")
    out = _linkify_html(out)
    out = re.sub(
        r"<a href=",
        '<a style="color:#5eead4;text-decoration:underline;" href=',
        out,
    )
    out = out.replace("<h1>", '<h1 style="font-size:1.3em;color:#5eead4;margin:4px 0 2px 0;">')
    out = out.replace("<h2>", '<h2 style="font-size:1.2em;color:#5eead4;margin:4px 0 2px 0;">')
    out = out.replace("<h3>", '<h3 style="font-size:1.08em;color:#eafffb;margin:6px 0 2px 0;">')
    out = out.replace("<h4>", '<h4 style="font-size:1.02em;color:#eafffb;margin:4px 0 2px 0;">')
    out = out.replace("<code>", '<code style="color:#a7f3d0;background-color:#0b1117;">')
    out = out.replace("<pre>", '<pre style="color:#a7f3d0;background-color:#0b1117;">')
    return out


class ChatView(QScrollArea):
    suggestion = Signal(str)

    def __init__(self, suggestions: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatScroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self._font_size = 14
        self._auto_scroll = True
        self._bubbles: list[tuple[QLabel, bool]] = []  # (label, is_user)
        self._stream_label: QLabel | None = None
        self._stream_text = ""
        self._pending = ""
        self._stream_meta: QLabel | None = None

        self.container = QWidget()
        self.container.setObjectName("ChatContainer")
        self._layout = QVBoxLayout(self.container)
        self._layout.setContentsMargins(2, 4, 2, 4)
        self._layout.setSpacing(9)
        self._welcome = self._build_welcome(suggestions or [])
        self._layout.addWidget(self._welcome)
        self._layout.addStretch(1)
        self.setWidget(self.container)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(80)
        self._flush_timer.timeout.connect(self._flush_stream)
        self.setStyleSheet(self.styleSheet() + theme.chat_css(self._font_size))

    # ---------- 欢迎页 ----------
    def _build_welcome(self, suggestions: list[str]) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 18, 8, 6)
        lay.setSpacing(8)
        title = QLabel("卡关了吗？")
        title.setStyleSheet("font-size:20px;font-weight:700;color:#eafffb;")
        sub = QLabel("只查本地攻略库，答案带来源；查不到会直说，不瞎编。")
        sub.setObjectName("Hint")
        sub.setWordWrap(True)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(4)
        for text in suggestions:
            btn = QPushButton(text)
            btn.setObjectName("Chip")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, t=text: self.suggestion.emit(t))
            lay.addWidget(btn)
        tip = QLabel("Enter 发送 · Shift+Enter 换行 · F8 显示/隐藏")
        tip.setObjectName("Hint")
        lay.addSpacing(4)
        lay.addWidget(tip)
        return box

    # ---------- 消息 ----------
    def _add_row(self, text_html: str, is_user: bool, meta_text: str = "") -> tuple[QLabel, QLabel]:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        bubble = QLabel()
        bubble.setObjectName("UserBubble" if is_user else "AssistantBubble")
        bubble.setTextFormat(Qt.RichText)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        bubble.setOpenExternalLinks(True)
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        bubble.setText(text_html)
        meta = QLabel(meta_text)
        meta.setObjectName("Meta")
        meta.setWordWrap(True)
        meta.setVisible(bool(meta_text))
        col.addWidget(bubble)
        col.addWidget(meta)
        if is_user:
            row.addStretch(1)
            row.addLayout(col, 0)
        else:
            row.addLayout(col, 0)
            row.addStretch(1)
        wrapper = QWidget()
        wrapper.setLayout(row)
        idx = max(0, self._layout.count() - 1)
        self._layout.insertWidget(idx, wrapper)
        self._bubbles.append((bubble, is_user))
        self._welcome.setVisible(False)
        QTimer.singleShot(0, self._update_widths)
        self._scroll_to_bottom()
        return bubble, meta

    def add_user(self, text: str) -> None:
        safe = html.escape(text).replace("\n", "<br>")
        self._add_row(safe, True)
        self._auto_scroll = True

    def start_assistant(self) -> None:
        label, meta = self._add_row('<span style="color:#8b98a5;">正在查攻略库…</span>', False)
        self._stream_label = label
        self._stream_meta = meta
        self._stream_text = ""
        self._pending = ""
        self.update_meta("查库中…")
        self._flush_timer.start()
        self._auto_scroll = True

    def append_assistant(self, chunk: str) -> None:
        if not chunk:
            return
        self._stream_text += chunk
        self._pending += chunk

    def update_meta(self, text: str) -> None:
        if self._stream_meta is not None:
            self._stream_meta.setText(text or "")
            self._stream_meta.setVisible(bool(text))

    def _flush_stream(self) -> None:
        if self._stream_label is None:
            return
        if not self._pending and self._stream_text:
            return
        if not self._pending:
            return
        self._pending = ""
        text = self._stream_text
        if text.strip():
            self._stream_label.setText(md_to_html(text) + '<span style="color:#2dd4bf;">▍</span>')
        self._update_widths()
        if self._auto_scroll:
            self._scroll_to_bottom()

    def finish_assistant(self, meta_text: str = "", cancelled: bool = False) -> None:
        if self._stream_label is None:
            return
        self._flush_timer.stop()
        text = self._stream_text.strip()
        if text:
            self._stream_label.setText(md_to_html(self._stream_text))
        elif cancelled:
            self._stream_label.setText('<span style="color:#8b98a5;">已停止生成。</span>')
        else:
            self._stream_label.setText('<span style="color:#fca5a5;">模型没有返回内容。</span>')
        self.update_meta(meta_text)
        self._stream_label = None
        self._stream_meta = None
        self._stream_text = ""
        self._pending = ""
        self._update_widths()
        self._scroll_to_bottom()

    def show_assistant(self, text: str, meta_text: str = "") -> None:
        """一次性塞入完整回答（用于知识库未命中的固定话术）。"""
        if self._stream_label is None:
            self.start_assistant()
        self._stream_text = text
        self._pending = ""
        self._stream_label.setText(md_to_html(text))
        self.finish_assistant(meta_text)

    @property
    def stream_text(self) -> str:
        return self._stream_text

    def fail_assistant(self, message: str) -> None:
        if self._stream_label is None:
            return
        self._flush_timer.stop()
        safe = html.escape(message).replace("\n", "<br>")
        self._stream_label.setText(f'<span style="color:#fca5a5;">{safe}</span>')
        self.update_meta("出错")
        self._stream_label = None
        self._stream_meta = None
        self._stream_text = ""
        self._pending = ""
        self._update_widths()

    def clear(self) -> None:
        self._flush_timer.stop()
        for bubble, _ in self._bubbles:
            wrapper = bubble.parentWidget()
            if wrapper is not None:
                self._layout.removeWidget(wrapper)
                wrapper.deleteLater()
        self._bubbles.clear()
        self._stream_label = None
        self._stream_meta = None
        self._stream_text = ""
        self._pending = ""
        self._welcome.setVisible(True)
        self._auto_scroll = True
        self._scroll_to_bottom()

    @property
    def busy(self) -> bool:
        return self._stream_label is not None

    def set_font_size(self, size: int) -> None:
        self._font_size = max(11, min(22, int(size)))
        self.setStyleSheet(theme.BASE_QSS + theme.chat_css(self._font_size))
        QTimer.singleShot(0, self._update_widths)

    def _update_widths(self) -> None:
        width = max(220, int(self.viewport().width() * 0.86))
        for bubble, _ in self._bubbles:
            bubble.setMaximumWidth(width)

    def _scroll_to_bottom(self) -> None:
        bar = self.verticalScrollBar()

        def go():
            bar.setValue(bar.maximum())

        QTimer.singleShot(30, go)
        QTimer.singleShot(120, go)

    def _on_scroll(self, value: int) -> None:
        bar = self.verticalScrollBar()
        self._auto_scroll = value >= bar.maximum() - 30

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_widths)
