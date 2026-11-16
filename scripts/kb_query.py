# -*- coding: utf-8 -*-
"""知识库 CLI 调试入口。

用法：
    python scripts/kb_query.py --list-games
    python scripts/kb_query.py --game deepspace-pawnshop --category achievements --query 头奖
    python scripts/kb_query.py --game deepspace-pawnshop --guides 芬太片
    python scripts/kb_query.py --game deepspace-pawnshop --show bosses --name 改造
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import kb.query as q


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-games", action="store_true")
    ap.add_argument("--game")
    ap.add_argument("--category", choices=q.CATEGORIES)
    ap.add_argument("--query")
    ap.add_argument("--guides")
    ap.add_argument("--show", choices=q.CATEGORIES)
    ap.add_argument("--name")
    args = ap.parse_args()

    if args.list_games:
        print(json.dumps(q.list_games(), ensure_ascii=False, indent=1))
        return 0
    if not args.game:
        ap.error("需要 --game（或 --list-games）")
    if args.query:
        res = q.search_data(args.game, args.query, args.category)
        print(f"命中 {len(res)} 条：")
        for e in res:
            print(f"- [{e['category']}] {e['name']}" + (f" / {e['name_en']}" if e.get("name_en") else ""))
        return 0
    if args.guides:
        res = q.search_guides(args.game, args.guides)
        print(f"命中 {len(res)} 篇：")
        for r in res:
            print(f"- {r['title']}  ({r['file']})")
            for m in r["matches"]:
                print(f"    {m}")
        return 0
    if args.show and args.name:
        e = q.get_entry(args.game, args.show, args.name)
        print(json.dumps(e, ensure_ascii=False, indent=1) if e else "未找到")
        return 0 if e else 1
    ap.error("需要 --query / --guides / --show+--name 之一")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
