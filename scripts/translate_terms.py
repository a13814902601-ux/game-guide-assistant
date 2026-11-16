# -*- coding: utf-8 -*-
"""Index-Translate 术语批量翻译（免费 B 站 API，OpenAI 兼容）。

用法（模块）：
    from scripts.translate_terms import translate_terms
    zh = translate_terms(["Bottle of Water", ...], cache_path)
用法（命令行）：
    echo '["A","B"]' | python scripts/translate_terms.py --game deepspace-pawnshop
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests

API_URL = "https://index-translate.bilibili.com/v1/chat/completions"
MODEL = "Index-Translate-35B-A3B"
BATCH = 25
CTX = (
    "Translate the following item/machine/event names from the game Probably Stolen "
    "(深空当铺：可能是偷的, a cyberpunk pawnshop management sim) from English to Simplified Chinese. "
    "Use the official Chinese in-game terms when you know them; otherwise translate naturally. "
    "Reply ONLY a valid JSON object mapping each English input to its Chinese translation, no other text."
)

ROOT = Path(__file__).resolve().parent.parent


_session = requests.Session()
_session.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _call_batch(terms: list[str]) -> dict[str, str]:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": CTX + "\n" + json.dumps(terms, ensure_ascii=False)}],
        "temperature": 0.1,
    }
    for attempt, delay in enumerate((5, 20)):
        try:
            resp = _session.post(API_URL, json=payload, timeout=60)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.strip("`")
                content = content[4:] if content.startswith("json") else content
            data = json.loads(content)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception as exc:  # noqa: BLE001
            print(f"  翻译批次失败（第 {attempt + 1} 次）: {exc}", file=sys.stderr)
            time.sleep(delay)
    return {}


def translate_terms(terms: list[str], cache_path: Path) -> dict[str, str]:
    """带本地缓存的批量翻译；失败的词保留英文原词。"""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache: dict[str, str] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    todo = [t for t in dict.fromkeys(terms) if t and t not in cache]
    print(f"待翻译 {len(todo)} 个术语（缓存 {len(cache)} 个）")
    for i in range(0, len(todo), BATCH):
        batch = todo[i : i + BATCH]
        got = _call_batch(batch)
        for t in batch:
            cache[t] = got.get(t, t)  # 失败保留英文
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {min(i + BATCH, len(todo))}/{len(todo)} 完成")
        time.sleep(3)
    return cache


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="deepspace-pawnshop")
    args = ap.parse_args()
    terms = json.load(sys.stdin)
    cache_path = ROOT / "output" / args.game / "data" / "_translations.json"
    result = translate_terms(terms, cache_path)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
