# -*- coding: utf-8 -*-
"""MCP 服务器冒烟测试：内存客户端调用全部 5 个工具并断言结果。"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastmcp import Client

from mcp_server.server import mcp

GAME = "deepspace-pawnshop"


def text_of(result) -> str:
    for c in result.content:
        if hasattr(c, "text"):
            return c.text
    return str(result.content)


async def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    async with Client(mcp) as client:
        # 1 list_games
        r = await client.call_tool("list_games", {})
        data = json.loads(text_of(r))
        ok = any(g.get("game") == GAME and g.get("data_total") == 135 for g in data)
        checks.append(("list_games", ok, f"games={len(data)}, total={data[0].get('data_total') if data else None}"))

        # 2 search_data（成就）
        r = await client.call_tool("search_data", {"game": GAME, "keyword": "头奖", "category": "achievements"})
        data = json.loads(text_of(r))
        ok = len(data) >= 1 and data[0]["name"] == "头奖"
        checks.append(("search_data:成就/头奖", ok, f"top={data[0]['name'] if data else '无'}"))

        # 3 search_data（配方，英文名应也能搜到）
        r = await client.call_tool("search_data", {"game": GAME, "keyword": "Wine", "category": "recipes"})
        data = json.loads(text_of(r))
        ok = len(data) >= 1
        checks.append(("search_data:配方/Wine", ok, f"hits={len(data)}, top={data[0]['name'] if data else '无'}"))

        # 4 get_entry
        r = await client.call_tool("get_entry", {"game": GAME, "category": "bosses", "name": "改造"})
        data = json.loads(text_of(r))
        ok = "Aug" in str(data.get("name_en", ""))
        checks.append(("get_entry:bosses/改造", ok, f"name={data.get('name')}"))

        # 5-6 search_guides / get_guide（公开版没有全文，自动跳过）
        guides_dir = ROOT / "output" / GAME / "guides"
        has_guides = guides_dir.is_dir() and any(guides_dir.rglob("*.md"))
        if has_guides:
            r = await client.call_tool("search_guides", {"game": GAME, "keyword": "芬太片"})
            data = json.loads(text_of(r))
            ok = len(data) >= 1
            checks.append(("search_guides:芬太片", ok, f"files={len(data)}"))
            if data:
                fp = data[0]["file"]
                r = await client.call_tool("get_guide", {"game": GAME, "path": fp})
                d2 = json.loads(text_of(r))
                ok = "content" in d2 and len(d2["content"]) > 200
                checks.append(("get_guide", ok, f"len={len(d2.get('content', ''))}"))
        else:
            print("  - 跳过 search_guides/get_guide：公开版不含攻略全文")

    print("\n===== MCP 冒烟测试 =====")
    failed = 0
    for name, ok, info in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name:28s} {info}")
        failed += 0 if ok else 1
    print(f"结果：{len(checks) - failed}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
