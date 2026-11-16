# -*- coding: utf-8 -*-
"""悬浮窗配置：读写 %APPDATA% 下的 JSON，密钥不进 git / outbox。"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

APP_DIR_NAME = "GameGuideAssistant"
CONFIG_ENV = "GGA_CONFIG"
DEFAULT_HOTKEY = "F8"
DEFAULT_HEALTH_PORT = 8894

DEFAULT_WINDOW = {
    "x": None,
    "y": None,
    "w": 430,
    "h": 620,
    "opacity": 0.95,
    "font_size": 14,
    "always_on_top": True,
    "last_game": "deepspace-pawnshop",
}


def default_providers() -> list[dict]:
    """首次启动的提供商预设；密钥留空，由用户在设置页填写。"""
    return [
        {
            "id": "openai",
            "name": "OpenAI 兼容接口",
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "model": "gpt-4o-mini",
            "models": ["gpt-4o-mini"],
            "max_tokens": 8192,
            "temperature": 0.3,
            "note": "任意 OpenAI 兼容接口，地址一般以 /v1 结尾",
        },
        {
            "id": "deepseek",
            "name": "DeepSeek 官方",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "",
            "model": "deepseek-flash",
            "models": ["deepseek-flash", "deepseek-v4-pro"],
            "max_tokens": 4096,
            "temperature": 0.3,
            "note": "官方接口，密钥失效时在设置里替换",
        },
    ]


def default_config() -> dict:
    return {
        "version": 1,
        "window": copy.deepcopy(DEFAULT_WINDOW),
        "hotkey": DEFAULT_HOTKEY,
        "health_port": DEFAULT_HEALTH_PORT,
        "kb_root": "",
        "active_provider": "openai",
        "providers": default_providers(),
    }


def config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override).expanduser()
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_DIR_NAME / "overlay-config.json"


def _merge(base, override):
    """默认值做底，用户配置覆盖；列表整体替换，不做逐项合并。"""
    if isinstance(base, dict) and isinstance(override, dict):
        out = copy.deepcopy(base)
        for key, value in override.items():
            out[key] = _merge(base.get(key), value) if key in base else copy.deepcopy(value)
        return out
    return copy.deepcopy(override)


def _normalize_provider(raw: dict, fallback: dict | None = None) -> dict:
    base = copy.deepcopy(fallback or {})
    base.update(raw or {})
    base.setdefault("id", f"custom-{os.urandom(3).hex()}")
    base.setdefault("name", "自定义提供商")
    base.setdefault("base_url", "")
    base.setdefault("api_key", "")
    base.setdefault("model", "")
    base.setdefault("models", [])
    base.setdefault("max_tokens", 4096)
    base.setdefault("temperature", 0.3)
    if not isinstance(base["models"], list):
        base["models"] = []
    return base


class Config:
    def __init__(self, data: dict | None = None, path: Path | None = None):
        self.path = Path(path) if path else config_path()
        merged = _merge(default_config(), data or {})
        # providers 若是用户列表，保留用户内容，仅补字段
        raw_providers = (data or {}).get("providers")
        if isinstance(raw_providers, list) and raw_providers:
            merged["providers"] = [_normalize_provider(p) for p in raw_providers]
        else:
            merged["providers"] = [_normalize_provider(p) for p in default_providers()]
        self.data = merged

    # ---------- 读写 ----------
    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        p = Path(path) if path else config_path()
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            return cls(data, p)
        return cls(None, p)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    # ---------- 窗口 ----------
    @property
    def window(self) -> dict:
        return self.data.setdefault("window", copy.deepcopy(DEFAULT_WINDOW))

    def update_window(self, **kwargs) -> None:
        self.window.update(kwargs)

    @property
    def hotkey(self) -> str:
        return str(self.data.get("hotkey") or DEFAULT_HOTKEY)

    @hotkey.setter
    def hotkey(self, value: str) -> None:
        self.data["hotkey"] = value

    @property
    def health_port(self) -> int:
        try:
            return int(self.data.get("health_port", DEFAULT_HEALTH_PORT))
        except (TypeError, ValueError):
            return DEFAULT_HEALTH_PORT

    # ---------- 知识库（外挂，归 MCP） ----------
    @property
    def kb_root(self) -> str:
        return str(self.data.get("kb_root") or "")

    @kb_root.setter
    def kb_root(self, value: str) -> None:
        self.data["kb_root"] = str(value or "")

    # ---------- 提供商 ----------
    @property
    def providers(self) -> list[dict]:
        items = self.data.get("providers")
        if not isinstance(items, list):
            items = []
            self.data["providers"] = items
        return items

    def provider(self, provider_id: str | None = None) -> dict:
        pid = provider_id or self.data.get("active_provider")
        for item in self.providers:
            if item.get("id") == pid:
                return item
        if self.providers:
            self.data["active_provider"] = self.providers[0]["id"]
            return self.providers[0]
        item = _normalize_provider(default_providers()[0])
        self.providers.append(item)
        self.data["active_provider"] = item["id"]
        return item

    @property
    def active_provider(self) -> dict:
        return self.provider()

    def set_active_provider(self, provider_id: str) -> None:
        if any(p.get("id") == provider_id for p in self.providers):
            self.data["active_provider"] = provider_id

    def upsert_provider(self, provider: dict) -> None:
        pid = provider.get("id")
        for i, item in enumerate(self.providers):
            if item.get("id") == pid:
                self.providers[i] = _normalize_provider(provider, item)
                return
        self.providers.append(_normalize_provider(provider))

    def remove_provider(self, provider_id: str) -> bool:
        if len(self.providers) <= 1:
            return False
        before = len(self.providers)
        self.providers[:] = [p for p in self.providers if p.get("id") != provider_id]
        if len(self.providers) == before:
            return False
        if self.data.get("active_provider") == provider_id:
            self.data["active_provider"] = self.providers[0]["id"]
        return True

    # ---------- 游戏 ----------
    @property
    def last_game(self) -> str:
        return str(self.window.get("last_game") or DEFAULT_WINDOW["last_game"])

    @last_game.setter
    def last_game(self, value: str) -> None:
        self.update_window(last_game=value)
