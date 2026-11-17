# -*- coding: utf-8 -*-
"""悬浮窗核心自测：配置、检索、提示词、快捷键、两家模型连通。

用法：
    .venv/Scripts/python.exe scripts/test_overlay.py            # 全跑（含模型请求）
    .venv/Scripts/python.exe scripts/test_overlay.py --skip-llm # 只跑本地部分
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from overlay.core import kb_bridge, llm_client, prompt  # noqa: E402
from overlay.core.config import Config  # noqa: E402
from overlay.core.hotkey import parse_hotkey  # noqa: E402
from overlay.ui.chat_view import md_to_html  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}" + (f" — {detail}" if detail else ""))


def test_config():
    print("[配置]")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cfg.json"
        cfg = Config(None, path)
        check("默认两个提供商", len(cfg.providers) == 2)
        check("默认 OpenAI 兼容接口", cfg.providers[0]["id"] == "openai")
        cfg.update_window(opacity=0.8, w=500)
        cfg.hotkey = "Ctrl+Shift+G"
        cfg.save()
        check("配置文件落盘", path.is_file())
        loaded = Config.load(path)
        check("透明度回读", abs(float(loaded.window["opacity"]) - 0.8) < 1e-6)
        check("宽度回读", int(loaded.window["w"]) == 500)
        check("快捷键回读", loaded.hotkey == "Ctrl+Shift+G")


def test_hotkey():
    print("[快捷键解析]")
    check("F8", parse_hotkey("F8") == (0, 0x77))
    check("Ctrl+Alt+G", parse_hotkey("Ctrl+Alt+G") == (0x0002 | 0x0001, ord("G")))
    try:
        parse_hotkey("G")
        check("单字母被拒绝", False)
    except ValueError:
        check("单字母被拒绝", True)
    try:
        parse_hotkey("Ctrl+Foo")
        check("未知键被拒绝", False)
    except ValueError:
        check("未知键被拒绝", True)


def test_retrieval():
    print("[知识库检索]")
    game = "deepspace-pawnshop"
    r = kb_bridge.retrieve(game, "通缉犯有哪几个？")
    check("通缉犯有命中", not r.empty and any(x["category"] == "characters" for x in r.entries))
    check("通缉犯命中名单总览", any("通缉名单" in x["entry"].get("name", "") for x in r.entries))
    check("通缉犯带分类全量名单", "characters" in r.category_index and r.category_index["characters"]["total"] >= 9)

    r = kb_bridge.retrieve(game, "水商怎么玩？")
    check("水商命中", not r.empty and "水商" in r.entries[0]["entry"].get("name", ""))

    r = kb_bridge.retrieve(game, "一共有多少个成就？")
    check("成就识别分类", r.intent_category == "achievements")
    check("成就总数 21", r.category_index.get("achievements", {}).get("total") == 21)
    check("成就列表问题", r.list_question)

    r = kb_bridge.retrieve(game, "熔炉配方有哪些？")
    check("配方识别分类", r.intent_category == "recipes")
    check("配方总数 74", r.category_index.get("recipes", {}).get("total") == 74)

    r = kb_bridge.retrieve(game, "花莓要如何获得？")
    check("动态术语桥命中中文别名", any("布洛姆莓" in x["entry"].get("name", "") for x in r.entries))

    guides_dir = Path(__file__).resolve().parents[1] / "output" / game / "guides"
    has_guides = guides_dir.is_dir() and any(guides_dir.rglob("*.md"))
    if has_guides:
        r = kb_bridge.retrieve(game, "怎么存档？")
        check("存档走全文", bool(r.guides) and not r.entries)
    else:
        print("  - 跳过「存档走全文」：公开版不含攻略全文")

    r = kb_bridge.retrieve(game, "火星怎么种土豆？")
    check("无关问题不命中", r.empty, f"entries={len(r.entries)} guides={len(r.guides)}")

    r = kb_bridge.retrieve(game, "通缉犯有哪几个？")
    context = r.context()
    check("上下文含统计", "知识库统计" in context and "本次展开" in context)
    check("上下文带来源", "来源：" in context)


def test_multi_game():
    print("[多游戏通用性]")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        game = "test-game"
        gdir = root / game
        (gdir / "data").mkdir(parents=True)
        (gdir / "guides" / "test").mkdir(parents=True)
        (gdir / "_index.json").write_text(
            json.dumps(
                {
                    "game": game,
                    "name_zh": "测试游戏",
                    "name_en": "Test Game",
                    "data": {"total": 2, "categories": {"items": 1, "recipes": 1}},
                    "guides": {"test": ["test/moonlight.md"]},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        entries = [
            {
                "id": "moonlight-herb",
                "name": "月光草",
                "name_en": "Moonlight Herb",
                "category": "items",
                "prerequisites": ["夜晚去河边"],
                "steps": ["在河边采集月光草"],
                "cautions": [],
                "source_url": "https://example.com/moonlight",
                "verified_date": "2026-11-17",
            },
            {
                "id": "moonlight-potion",
                "name": "月光药剂",
                "name_en": "Moonlight Potion",
                "category": "recipes",
                "prerequisites": ["需要机器：炼金锅"],
                "steps": ["原料：月光草 x2", "机器：炼金锅（Alchemy Pot）", "产出：x1 Moonlight Potion"],
                "cautions": [],
                "source_url": "https://example.com/potion",
                "verified_date": "2026-11-17",
            },
        ]
        (gdir / "data" / "items.json").write_text(json.dumps(entries[:1], ensure_ascii=False), encoding="utf-8")
        (gdir / "data" / "recipes.json").write_text(json.dumps(entries[1:], ensure_ascii=False), encoding="utf-8")
        (gdir / "guides" / "test" / "moonlight.md").write_text(
            "# Moonlight Herb\n\n## Where to get\n"
            "Moonlight Herbs grow near the river at night. Bring a basket.\n\n"
            "## Moonlight Potion\nUse 2 Moonlight Herbs in an Alchemy Pot.\n",
            encoding="utf-8",
        )
        previous = kb_bridge.current_output_root()
        try:
            kb_bridge.set_output_root(root)
            r = kb_bridge.retrieve(game, "月光草怎么获得？")
            check("新游戏命中结构化条目", bool(r.entries) and "月光草" in r.entries[0]["entry"].get("name", ""))
            check("动态术语桥命中英文攻略", any("moonlight.md" in g["file"] for g in r.guides))
            check("新游戏上下文可引用", "Moonlight Herbs grow near the river" in r.context())
        finally:
            kb_bridge.set_output_root(previous)


def test_prompt():
    print("[提示词]")
    system = prompt.system_prompt()
    check("注入技能规则", "前置条件" in system and "知识库暂未收录" in system)
    check("包含悬浮窗硬规则", "资料是唯一事实来源" in system)
    r = kb_bridge.retrieve("deepspace-pawnshop", "水商怎么玩？")
    messages = prompt.build_messages("水商怎么玩？", r, [{"role": "user", "content": "上一轮"}])
    check("消息结构", messages[0]["role"] == "system" and messages[-1]["role"] == "user")
    check("上下文进入用户消息", "知识库检索结果" in messages[-1]["content"])


def test_markdown():
    print("[Markdown 渲染]")
    html = md_to_html("### 标题\n\n**加粗**\n\n- 一\n- 二")
    check("标题", "<h3" in html)
    check("加粗", "<strong>" in html)
    check("列表", "<li>" in html)
    html = md_to_html("来源：https://example.com/a。已有链接 [B](https://example.com/b)")
    check("纯文本网址转链接", 'href="https://example.com/a"' in html)
    check("已有链接不重复嵌套", html.count("<a ") == 2, html)
    check("中文句号不吞进网址", 'href="https://example.com/a。' not in html)


def test_llm():
    print("[模型连通]")
    cfg = Config.load()
    for provider in cfg.providers:
        if not provider.get("api_key"):
            print(f"  - 跳过「{provider['name']}」：未配置 API Key")
            continue
        try:
            models = llm_client.fetch_models(provider)
            check(f"{provider['name']} 模型清单", bool(models), f"数量 {len(models)}")
        except llm_client.LLMError as exc:
            check(f"{provider['name']} 模型清单", False, str(exc)[:160])
            continue
        try:
            result = llm_client.chat_once(
                provider, [{"role": "user", "content": "只回复两个字：收到"}], max_tokens=512
            )
            check(f"{provider['name']} 最小对话", bool(result.text.strip()), repr(result.text[:40]))
        except llm_client.LLMError as exc:
            check(f"{provider['name']} 最小对话", False, str(exc)[:160])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-llm", action="store_true")
    args = parser.parse_args()
    test_config()
    test_hotkey()
    test_retrieval()
    test_multi_game()
    test_prompt()
    test_markdown()
    if not args.skip_llm:
        test_llm()
    print(f"\n结果：{PASS} 通过，{FAIL} 失败")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
