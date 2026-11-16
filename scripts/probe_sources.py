# -*- coding: utf-8 -*-
"""新游戏资料源探测：一条命令看清各源有没有内容。

用法：
    python scripts/probe_sources.py --name "游戏中文名" --name-en "Game Name" \
        --appid 123456 --wikily-slug game-slug --ali213-zone https://gl.ali213.net/z/12345

只做公开页面探测（限速、带UA、尊重 robots），B站/小黑盒等需要登录的源给出人工检查提示。
输出一份 JSON 报告，可直接贴进 games/<slug>.json 的 sources 字段。
"""
import argparse
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scrapers.base import Fetcher

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) game-guide-assistant/0.1"}


def probe_steam(appid: int, fetcher: Fetcher) -> dict:
    """Steam 社区指南：统计总篇数与疑似中文篇数。"""
    from scrapers import steam_guide

    if not appid:
        return {"status": "no-appid"}
    try:
        items = steam_guide.discover_guides(fetcher, appid)
        zh = [g for g in items if g["zh"]]
        return {
            "status": "ok" if items else "empty",
            "total_guides": len(items),
            "zh_guides": len(zh),
            "sample": [g["title"][:40] for g in zh[:5]],
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)[:150]}


def probe_wikily(slug: str, fetcher: Fetcher) -> dict:
    """Wikily：统计顶层页 + 二级详情页数量。"""
    from scrapers import wikily

    if not slug:
        return {"status": "no-slug"}
    try:
        paths = wikily.discover_pages(fetcher, slug)
        return {
            "status": "ok" if paths else "empty",
            "pages": len(paths),
            "subpages": sum(1 for p in paths if "/" in p),
            "sample": paths[:8],
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)[:150]}


def probe_ali213(zone_url: str, fetcher: Fetcher) -> dict:
    """游民星空专区：统计文章数。"""
    from scrapers import ali213

    if not zone_url:
        return {"status": "no-zone"}
    try:
        arts = ali213.discover_articles(fetcher, zone_url)
        return {
            "status": "ok" if arts else "empty",
            "articles": len(arts),
            "sample": [a["title"][:40] for a in arts[:5]],
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)[:150]}


def probe_biligame(name_zh: str) -> dict:
    """B站游戏中心 wiki：收录 ≠ 建站，必须看有没有 <code>/首页 链接。"""
    try:
        r = requests.get("https://wiki.biligame.com/wiki/首页", headers=UA, timeout=20)
        r.encoding = r.apparent_encoding or "utf-8"
        if name_zh not in r.text:
            return {"status": "not-listed", "note": "首页游戏列表中未见该游戏"}
        idx = r.text.find(name_zh)
        ctx = r.text[max(0, idx - 600) : idx + 300]
        # 建站游戏必然有 wiki.biligame.com/<代码>/ 链接；未建站只有图标文件引用
        has_site = bool(re.search(r'href="https://wiki\.biligame\.com/[a-z0-9_-]+/?"', ctx))
        return {
            "status": "has-site" if has_site else "listed-no-site",
            "note": "已建站，可走 MediaWiki API" if has_site else "仅收录未建站（无内容可采）",
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)[:150]}


def probe_xiaoheihe() -> dict:
    """小黑盒：网页端基本无公开内容，给结论而不是反复试。"""
    return {
        "status": "app-only",
        "note": "网页端社区/游戏页均 404（2026-11-16 实测）；内容仅在 APP，无公开接口。"
                "其用户攻略常被游民星空转载，可经 ali213 间接收录。",
    }


def probe_bilibili(name_zh: str) -> dict:
    """B站：搜索 API 需登录态，只能给人工检查提示。"""
    return {
        "status": "needs-login",
        "note": f"在 browser-use 打开 bilibili.com（已登录）后调用搜索 API："
                f"search_type=video/article&keyword={name_zh}+攻略；"
                f"专栏正文取 .bili-opus-view，视频字幕查 player/v2 的 subtitle.subtitles[].subtitle_url",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="游戏中文名（用于 biligame/B站探测）")
    ap.add_argument("--name-en")
    ap.add_argument("--appid", type=int)
    ap.add_argument("--wikily-slug")
    ap.add_argument("--ali213-zone")
    args = ap.parse_args()

    fetcher = Fetcher(ROOT / ".cache")
    report = {
        "name_zh": args.name,
        "name_en": args.name_en,
        "steam": probe_steam(args.appid or 0, fetcher),
        "wikily": probe_wikily(args.wikily_slug or "", fetcher),
        "ali213": probe_ali213(args.ali213_zone or "", fetcher),
        "biligame": probe_biligame(args.name),
        "xiaoheihe": probe_xiaoheihe(),
        "bilibili": probe_bilibili(args.name),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
