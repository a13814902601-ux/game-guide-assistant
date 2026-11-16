# -*- coding: utf-8 -*-
"""OpenAI 兼容接口客户端：拉模型清单、流式对话、推理模型空正文重试。"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field

import requests

UA = "GameGuideOverlay/1.0 (+local desktop app)"
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 300


class LLMError(Exception):
    def __init__(self, message: str, detail: str = ""):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        return self.message + (f"\n\n接口原文：{self.detail}" if self.detail else "")


@dataclass
class ChatResult:
    text: str = ""
    reasoning: str = ""
    usage: dict = field(default_factory=dict)
    model: str = ""
    cancelled: bool = False


def _base(provider: dict) -> str:
    return str(provider.get("base_url") or "").strip().rstrip("/")


def _key(provider: dict) -> str:
    return str(provider.get("api_key") or "").strip()


def _headers(provider: dict) -> dict:
    headers = {"Content-Type": "application/json", "User-Agent": UA}
    key = _key(provider)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _detail(response: requests.Response) -> str:
    try:
        text = response.text
    except Exception:
        text = ""
    return (text or "").strip()[:800]


def _friendly_http(status: int, body: str, provider: dict) -> str:
    base = _base(provider)
    if status == 401:
        return "API Key 无效或已过期（HTTP 401）。去设置里检查 Key。"
    if status == 403:
        return "接口拒绝访问（HTTP 403）。可能是 Key 权限或地区限制。"
    if status == 404:
        return f"接口地址或模型名不对（HTTP 404）。检查 Base URL（当前 {base}）和模型名。"
    if status == 429:
        return "请求太频繁或额度不足（HTTP 429）。稍等再试，或换一个提供商。"
    if status >= 500:
        return f"模型服务端出错（HTTP {status}）。稍后重试或换提供商。"
    if "max_tokens" in body and "max_completion_tokens" not in body:
        return f"接口要求改用 max_completion_tokens（HTTP {status}）。"
    return f"接口返回错误（HTTP {status}）。"


def _wrap_request_error(exc: Exception, provider: dict) -> LLMError:
    base = _base(provider)
    if isinstance(exc, requests.exceptions.Timeout):
        return LLMError(f"请求超时：{base} 长时间没有响应。")
    if isinstance(exc, requests.exceptions.ConnectionError):
        if "127.0.0.1" in base or "localhost" in base:
            return LLMError(
                f"连不上本机接口 {base}。如果这是本地反代，请先启动对应服务（常见端口 8788）；"
                "也可以在设置里换一个提供商。"
            )
        return LLMError(f"连不上接口 {base}。检查网络或代理设置。")
    return LLMError(f"请求失败：{exc}")


def _payload(provider: dict, messages: list[dict], stream: bool, *, max_tokens: int | None = None,
             use_completion_tokens: bool = False, include_temperature: bool = True) -> dict:
    payload = {
        "model": provider.get("model") or "",
        "messages": messages,
        "stream": stream,
    }
    tokens = int(max_tokens or provider.get("max_tokens") or 4096)
    payload["max_completion_tokens" if use_completion_tokens else "max_tokens"] = tokens
    temp = provider.get("temperature", 0.3)
    if include_temperature and temp is not None:
        try:
            payload["temperature"] = float(temp)
        except (TypeError, ValueError):
            pass
    return payload


def fetch_models(provider: dict, timeout: int = 20) -> list[str]:
    base = _base(provider)
    if not base:
        raise LLMError("还没有填写接口地址（Base URL）。")
    url = f"{base}/models"
    try:
        response = requests.get(url, headers=_headers(provider), timeout=timeout)
    except Exception as exc:
        raise _wrap_request_error(exc, provider) from exc
    if response.status_code != 200:
        raise LLMError(_friendly_http(response.status_code, _detail(response), provider), _detail(response))
    try:
        data = response.json()
    except ValueError as exc:
        raise LLMError("模型清单不是合法 JSON，接口地址可能填错了。", _detail(response)) from exc
    items = data.get("data") if isinstance(data, dict) else data
    if items is None and isinstance(data, dict):
        items = data.get("models") or []
    ids: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = item.get("id") or item.get("model") or item.get("name") or ""
        else:
            name = ""
        if name and name not in ids:
            ids.append(str(name))
    if not ids:
        raise LLMError("接口返回了空模型清单。检查 Base URL 是否以 /v1 结尾。", json.dumps(data, ensure_ascii=False)[:500])
    return sorted(ids, key=lambda s: s.lower())


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # 少数接口返回分段内容
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    return ""


def _extract_delta(obj: dict) -> tuple[str, str]:
    content, reasoning = "", ""
    for choice in obj.get("choices") or []:
        delta = choice.get("delta") or choice.get("message") or {}
        content += _content_text(delta.get("content"))
        reasoning += _content_text(delta.get("reasoning_content") or delta.get("reasoning"))
        # 兼容个别反代把正文放在 choice.text
        if not content and choice.get("text"):
            content += _content_text(choice.get("text"))
    return content, reasoning


def _stream_once(
    provider: dict,
    messages: list[dict],
    on_delta,
    on_reasoning,
    cancel_event: threading.Event | None,
    *,
    max_tokens: int | None,
    use_completion_tokens: bool = False,
    include_temperature: bool = True,
) -> ChatResult:
    base = _base(provider)
    url = f"{base}/chat/completions"
    payload = _payload(
        provider,
        messages,
        True,
        max_tokens=max_tokens,
        use_completion_tokens=use_completion_tokens,
        include_temperature=include_temperature,
    )
    try:
        response = requests.post(
            url, headers=_headers(provider), json=payload, stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
        )
    except Exception as exc:
        raise _wrap_request_error(exc, provider) from exc
    if response.status_code != 200:
        body = _detail(response)
        response.close()
        raise LLMError(_friendly_http(response.status_code, body, provider), body)

    result = ChatResult(model=str(provider.get("model") or ""))
    content_type = (response.headers.get("Content-Type") or "").lower()
    try:
        if "application/json" in content_type and "event-stream" not in content_type:
            data = response.json()
            if data.get("error"):
                raise LLMError("接口返回错误。", json.dumps(data["error"], ensure_ascii=False)[:500])
            text, reasoning = _extract_delta(data)
            result.text = text
            result.reasoning = reasoning
            if text and on_delta:
                on_delta(text)
            if reasoning and on_reasoning:
                on_reasoning(reasoning)
            result.usage = data.get("usage") or {}
            return result

        for raw in response.iter_lines(chunk_size=1, decode_unicode=False):
            if cancel_event is not None and cancel_event.is_set():
                result.cancelled = True
                break
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("data:"):
                data_text = line[5:].strip()
            elif line.startswith("{"):
                data_text = line
            else:
                continue
            if data_text == "[DONE]":
                break
            try:
                obj = json.loads(data_text)
            except json.JSONDecodeError:
                continue
            if obj.get("error"):
                detail = json.dumps(obj["error"], ensure_ascii=False)
                raise LLMError("接口返回错误。", detail[:500])
            content, reasoning = _extract_delta(obj)
            if content:
                result.text += content
                if on_delta:
                    on_delta(content)
            if reasoning:
                result.reasoning += reasoning
                if on_reasoning:
                    on_reasoning(reasoning)
            if obj.get("usage"):
                result.usage = obj["usage"]
    except requests.exceptions.RequestException as exc:
        raise _wrap_request_error(exc, provider) from exc
    finally:
        response.close()
    return result


def _retry_messages(messages: list[dict]) -> list[dict]:
    return messages + [
        {
            "role": "system",
            "content": "上一次回复只输出了思考过程，没有正文。这次请直接给出最终答案，不要输出思考过程。",
        }
    ]


def chat_stream(
    provider: dict,
    messages: list[dict],
    on_delta=None,
    on_reasoning=None,
    on_notice=None,
    cancel_event: threading.Event | None = None,
) -> ChatResult:
    """流式对话；推理模型空正文时自动加倍 token 重试一次。"""
    if not _base(provider):
        raise LLMError("还没有配置接口地址。打开设置 → 模型，填 Base URL 和 API Key。")
    if not provider.get("model"):
        raise LLMError("还没有选择模型。打开设置 → 模型，拉取清单后选一个。")

    result = _stream_once(
        provider, messages, on_delta, on_reasoning, cancel_event, max_tokens=None
    )
    if result.cancelled:
        return result

    # 有些推理模型把 token 全烧在 reasoning_content 上，正文为空：加倍 token 重试
    if not result.text.strip() and not result.cancelled:
        if on_notice:
            on_notice("模型只输出了思考过程，正在加大长度重试…")
        base_tokens = int(provider.get("max_tokens") or 4096)
        try:
            retry = _stream_once(
                provider,
                _retry_messages(messages),
                on_delta,
                on_reasoning,
                cancel_event,
                max_tokens=min(max(base_tokens * 2, 8192), 65536),
            )
        except LLMError:
            raise
        if retry.text.strip():
            retry.reasoning = result.reasoning + retry.reasoning
            return retry
        result = retry

    if not result.text.strip() and not result.cancelled:
        raise LLMError(
            "模型没有返回正文（可能把 token 全用在思考上，或接口只返回了 reasoning_content）。"
            "到设置里换一个模型，或把 max_tokens 调大后重试。"
        )
    return result


def chat_once(provider: dict, messages: list[dict], max_tokens: int = 512, _retried: bool = False) -> ChatResult:
    """非流式请求，用于「测试连接」。"""
    base = _base(provider)
    url = f"{base}/chat/completions"
    payload = _payload(provider, messages, False, max_tokens=max_tokens)
    try:
        response = requests.post(url, headers=_headers(provider), json=payload, timeout=(CONNECT_TIMEOUT, 120))
    except Exception as exc:
        raise _wrap_request_error(exc, provider) from exc
    if response.status_code != 200:
        body = _detail(response)
        # max_tokens / temperature 兼容性重试
        if response.status_code in (400, 422) and "max_tokens" in body and "max_completion_tokens" not in body:
            payload.pop("max_tokens", None)
            payload["max_completion_tokens"] = max_tokens
        elif response.status_code in (400, 422) and "temperature" in body:
            payload.pop("temperature", None)
        else:
            raise LLMError(_friendly_http(response.status_code, body, provider), body)
        try:
            response = requests.post(url, headers=_headers(provider), json=payload, timeout=(CONNECT_TIMEOUT, 120))
        except Exception as exc:
            raise _wrap_request_error(exc, provider) from exc
        if response.status_code != 200:
            body = _detail(response)
            raise LLMError(_friendly_http(response.status_code, body, provider), body)
    try:
        data = response.json()
    except ValueError as exc:
        raise LLMError("接口没有返回 JSON，地址可能填错了。", _detail(response)) from exc
    if data.get("error"):
        raise LLMError("接口返回错误。", json.dumps(data["error"], ensure_ascii=False)[:500])
    text, reasoning = _extract_delta(data)
    if not text.strip() and reasoning and not _retried:
        retry = chat_once(provider, _retry_messages(messages), max_tokens=max(2048, max_tokens * 4), _retried=True)
        retry.reasoning = reasoning + retry.reasoning
        return retry
    if not text.strip() and reasoning:
        raise LLMError(
            "模型只返回了思考过程，没有正文。换一个模型，或把 max_tokens 调大后再试。",
            reasoning[:400],
        )
    return ChatResult(text=text, reasoning=reasoning, usage=data.get("usage") or {}, model=data.get("model", ""))
