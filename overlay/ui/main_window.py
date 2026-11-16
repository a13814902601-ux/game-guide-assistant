# -*- coding: utf-8 -*-
"""悬浮主窗口：无边框置顶、拖动/缩放、聊天、流式回答、系统托盘配合。"""
from __future__ import annotations

import copy
import threading
import time

from PySide6.QtCore import QPoint, QRect, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core import kb_bridge, llm_client, prompt
from ..core.config import Config
from . import theme
from .chat_view import ChatView
from .icon import app_icon


def _refusal_text(question: str, game_name: str) -> str:
    return kb_bridge.refusal_text(question, game_name)


class ElidedLabel(QLabel):
    """按可用宽度省略文字，避免底部栏把模型名截成半截。"""

    def __init__(self, mode=Qt.ElideRight, parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._mode = mode

    def set_full_text(self, text: str):
        self._full_text = text or ""
        self.setToolTip(self._full_text)
        self._apply()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply()

    def _apply(self):
        width = max(12, self.width() - 2)
        self.setText(self.fontMetrics().elidedText(self._full_text, self._mode, width))


class AskWorker(QThread):
    status = Signal(str)
    retrieved = Signal(object)
    delta = Signal(str)
    reasoning = Signal(str)
    notice = Signal(str)
    refused = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, game: str, game_name: str, question: str, last_question: str | None,
                 provider: dict, history: list[dict]):
        super().__init__()
        self.game = game
        self.game_name = game_name
        self.question = question
        self.last_question = last_question
        self.provider = provider
        self.history = history
        self.cancel_event = threading.Event()

    def run(self):
        try:
            self.status.emit("查库中…")
            retrieval = kb_bridge.retrieve(self.game, self.question, self.last_question)
            if self.cancel_event.is_set():
                self.done.emit(llm_client.ChatResult(cancelled=True))
                return
            if retrieval.empty:
                self.refused.emit(_refusal_text(self.question, self.game_name))
                return
            self.retrieved.emit(retrieval)
            messages = prompt.build_messages(self.question, retrieval, self.history)
            result = llm_client.chat_stream(
                self.provider,
                messages,
                on_delta=self.delta.emit,
                on_reasoning=self.reasoning.emit,
                on_notice=self.notice.emit,
                cancel_event=self.cancel_event,
            )
            self.done.emit(result)
        except llm_client.LLMError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # 不让线程异常静默消失
            self.failed.emit(f"内部错误：{exc}")


class ChatInput(QPlainTextEdit):
    submit = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submit.emit()
                event.accept()
            return
        if event.key() == Qt.Key_Escape:
            window = self.window()
            hide = getattr(window, "hide_to_tray", None)
            if hide:
                hide()
            event.accept()
            return
        super().keyPressEvent(event)


class Composer(QFrame):
    submit = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Composer")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 6, 6, 6)
        layout.setSpacing(6)
        self.input = ChatInput()
        self.input.setObjectName("Input")
        self.input.setPlaceholderText("问攻略…（Enter 发送，Shift+Enter 换行）")
        self.input.setTabChangesFocus(True)
        self.input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.input.setFixedHeight(38)
        self.input.textChanged.connect(self._adjust_height)
        self.input.submit.connect(self.submit.emit)
        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("SendBtn")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setFixedHeight(34)
        layout.addWidget(self.input, 1)
        layout.addWidget(self.send_btn, 0, Qt.AlignBottom)
        self.send_btn.clicked.connect(self.submit.emit)

    def _adjust_height(self):
        lines = max(1, min(5, self.input.blockCount()))
        height = self.input.fontMetrics().lineSpacing() * lines + 16
        self.input.setFixedHeight(max(38, min(118, height)))

    def set_busy(self, busy: bool):
        self.send_btn.setText("停止" if busy else "发送")
        self.send_btn.setObjectName("StopBtn" if busy else "SendBtn")
        self.send_btn.style().unpolish(self.send_btn)
        self.send_btn.style().polish(self.send_btn)


