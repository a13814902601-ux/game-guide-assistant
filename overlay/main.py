# -*- coding: utf-8 -*-
"""攻略悬浮窗入口：单实例、托盘、全局快捷键、健康端口、无界面问答模式。"""
from __future__ import annotations

import argparse
import ctypes
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from overlay.core import kb_bridge, llm_client  # noqa: E402
from overlay.core.config import Config  # noqa: E402

APP_NAME = "攻略助手"
VERSION = "1.0.0"
IPC_NAME = "GameGuideAssistantOverlay"
LOG_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "GameGuideAssistant" / "logs"
LOG_FILE = LOG_DIR / "app.log"


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("gga")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        try:
            handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        except OSError:
            # GUI 正在运行并占着日志文件时，--ask 等第二进程不应启动失败
            handler = logging.NullHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def _set_app_id():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GameGuideAssistant.Overlay.1")
    except Exception:
        pass


def _write_out(path: str, text: str) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def run_headless(
    question: str,
    game: str | None = None,
    provider_id: str | None = None,
    dry_run: bool = False,
    out_path: str | None = None,
) -> int:
    config = Config.load()
    kb_bridge.set_output_root(config.kb_root or None)
    game = game or config.last_game
    provider = config.provider(provider_id) if provider_id else config.active_provider
    answer_parts: list[str] = []
    meta_parts: list[str] = []

    def out(text: str) -> None:
        answer_parts.append(text)
        if not out_path and sys.stdout is not None:
            sys.stdout.write(text)
            sys.stdout.flush()

    def note(text: str) -> None:
        meta_parts.append(text)
        if not out_path and sys.stderr is not None:
            sys.stderr.write(text + "\n")
            sys.stderr.flush()

    def finish(code: int) -> int:
        if out_path:
            body = "\n".join(meta_parts) + "\n\n" + "".join(answer_parts)
            _write_out(out_path, body)
        return code

    if not kb_bridge.games():
        out(kb_bridge.no_kb_text(str(kb_bridge.current_output_root())))
        return finish(1)

    retrieval = kb_bridge.retrieve(game, question)
    if retrieval.empty:
        out(kb_bridge.refusal_text(question, retrieval.game_name or game))
        return finish(0)

    note(f"[查库] {retrieval.summary} | {retrieval.total_counts}")
    if dry_run:
        note(f"[模式] dry-run（只检索，不调用模型）")
        out(retrieval.context())
        return finish(0)

    from overlay.core import prompt

    messages = prompt.build_messages(question, retrieval, [])
    note(f"[模型] {provider.get('name')} · {provider.get('model')}")
    started = time.time()
    try:
        result = llm_client.chat_stream(
            provider,
            messages,
            on_delta=out,
            on_reasoning=None,
            on_notice=lambda text: note(f"[提示] {text}"),
        )
    except llm_client.LLMError as exc:
        note(f"[错误] {exc}")
        return finish(1)
    if not result.text.strip():
        note("[错误] 模型没有返回正文")
        return finish(1)
    note(f"[完成] {time.time() - started:.1f}s")
    return finish(0)


def run_list_models(provider_id: str | None = None, out_path: str | None = None) -> int:
    config = Config.load()
    provider = config.provider(provider_id) if provider_id else config.active_provider
    try:
        models = llm_client.fetch_models(provider)
    except llm_client.LLMError as exc:
        text = f"失败：{exc}"
        if out_path:
            _write_out(out_path, text)
        else:
            print(text)
        return 1
    lines = [f"{provider.get('name')}（{provider.get('base_url')}）共 {len(models)} 个模型："]
    lines.extend(f" - {model}" for model in models)
    text = "\n".join(lines)
    if out_path:
        _write_out(out_path, text)
    else:
        print(text)
    return 0


def _try_activate_existing() -> bool:
    from PySide6.QtNetwork import QLocalSocket

    socket = QLocalSocket()
    socket.connectToServer(IPC_NAME)
    if socket.waitForConnected(400):
        socket.write(b"show\n")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True
    return False


