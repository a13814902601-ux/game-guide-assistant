# -*- coding: utf-8 -*-
"""游戏攻略知识库 MCP 服务器（fastmcp，stdio）。

ZCode/AI 客户端通过 5 个工具查询本地攻略知识库：
  list_games / search_data / get_entry / search_guides / get_guide
"""
import json
import os
import sys
from pathlib import Path

# Windows 默认 stdio 编码是 ANSI 代码页（如 GBK），会把 JSON 里的中文写坏；
# MCP 协议规定 UTF-8，这里在启动时强制重配。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastmcp import FastMCP

import kb.query as q

# 知识库归 MCP：默认用项目 output/，也可用 GGA_OUTPUT_DIR 外挂到任意目录
_external_kb = os.environ.get("GGA_OUTPUT_DIR") or os.environ.get("KB_OUTPUT_DIR")
if _external_kb:
    q.set_output_dir(_external_kb)

mcp = FastMCP("game-guide-kb")


@mcp.tool
def list_games() -> str:
    """列出知识库里所有游戏（含结构化数据条数与攻略篇数）。"""
    return json.dumps(q.list_games(), ensure_ascii=False)


@mcp.tool
def search_data(game: str, keyword: str, category: str | None = None) -> str:
    """在结构化攻略数据中按关键词检索（按当前游戏 name/name_en 自动中英桥接，通用词如 通缉犯↔Wanted 另有兜底）。

    category 可选：quests(任务/委托/事件/结局)、items(道具获取)、bosses(危机/强敌/治安)、
    achievements(成就)、recipes(配方)、characters(角色/通缉犯/NPC)；不传则全部分类。
    每条含 name/prerequisites(前置条件)/steps(步骤)/cautions(注意事项)/source_url。
    列表类问题请不限分类搜全量，并如实报告命中数量。
    """
    try:
        res = q.search_data(game, keyword, category)
        return json.dumps(res, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@mcp.tool
def get_entry(game: str, category: str, name: str) -> str:
    """按名称或 id 精确取一条结构化数据（含完整前置条件/步骤/注意事项）。"""
    try:
        res = q.get_entry(game, category, name)
        return json.dumps(res if res else {"not_found": name, "category": category}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@mcp.tool
def search_guides(game: str, keyword: str) -> str:
    """全文检索攻略库，返回命中文件与行预览。关键词会用当前游戏的 name/name_en 自动做中英桥接；中文没命中时可换英文名再搜一次。"""
    try:
        return json.dumps(q.search_guides(game, keyword), ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@mcp.tool
def get_guide(game: str, path: str) -> str:
    """读取一篇攻略全文。path 用 search_guides 返回的 file 字段。"""
    try:
        res = q.get_guide(game, path)
        return json.dumps(res if res else {"not_found": path}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
