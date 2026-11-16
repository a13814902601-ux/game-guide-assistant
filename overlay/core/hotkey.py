# -*- coding: utf-8 -*-
"""Windows 全局快捷键：RegisterHotKey + WM_HOTKEY 原生事件过滤。"""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

user32 = ctypes.WinDLL("user32", use_last_error=True)

VK_SPECIAL = {
    "space": 0x20,
    "escape": 0x1B,
    "esc": 0x1B,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "backspace": 0x08,
    "insert": 0x2D,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
}

ERROR_TEXT = {
    5: "权限不足（可能被系统或其他程序占用）",
    1409: "这个快捷键已经被其他程序占用了",
}


def parse_hotkey(spec: str) -> tuple[int, int]:
    """'Ctrl+Alt+G' / 'F8' -> (RegisterHotKey 修饰键, 虚拟键码)。"""
    if not spec or not spec.strip():
        raise ValueError("快捷键不能为空")
    parts = [p.strip() for p in spec.replace("＋", "+").split("+") if p.strip()]
    if not parts:
        raise ValueError("快捷键不能为空")
    mods = 0
    key = parts[-1].lower()
    for part in parts[:-1]:
        p = part.lower()
        if p in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif p == "alt":
            mods |= MOD_ALT
        elif p == "shift":
            mods |= MOD_SHIFT
        elif p in ("win", "meta", "super"):
            mods |= MOD_WIN
        else:
            raise ValueError(f"不认识的修饰键：{part}")
    if len(key) == 1 and key.isalpha():
        vk = ord(key.upper())
    elif len(key) == 1 and key.isdigit():
        vk = ord(key)
    elif key in VK_SPECIAL:
        vk = VK_SPECIAL[key]
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError(f"不支持的按键：{parts[-1]}")
    # 单个字母/数字必须带修饰键，否则会抢走正常打字
    if len(key) == 1 and key.isalnum() and mods == 0:
        raise ValueError("单个字母或数字必须配合 Ctrl / Alt / Shift / Win 使用")
    return mods, vk


def register_raw(spec: str, hotkey_id: int, hwnd: int = 0) -> tuple[bool, str]:
    mods, vk = parse_hotkey(spec)
    # 绑到主窗口 HWND：WM_HOTKEY 会进窗口消息队列，Qt 的 nativeEventFilter 才能稳定收到
    if user32.RegisterHotKey(wintypes.HWND(hwnd or 0), hotkey_id, mods | MOD_NOREPEAT, vk):
        return True, ""
    err = ctypes.get_last_error()
    return False, ERROR_TEXT.get(err, f"系统错误码 {err}")


def unregister_raw(hotkey_id: int, hwnd: int = 0) -> None:
    try:
        user32.UnregisterHotKey(wintypes.HWND(hwnd or 0), hotkey_id)
    except Exception:
        pass


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, owner: "GlobalHotkey"):
        super().__init__()
        self.owner = owner

    def nativeEventFilter(self, eventType, message):
        try:
            name = bytes(eventType).decode("ascii", "ignore")
        except Exception:
            name = str(eventType)
        if name in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    logging.getLogger("gga").info(
                        "WM_HOTKEY id=%s type=%s", msg.wParam, name
                    )
                    if int(msg.wParam) == self.owner.hotkey_id:
                        self.owner.activated.emit()
                        return True, 0
            except Exception:
                logging.getLogger("gga").exception("hotkey filter error")
        return False, 0


class GlobalHotkey(QObject):
    activated = Signal()

    def __init__(self, app, hotkey_id: int = 0xA11CE):
        super().__init__()
        self.app = app
        self.hotkey_id = hotkey_id
        self.current = ""
        self.hwnd = 0
        self._filter = _HotkeyFilter(self)
        self.app.installNativeEventFilter(self._filter)
        self.app.aboutToQuit.connect(self.unregister)

    def register(self, spec: str, hwnd: int | None = None) -> tuple[bool, str]:
        try:
            parse_hotkey(spec)
        except ValueError as exc:
            return False, str(exc)
        if hwnd:
            self.hwnd = int(hwnd)
        old = self.current
        self.unregister()
        ok, error = register_raw(spec, self.hotkey_id, self.hwnd)
        if ok:
            self.current = spec
        elif old:
            # 新快捷键注册失败时把旧的抢回来，避免用户失去开关
            restored, _ = register_raw(old, self.hotkey_id, self.hwnd)
            if restored:
                self.current = old
        return ok, error

    def unregister(self) -> None:
        if self.current:
            unregister_raw(self.hotkey_id, self.hwnd)
            self.current = ""