def run_gui(hidden: bool = False) -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QAction
    from PySide6.QtNetwork import QLocalServer
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    from overlay.core.health_server import HealthServer
    from overlay.core.hotkey import GlobalHotkey
    from overlay.ui.icon import app_icon
    from overlay.ui.main_window import OverlayWindow

    _set_app_id()
    logger = logging.getLogger("gga")
    app = QApplication(sys.argv[:1] + ["--overlay"])
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("GameGuideAssistant")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    if _try_activate_existing():
        return 0

    config = Config.load()
    if not config.path.exists():
        try:
            config.save()
        except OSError:
            pass
    kb_bridge.set_output_root(config.kb_root or None)

    window = OverlayWindow(config)
    hotkey = GlobalHotkey(app)
    window.hotkey_manager = hotkey
    hotkey.activated.connect(window.toggle_visible)
    ok, error = hotkey.register(config.hotkey, int(window.winId()))
    if not ok:
        logger.warning("hotkey register failed: %s", error)

    def health_state():
        provider = config.active_provider
        return {
            "visible": window.isVisible(),
            "busy": window.busy,
            "hotkey": hotkey.current,
            "provider": provider.get("name", ""),
            "model": provider.get("model", ""),
            "game": config.last_game,
            "kb_root": str(kb_bridge.current_output_root()),
            "games": len(kb_bridge.games()),
        }

    health = HealthServer(config.health_port, health_state)
    if not health.start():
        logger.warning("health server: %s", health.error)

    server = QLocalServer()
    QLocalServer.removeServer(IPC_NAME)
    if not server.listen(IPC_NAME):
        logger.warning("local server listen failed: %s", server.errorString())

    def on_new_connection():
        while server.hasPendingConnections():
            conn = server.nextPendingConnection()
            conn.readyRead.connect(lambda c=conn: _handle_ipc(c, window))
            conn.disconnected.connect(conn.deleteLater)

    def _handle_ipc(conn, win):
        try:
            data = bytes(conn.readAll()).decode("utf-8", "ignore")
        except Exception:
            data = ""
        if "show" in data:
            QTimer.singleShot(0, win.show_and_focus)
        conn.disconnectFromServer()

    server.newConnection.connect(on_new_connection)

    tray = QSystemTrayIcon(app_icon(), app)
    tray.setToolTip("攻略助手 · 快捷键显示/隐藏")
    menu = QMenu()
    show_action = QAction("显示 / 隐藏", menu)
    show_action.triggered.connect(window.toggle_visible)
    settings_action = QAction("设置…", menu)
    settings_action.triggered.connect(window.open_settings)
    clear_action = QAction("清空对话", menu)
    clear_action.triggered.connect(window.clear_chat)
    quit_action = QAction("退出", menu)
    menu.addAction(show_action)
    menu.addAction(settings_action)
    menu.addAction(clear_action)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)

    def on_tray_activated(reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            window.toggle_visible()

    tray.activated.connect(on_tray_activated)
    tray.show()

    quitting = {"done": False}

    def quit_app():
        if quitting["done"]:
            return
        quitting["done"] = True
        window.prepare_quit()
        hotkey.unregister()
        health.stop()
        server.close()
        tray.hide()
        app.quit()

    quit_action.triggered.connect(quit_app)
    app.aboutToQuit.connect(quit_app)

    if hidden:
        window.hide()
        window._ready = True
    else:
        window.show_and_focus()

    if not ok:
        window.set_status(f"快捷键 {config.hotkey} 注册失败：{error}", "error")
        tray.showMessage("快捷键没注册上", f"{error}\n到设置里换一个组合。", QSystemTrayIcon.Warning, 6000)
    else:
        window.set_status(f"就绪 · {config.hotkey} 显示/隐藏", "ok")

    if not config.active_provider.get("api_key") and "127.0.0.1" not in str(
        config.active_provider.get("base_url", "")
    ):
        QTimer.singleShot(
            800,
            lambda: tray.showMessage(
                "还没配置 API Key",
                "打开设置 → 模型，填入 Key 后点「拉取清单」。",
                QSystemTrayIcon.Information,
                6000,
            ),
        )

    logger.info("overlay started pid=%s health=%s hotkey=%s", os.getpid(), health.running, config.hotkey)
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(description="游戏攻略悬浮窗")
    parser.add_argument("--ask", metavar="QUESTION", help="无界面提问（打印答案后退出）")
    parser.add_argument("--game", help="知识库 slug，默认使用上次选择")
    parser.add_argument("--provider", help="提供商 id，默认当前提供商")
    parser.add_argument("--list-models", action="store_true", help="打印当前提供商的模型清单")
    parser.add_argument("--dry-run", action="store_true", help="只检索不调用模型（配合 --ask）")
    parser.add_argument("--out", metavar="FILE", help="把 --ask / --list-models 输出写到文件（无控制台 exe 用）")
    parser.add_argument("--hidden", action="store_true", help="启动后隐藏到托盘")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args()
    setup_logging()

    if args.dry_run and not args.ask:
        parser.error("--dry-run 需要配合 --ask 使用")
    if args.list_models:
        return run_list_models(args.provider, args.out)
    if args.ask:
        return run_headless(args.ask, args.game, args.provider, args.dry_run, args.out)
    return run_gui(hidden=args.hidden)


if __name__ == "__main__":
    sys.exit(main())
