# -*- coding: utf-8 -*-
"""阶段2数据装配（程序化部分）：wikily 配方表 → data/recipes.json（中英双语）。

用法：python scripts/build_data.py --game deepspace-pawnshop
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.translate_terms import translate_terms

TODAY = dt.date.today().isoformat()
SOURCE_URL = "https://wikily.gg/probably-stolen/crafting-recipes"


def parse_recipe_table(md_path: Path) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple] = set()
    for line in md_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6:
            continue
        product, inputs, machine, makes, needs, value = cells[:6]
        # 跳过表头/分隔行/空行
        if not product or product in ("Inputs", "---") or set(product) <= {"-"}:
            continue
        key = (product, inputs, machine)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name_en": product,
                "inputs_en": inputs,
                "machine_en": machine,
                "makes_en": makes,
                "needs_en": needs,
                "value_en": value,
            }
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="deepspace-pawnshop")
    args = ap.parse_args()
    out_dir = ROOT / "output" / args.game
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "guides" / "wikily" / "crafting-recipes.md"
    rows = parse_recipe_table(md_path)
    print(f"解析配方表：{len(rows)} 条（去重后）")

    # 收集待翻译术语：产品名 + 机器名 + 原料短语
    terms = [r["name_en"] for r in rows]
    terms += [r["machine_en"] for r in rows]
    terms += [r["inputs_en"] for r in rows]
    cache_path = data_dir / "_translations.json"
    zh = translate_terms(terms, cache_path)

    entries = []
    for r in rows:
        machine_zh = "手工" if r["machine_en"].lower() == "by hand" else zh.get(r["machine_en"], r["machine_en"])
        product_zh = zh.get(r["name_en"], r["name_en"])
        inputs_zh = zh.get(r["inputs_en"], r["inputs_en"])
        prereqs = [f"需要机器：{machine_zh}"]
        notes = []
        if r["needs_en"]:
            notes.append(f"备注（原文）：{r['needs_en']}")
        steps = [
            f"原料：{inputs_zh}",
            f"机器：{machine_zh}（{r['machine_en']}）",
            f"产出：{r['makes_en'] or '见备注'}",
        ]
        if r["value_en"]:
            steps.append(f"参考价值：{r['value_en']}")
        entries.append(
            {
                "id": re.sub(r"[^a-z0-9]+", "-", r["name_en"].lower()).strip("-"),
                "name": product_zh,
                "name_en": r["name_en"],
                "category": "recipes",
                "prerequisites": prereqs,
                "steps": steps,
                "cautions": notes,
                "source_url": SOURCE_URL,
                "verified_date": TODAY,
                "game_version": "正式版（2026-10）",
            }
        )

    out = data_dir / "recipes.json"
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    zh_count = sum(1 for e in entries if e["name"] != e["name_en"])
    print(f"写出 {len(entries)} 条 → {out}（其中 {zh_count} 条拿到中文译名）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
