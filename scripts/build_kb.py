# -*- coding: utf-8 -*-
"""建库入口：python scripts/build_kb.py --game deepspace-pawnshop [--force]

游戏配置在 games/<slug>.json，新增游戏只需加一个配置文件和对应 guides/ 源。
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scrapers import ali213, gamersky, powerpyx, steam_guide, wikily
from scrapers.base import Fetcher

TODAY = dt.date.today().isoformat()
GAMES_DIR = ROOT / "games"


def load_games() -> dict:
    """读取 games/*.json，返回 {slug: config}。"""
    games = {}
    for p in sorted(GAMES_DIR.glob("*.json")):
        cfg = json.loads(p.read_text(encoding="utf-8"))
        slug = cfg.get("game") or p.stem
        games[slug] = cfg
    return games


def slugify(text: str, fallback: str) -> str:
    text = re.sub(r'[\\/:*?"<>|\s#`]+', "-", text.strip())
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:40] or fallback


def build_steam(game_cfg: dict, out_dir: Path, fetcher: Fetcher, force: bool) -> dict:
    guides_dir = out_dir / "guides" / "steam"
    guides_dir.mkdir(parents=True, exist_ok=True)
    items = steam_guide.discover_guides(fetcher, game_cfg["steam_appid"])
    zh_items = [g for g in items if g["zh"]]
    fetcher._note(f"Steam：发现 {len(items)} 篇，其中疑似中文 {len(zh_items)} 篇，开始抓正文")
    kept = []
    for it in zh_items:
        g = steam_guide.fetch_guide(fetcher, it["id"])
        if not g or not g["sections"]:
            fetcher._note(f"跳过 {it['id']}（无正文或抓取失败）")
            continue
        if not g["zh"]:
            fetcher._note(f"跳过 {it['id']}（正文中文占比不足）")
            continue
        fname = f"{g['id']}-{slugify(g['title'], g['id'])}.md"
        (guides_dir / fname).write_text(steam_guide.guide_to_markdown(g), encoding="utf-8")
        kept.append({"id": g["id"], "title": g["title"], "url": g["url"], "file": f"guides/steam/{fname}"})
    return {"count": len(kept), "items": kept}


def build_wikily(game_cfg: dict, out_dir: Path, fetcher: Fetcher, force: bool) -> dict:
    guides_dir = out_dir / "guides" / "wikily"
    guides_dir.mkdir(parents=True, exist_ok=True)
    slugs = wikily.discover_pages(fetcher, game_cfg["wikily_slug"])
    fetcher._note(f"Wikily：发现 {len(slugs)} 个页面，开始抓正文")
    kept = []
    for slug in slugs:
        p = wikily.fetch_page(fetcher, game_cfg["wikily_slug"], slug)
        if not p:
            fetcher._note(f"跳过 {slug}（无正文）")
            continue
        fname = f"{slug}.md"
        out_file = guides_dir / fname
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(wikily.page_to_markdown(p), encoding="utf-8")
        kept.append({"id": slug, "title": p["title"], "url": p["url"], "file": f"guides/wikily/{fname}"})
    return {"count": len(kept), "items": kept}


def main() -> int:
    games = load_games()
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True, choices=list(games))
    ap.add_argument("--force", action="store_true", help="忽略本地缓存强制重抓")
    args = ap.parse_args()

    cfg = games[args.game]
    out_dir = ROOT / "output" / args.game
    out_dir.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(ROOT / ".cache")

    def build_ali213(game_cfg: dict, out_dir: Path, fetcher: Fetcher, force: bool) -> dict:
        guides_dir = out_dir / "guides" / "ali213"
        guides_dir.mkdir(parents=True, exist_ok=True)
        articles = ali213.discover_articles(fetcher, game_cfg["ali213_zone"])
        fetcher._note(f"游民星空：发现 {len(articles)} 篇文章，开始抓正文")
        kept = []
        for art in articles:
            a = ali213.fetch_article(fetcher, art["path"])
            if not a:
                fetcher._note(f"跳过 {art['path']}（无正文）")
                continue
            fname = f"{a['id']}-{slugify(a['title'], a['id'])}.md"
            (guides_dir / fname).write_text(ali213.article_to_markdown(a), encoding="utf-8")
            kept.append({"id": a["id"], "title": a["title"], "url": a["url"], "file": f"guides/ali213/{fname}"})
        return {"count": len(kept), "items": kept}

    def build_gamersky(game_cfg: dict, out_dir: Path, fetcher: Fetcher, force: bool) -> dict:
        guides_dir = out_dir / "guides" / "gamersky"
        guides_dir.mkdir(parents=True, exist_ok=True)
        articles = gamersky.discover_articles(fetcher, game_cfg["gamersky_tab"])
        # 标题预筛：跳过预告解析/新闻，只收真攻略
        guides = [a for a in articles if gamersky.is_guide_title(a["title"])]
        skipped = len(articles) - len(guides)
        fetcher._note(
            f"游民星空：发现 {len(articles)} 篇，预筛后 {len(guides)} 篇（跳过 {skipped} 篇新闻/预告），开始抓正文")
        kept = []
        for art in guides:
            a = gamersky.fetch_article(fetcher, art["path"])
            if not a:
                fetcher._note(f"跳过 {art['path']}（无正文）")
                continue
            fname = f"{a['id']}-{slugify(a['title'], a['id'])}.md"
            (guides_dir / fname).write_text(gamersky.article_to_markdown(a), encoding="utf-8")
            kept.append({"id": a["id"], "title": a["title"], "url": a["url"], "file": f"guides/gamersky/{fname}"})
        # 全任务流程 roadbook（静态页仅含已渲染章节，任务清单记进索引）
        if game_cfg.get("gamersky_roadbook"):
            rb = gamersky.fetch_roadbook(fetcher, game_cfg["gamersky_roadbook"])
            if rb:
                fname = "roadbook-全任务流程图文攻略.md"
                note = (f"- 来源: {rb['url']}\n- 语言: 中文\n- 覆盖: 静态页已渲染的任务"
                        f"（{len(rb['tasks'])} 个；roadbook 分章 JS 动态加载，后续章节待浏览器补采）\n")
                (guides_dir / fname).write_text(
                    f"# {rb['title']}\n\n{note}\n{rb['body']}\n", encoding="utf-8")
                kept.append({"id": "roadbook", "title": rb["title"], "url": rb["url"],
                             "file": f"guides/gamersky/{fname}", "tasks": rb["tasks"]})
                fetcher._note(f"游民星空 roadbook：{len(rb['tasks'])} 个任务卡片入库")
        return {"count": len(kept), "items": kept}

    def build_powerpyx(game_cfg: dict, out_dir: Path, fetcher: Fetcher, force: bool) -> dict:
        guides_dir = out_dir / "guides" / "powerpyx"
        guides_dir.mkdir(parents=True, exist_ok=True)
        articles = powerpyx.discover_articles(fetcher, game_cfg["powerpyx_hub"])
        fetcher._note(f"PowerPyx：发现 {len(articles)} 篇攻略，开始抓正文")
        kept = []
        for art in articles:
            a = powerpyx.fetch_article(fetcher, art["path"])
            if not a:
                fetcher._note(f"跳过 {art['path']}（无正文）")
                continue
            fname = f"{slugify(a['title'], a['id'])}.md"
            (guides_dir / fname).write_text(powerpyx.article_to_markdown(a), encoding="utf-8")
            kept.append({"id": a["id"], "title": a["title"], "url": a["url"], "file": f"guides/powerpyx/{fname}"})
        return {"count": len(kept), "items": kept}

    # 按配置启用各源；缺配置键的源跳过（新游戏不用一次接齐所有源）
    results = {}
    if cfg.get("steam_appid"):
        results["steam"] = build_steam(cfg, out_dir, fetcher, args.force)
    if cfg.get("wikily_slug"):
        results["wikily"] = build_wikily(cfg, out_dir, fetcher, args.force)
    if cfg.get("ali213_zone"):
        results["ali213"] = build_ali213(cfg, out_dir, fetcher, args.force)
    if cfg.get("gamersky_tab"):
        results["gamersky"] = build_gamersky(cfg, out_dir, fetcher, args.force)
    if cfg.get("powerpyx_hub"):
        results["powerpyx"] = build_powerpyx(cfg, out_dir, fetcher, args.force)

    # 手动采集源（B站/小黑盒等，浏览器辅助），只统计已有产物，不参与自动管线。
    # guides/ 下除自动管线源外的目录都算手动源；旧 _index.json 同 file 条目原样保留（保住 url/作者等富字段）
    old_by_file: dict[str, dict] = {}
    old_index_path = out_dir / "_index.json"
    if old_index_path.exists():
        try:
            old_idx = json.loads(old_index_path.read_text(encoding="utf-8"))
            for items in old_idx.get("guides", {}).values():
                for it in items if isinstance(items, list) else []:
                    if isinstance(it, dict) and it.get("file"):
                        old_by_file[it["file"]] = it
        except (json.JSONDecodeError, OSError):
            pass
    auto_ids = {"steam", "wikily", "ali213", "gamersky", "powerpyx"}
    manual: dict[str, list[dict]] = {}
    for d in sorted((out_dir / "guides").glob("*")):
        if not d.is_dir() or d.name in auto_ids:
            continue
        items = []
        for f in sorted(d.glob("*.md")):
            rel = f"guides/{d.name}/{f.name}"
            if rel in old_by_file:
                items.append(old_by_file[rel])
                continue
            first = f.read_text(encoding="utf-8", errors="ignore").splitlines()[0].lstrip("# ").strip()
            items.append({"id": f.stem, "title": first, "file": rel})
        if items:
            manual[d.name] = items

    # 索引 README.md
    lines = [f"# {cfg['name_zh']}（{cfg['name_en']}）攻略知识库", "", f"采集日期：{TODAY}", ""]
    for src, res in results.items():
        lines.append(f"## {src}（{res['count']} 篇）")
        lines.append("")
        for it in res["items"]:
            lines.append(f"- [{it['title']}]({it['file']})")
        lines.append("")
    for mid, items in manual.items():
        lines.append(f"## {mid}（手动采集，{len(items)} 篇）")
        lines.append("")
        for it in items:
            lines.append(f"- [{it['title']}]({it['file']})")
        lines.append("")
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")

    # _index.json：游戏元数据 + 资料源清单 + 文章索引
    sources = []
    for s in cfg["sources"]:
        if s.get("pipeline") and s["id"] in results:
            sources.append({"id": s["id"], "status": "active", "note": s.get("note", ""),
                            "scraped_at": TODAY, "count": results[s["id"]]["count"]})
        elif s.get("pipeline"):
            sources.append({"id": s["id"], "status": "not-configured", "note": s.get("note", "")})
        elif s["id"] in manual:
            sources.append({"id": s["id"], "status": "active", "note": s.get("note", ""),
                            "scraped_at": TODAY, "count": len(manual[s["id"]])})
        else:
            sources.append({"id": s["id"], "status": s.get("status", "skipped"), "note": s.get("note", "")})
    known_ids = {s["id"] for s in sources}
    for mid, items in manual.items():  # 手动源但配置里没登记的，兜底收进清单
        if mid not in known_ids:
            sources.append({"id": mid, "status": "active",
                            "note": "手动采集源（guides/ 目录自动统计）",
                            "scraped_at": TODAY, "count": len(items)})
    guides = {src: res["items"] for src, res in results.items()}
    guides.update(manual)
    # 结构化数据统计（data/*.json，供 list_games 与问答技能报告覆盖量）
    data_dir = out_dir / "data"
    data_stats, data_total = {}, 0
    if data_dir.is_dir():
        for f in sorted(data_dir.glob("*.json")):
            if f.name.startswith("_"):
                continue
            try:
                n = len(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
            data_stats[f.stem] = n
            data_total += n
    index = {
        "game": args.game,
        "name_zh": cfg["name_zh"],
        "name_en": cfg["name_en"],
        "steam_appid": cfg.get("steam_appid"),
        "scraped_at": TODAY,
        "sources": sources,
        "guides": guides,
        "data": {"categories": data_stats, "total": data_total, "extracted_at": TODAY},
    }
    (out_dir / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 汇总只打印实际跑了的源（不同游戏接入的源不一样）
    parts = [f"{sid} {res['count']} 篇" for sid, res in results.items()]
    parts += [f"{mid} {len(items)} 篇" for mid, items in manual.items()]
    print("完成：" + ("、".join(parts) if parts else "无采集源") + f" → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