class TitleBar(QWidget):
    def __init__(self, window: "OverlayWindow", parent=None):
        super().__init__(parent)
        self.setObjectName("Header")
        self.window_ref = window
        self._dragging = False
        self._drag_offset = QPoint()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(7)

        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(22, 22))
        icon.setFixedSize(22, 22)
        self.title = QLabel("攻略助手")
        self.title.setObjectName("Title")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("Subtitle")
        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(0)
        title_col.addWidget(self.title)
        title_col.addWidget(self.subtitle)
        layout.addWidget(icon, 0, Qt.AlignVCenter)
        layout.addLayout(title_col, 1)

        self.pin_btn = self._button("📌", "窗口置顶（点击切换）", "PinBtn")
        self.pin_btn.setCheckable(True)
        self.pin_btn.toggled.connect(window._on_pin_toggled)
        self.settings_btn = self._button("⚙", "设置", "HeaderBtn")
        self.settings_btn.clicked.connect(window.open_settings)
        self.hide_btn = self._button("—", "隐藏到托盘", "HeaderBtn")
        self.hide_btn.clicked.connect(window.hide_to_tray)
        self.close_btn = self._button("×", "隐藏到托盘（右键托盘图标可退出）", "CloseBtn")
        self.close_btn.clicked.connect(window.hide_to_tray)
        for btn in (self.pin_btn, self.settings_btn, self.hide_btn, self.close_btn):
            layout.addWidget(btn, 0, Qt.AlignVCenter)

    @staticmethod
    def _button(text: str, tip: str, name: str) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setObjectName(name)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setAutoRaise(True)
        btn.setFixedSize(28, 26)
        return btn

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)


