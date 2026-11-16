# -*- coding: utf-8 -*-
"""本机健康端口（默认 127.0.0.1:8894），给快速启动导航做在线探测。"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    app_name = "guide-overlay"
    state_provider = None

    def do_GET(self):  # noqa: N802
        data = {
            "app": self.app_name,
            "status": "ok",
            "pid": os.getpid(),
            "service": "游戏攻略悬浮窗",
        }
        if callable(self.state_provider):
            try:
                data.update(self.state_provider() or {})
            except Exception:
                pass
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except OSError:
            pass

    def log_message(self, fmt, *args):
        pass


class HealthServer:
    def __init__(self, port: int = 8894, state_provider=None):
        self.port = int(port or 0)
        self.state_provider = state_provider
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.error = ""

    @property
    def running(self) -> bool:
        return self.httpd is not None

    def start(self) -> bool:
        if self.port <= 0:
            self.error = "健康端口已关闭"
            return False
        try:
            handler = type(
                "BoundHealthHandler",
                (_Handler,),
                {"state_provider": staticmethod(self.state_provider)},
            )
            self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        except OSError as exc:
            self.error = f"健康端口 {self.port} 启动失败：{exc}"
            self.httpd = None
            return False
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="gga-health", daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        if self.httpd is not None:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
        self.httpd = None