class OverlayWindow(QWidget):
    quit_requested = Signal()

    def __init__(self, config: Config, hotkey_manager=None):
        super().__init__()
        self.config = config
        kb_bridge.set_output_root(config.kb_root or None)
        self.hotkey_manager = hotkey_manager
        self._worker: AskWorker | None = None
        self._retrieval = None
        self._busy = False
        self._started_at = 0.0
        self._history: list[dict] = []
        self._last_user_question: str | None = None
        self._discard_result = False
        self._ready = False
        self._allow_close = False
        self._settings_dialog = None

        self.setWindowTitle("攻略助手")
        self.setWindowIcon(app_icon())
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        if bool(config.window.get("always_on_top", True)):
            self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setMinimumSize(340, 420)
        self.setMouseTracking(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.panel = QFrame()
        self.panel.setObjectName("Panel")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 170))
        self.panel.setGraphicsEffect(shadow)
        outer.addWidget(self.panel)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(11, 7, 11, 9)
        panel_layout.setSpacing(7)

        self.title_bar = TitleBar(self)
        panel_layout.addWidget(self.title_bar)

        game_slug = config.last_game
        try:
            suggestions = kb_bridge.suggested_questions(game_slug)
        except Exception:
            suggestions = []
        self.chat = ChatView(suggestions)
        self.chat.suggestion.connect(self.send_question)
        panel_layout.addWidget(self.chat, 1)

        self.composer = Composer()
        self.composer.submit.connect(self.send_or_stop)
        panel_layout.addWidget(self.composer)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(2, 0, 2, 0)
        footer_layout.setSpacing(6)
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color:{theme.ACCENT};font-size:9px;")
        self.status_label = ElidedLabel(Qt.ElideRight)
        self.status_label.setObjectName("Hint")
        self.status_label.set_full_text("就绪")
        self.status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.model_label = ElidedLabel(Qt.ElideMiddle)
        self.model_label.setObjectName("Hint")
        self.model_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.model_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setObjectName("Ghost")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setToolTip("清空当前对话")
        self.clear_btn.clicked.connect(self.clear_chat)
        footer_layout.addWidget(self.status_dot)
        footer_layout.addWidget(self.status_label, 1)
        footer_layout.addWidget(self.model_label, 1)
        footer_layout.addWidget(self.clear_btn)
        panel_layout.addWidget(footer)

        self.setStyleSheet(theme.BASE_QSS)
        self._restore_geometry()
        self.apply_config()

    @property
    def busy(self) -> bool:
        return self._busy

    # ---------- 配置 ----------
    def apply_config(self):
        kb_bridge.set_output_root(self.config.kb_root or None)
        window = self.config.window
        opacity = float(window.get("opacity", 0.95))
        self.setWindowOpacity(max(0.25, min(1.0, opacity)))
        self.chat.set_font_size(int(window.get("font_size", 14)))
        topmost = bool(window.get("always_on_top", True))
        self.title_bar.pin_btn.blockSignals(True)
        self.title_bar.pin_btn.setChecked(topmost)
        self.title_bar.pin_btn.blockSignals(False)
        self._apply_topmost(topmost)
        self.update_model_label()
        self.update_game_label()

    def update_game_label(self):
        games = kb_bridge.games()
        if not games:
            self.title_bar.subtitle.setText("未连接攻略库 · 设置里选择 output")
            self.title_bar.subtitle.setToolTip(
                f"当前查找路径：{kb_bridge.current_output_root()}\n"
                "攻略库归 MCP 所有；把 output 目录放到 exe 旁边，或在设置 → 知识库里选择。"
            )
            return
        name = self.config.last_game
        for game in games:
            if game.get("game") == self.config.last_game:
                name = game.get("name_zh") or game.get("game") or name
                break
        self.title_bar.subtitle.setText(f"{name} · 本地攻略库")
        self.title_bar.subtitle.setToolTip(
            f"{self.config.last_game}\n{kb_bridge.current_output_root()}"
        )

    def update_model_label(self):
        provider = self.config.active_provider
        text = f"{provider.get('name', '')} · {provider.get('model', '未选模型')}"
        self.model_label.set_full_text(text)
        self.model_label.setToolTip(f"{provider.get('base_url', '')}\n{text}")

    def _apply_topmost(self, enabled: bool):
        current = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
        if current == enabled:
            return
        self.setWindowFlag(Qt.WindowStaysOnTopHint, enabled)
        if self.isVisible():
            self.show()

    def _on_pin_toggled(self, checked: bool):
        self.config.update_window(always_on_top=bool(checked))
        self.config.save()
        self._apply_topmost(bool(checked))

    # ---------- 几何 ----------
    def _restore_geometry(self):
        window = self.config.window
        width = int(window.get("w") or 430)
        height = int(window.get("h") or 620)
        width = max(self.minimumWidth(), width)
        height = max(self.minimumHeight(), height)
        x, y = window.get("x"), window.get("y")
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            if x is None or y is None:
                x = avail.right() - width - 24
                y = avail.top() + max(20, (avail.height() - height) // 2)
            rect = QRect(int(x), int(y), width, height)
            if not any(s.availableGeometry().intersects(rect) for s in QApplication.screens()):
                x = avail.right() - width - 24
                y = avail.top() + max(20, (avail.height() - height) // 2)
        self.setGeometry(int(x or 80), int(y or 80), width, height)

    def reset_geometry(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        width, height = 430, 620
        x = avail.right() - width - 24
        y = avail.top() + max(20, (avail.height() - height) // 2)
        self.setGeometry(x, y, width, height)
        self._save_geometry()

    def _schedule_save_geometry(self):
        if not self._ready:
            return
        QTimer.singleShot(650, self._save_geometry)

    def _save_geometry(self):
        if not self.isVisible() and not self._ready:
            return
        geo = self.geometry()
        self.config.update_window(x=geo.x(), y=geo.y(), w=geo.width(), h=geo.height())
        try:
            self.config.save()
        except OSError:
            pass

    def moveEvent(self, event):
        super().moveEvent(event)
        self._schedule_save_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_save_geometry()

    # ---------- 显示/隐藏 ----------
    def show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()
        handle = self.windowHandle()
        if handle is not None:
            handle.requestActivate()
        # 游戏在前台时 Qt 的 activateWindow 可能被前台锁拦下，补一刀 Win32
        try:
            import ctypes

            ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
        except Exception:
            pass
        self.composer.input.setFocus()
        self._ready = True

    def hide_to_tray(self):
        self._save_geometry()
        self.hide()

    def toggle_visible(self):
        if self.isVisible():
            self.hide_to_tray()
        else:
            self.show_and_focus()

    def prepare_quit(self):
        self._allow_close = True
        if self._worker is not None:
            self._worker.cancel_event.set()

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
        else:
            event.ignore()
            self.hide_to_tray()

    # ---------- 缩放（无边框窗口边缘） ----------
    def _edge_at(self, pos):
        margin = 9
        edges = Qt.Edges()
        if pos.x() <= margin:
            edges |= Qt.LeftEdge
        if pos.x() >= self.width() - margin:
            edges |= Qt.RightEdge
        if pos.y() <= margin:
            edges |= Qt.TopEdge
        if pos.y() >= self.height() - margin:
            edges |= Qt.BottomEdge
        return edges

    def mouseMoveEvent(self, event):
        edges = self._edge_at(event.position().toPoint())
        if edges in (Qt.LeftEdge | Qt.TopEdge, Qt.RightEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edges in (Qt.RightEdge | Qt.TopEdge, Qt.LeftEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edges & (Qt.LeftEdge | Qt.RightEdge):
            self.setCursor(Qt.SizeHorCursor)
        elif edges & (Qt.TopEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edges = self._edge_at(event.position().toPoint())
            if edges:
                handle = self.windowHandle()
                if handle is not None and handle.startSystemResize(edges):
                    event.accept()
                    return
        super().mousePressEvent(event)

    # ---------- 对话 ----------
    def clear_chat(self):
        if self._busy:
            self._discard_result = True
            self.stop_generation()
        self.chat.clear()
        self._history.clear()
        self._last_user_question = None
        self.set_status("就绪", "ok")

    def set_status(self, text: str, kind: str = "ok"):
        colors = {"ok": theme.ACCENT, "busy": "#fbbf24", "error": "#f87171", "muted": "#6f7d8a"}
        self.status_label.set_full_text(text)
        self.status_dot.setStyleSheet(f"color:{colors.get(kind, theme.ACCENT)};font-size:9px;")

    def send_or_stop(self):
        if self._busy:
            self.stop_generation()
            return
        text = self.composer.input.toPlainText().strip()
        if not text:
            return
        self.send_question(text)

    def send_question(self, text: str):
        text = (text or "").strip()
        if not text:
            return
        if self._busy:
            return
        if not kb_bridge.games():
            self.composer.input.clear()
            self.chat.add_user(text)
            self.chat.start_assistant()
            self.chat.show_assistant(
                kb_bridge.no_kb_text(str(kb_bridge.current_output_root())), "未找到攻略库"
            )
            self.set_status("未找到攻略库", "error")
            return
        self.composer.input.clear()
        self.chat.add_user(text)
        self.chat.start_assistant()
        self._set_busy(True)
        self.set_status("查库中…", "busy")
        self._started_at = time.monotonic()
        self._retrieval = None
        self._discard_result = False

        provider = copy.deepcopy(self.config.active_provider)
        history = list(self._history)
        worker = AskWorker(
            self.config.last_game,
            self._game_display_name(),
            text,
            self._last_user_question,
            provider,
            history,
        )
        self._worker = worker
        worker.status.connect(lambda s: self.set_status(s, "busy"))
        worker.retrieved.connect(self._on_retrieved)
        worker.delta.connect(self.chat.append_assistant)
        worker.reasoning.connect(self._on_reasoning)
        worker.notice.connect(lambda s: self.chat.update_meta(s))
        worker.refused.connect(self._on_refused)
        worker.done.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda w=worker: self._on_worker_finished(w))
        self._history.append({"role": "user", "content": text})
        self._last_user_question = text
        worker.start()

    def _game_display_name(self) -> str:
        for game in kb_bridge.games():
            if game.get("game") == self.config.last_game:
                return game.get("name_zh") or game.get("game") or self.config.last_game
        return self.config.last_game

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.composer.set_busy(busy)

    def stop_generation(self):
        if self._worker is not None:
            self._worker.cancel_event.set()
            self.set_status("正在停止…", "busy")

    def _on_retrieved(self, retrieval):
        self._retrieval = retrieval
        self.chat.update_meta(f"{retrieval.summary} · 正在生成答案…")
        self.set_status(retrieval.summary, "busy")

    def _on_reasoning(self, text: str):
        if not text:
            return
        if not self.chat.stream_text:
            self.chat.update_meta(f"模型思考中…（{len(text)} 字）")

    def _consume_discard(self) -> bool:
        if not self._discard_result:
            return False
        self._discard_result = False
        self._set_busy(False)
        self.set_status("就绪", "ok")
        return True

    def _on_refused(self, message: str):
        if self._consume_discard():
            return
        self.chat.show_assistant(message, "知识库未命中")
        self._set_busy(False)
        self.set_status("知识库未收录", "muted")
        self._history.append({"role": "assistant", "content": message})
        self._trim_history()

    def _on_done(self, result):
        if self._consume_discard():
            return
        elapsed = time.monotonic() - self._started_at
        summary = self._retrieval.summary if self._retrieval is not None else "已生成"
        meta = f"{summary} · {elapsed:.1f}s"
        if result.cancelled:
            meta = "已停止"
        self.chat.finish_assistant(meta, cancelled=result.cancelled)
        self._set_busy(False)
        if result.text.strip():
            self._history.append({"role": "assistant", "content": result.text.strip()})
            self._trim_history()
        self.set_status("已生成" if not result.cancelled else "已停止", "ok" if not result.cancelled else "muted")

    def _on_failed(self, message: str):
        if self._consume_discard():
            return
        self.chat.fail_assistant(message)
        self._set_busy(False)
        self.set_status("出错", "error")

    def _on_worker_finished(self, worker):
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    def _trim_history(self):
        if len(self._history) > 10:
            self._history = self._history[-10:]

    # ---------- 设置 ----------
    def open_settings(self):
        from .settings_dialog import SettingsDialog

        if self._settings_dialog is not None:
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dialog = SettingsDialog(self.config, self, self.hotkey_manager)
        self._settings_dialog = dialog
        try:
            accepted = dialog.exec()
        finally:
            self._settings_dialog = None
        self.apply_config()
        if accepted:
            self.update_model_label()
            self.set_status("设置已保存", "ok")
