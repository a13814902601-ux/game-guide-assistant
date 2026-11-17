# -*- coding: utf-8 -*-
"""中英游戏术语表：查询时自动把中文关键词桥接到英文同义词，反之亦然。

知识库里有大量英文 wiki 内容（Wikily），中文关键词直接搜会漏——
「通缉犯」搜不中 "Wanted"。这里维护人工核对过的核心术语映射。

另外每个游戏的结构化数据里都有 name / name_en 双语名，运行时自动抽成
该游戏的临时术语表（game_pairs），新游戏不用手写映射也能中英互搜。
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

PAIRS: list[tuple[str, str]] = [
    ("通缉犯", "wanted"),
    ("通缉", "wanted"),
    ("悬赏", "bounty"),
    ("改造人", "aug"),
    ("改造体", "aug"),
    ("成就", "achievement"),
    ("配方", "recipe"),
    ("制作", "crafting"),
    ("化学", "chemistry"),
    ("纯度", "purity"),
    ("水质", "water"),
    ("优质水", "premium water"),
    ("净水", "purification"),
    ("水培", "hydroponic"),
    ("水培系统", "hydroponic system"),
    ("熔炉", "furnace"),
    ("净水器", "water purifier"),
    ("蒸发器", "evaporator"),
    ("冰箱", "fridge"),
    ("陈化架", "agewell"),
    ("鉴定", "appraisal"),
    ("顾客", "customer"),
    ("角色", "character"),
    ("剧情", "storyline"),
    ("结局", "ending"),
    ("声望", "reputation"),
    ("派系", "faction"),
    ("治安部", "security"),
    ("案值", "case"),
    ("罚款", "fine"),
    ("监禁", "arrested"),
    ("处决", "executed"),
    ("赃物", "stolen"),
    ("违禁品", "contraband"),
    ("假货", "counterfeit"),
    ("赝品", "counterfeit"),
    ("模组", "module"),
    ("机器", "machine"),
    ("武器", "weapon"),
    ("食物", "food"),
    ("酒", "wine"),
    ("酿酒", "winemaking"),
    ("酒瓶", "wine bottle"),
    ("酵母", "yeast"),
    ("陈化", "aging"),
    ("花莓", "bloomberry"),
    ("荧光莓", "bloomberry"),
    ("布洛姆莓", "bloomberry"),
    ("种子", "seed"),
    ("酒精", "alcohol"),
    ("芬太片", "fentanyl"),
    ("营养果", "nutrifruit"),
    ("地契", "deed"),
    ("店铺", "store"),
    ("房租", "rent"),
    ("高利贷", "loan shark"),
    ("难度", "difficulty"),
    ("事件", "event"),
    ("市场", "market"),
    ("价格", "price"),
    ("概率", "chance"),
    ("幸运", "luck"),
    ("刮刮乐", "lottery"),
    ("存档", "save"),
    ("一天", "day"),
]


def _entry_pairs(entry: dict) -> list[tuple[str, str]]:
    """从一条结构化数据里抽出 (中文名, 英文名)，并附带去括号的短名。"""
    zh = str(entry.get("name") or "").strip()
    en = str(entry.get("name_en") or "").strip()
    if len(zh) < 2 or not en or zh.lower() == en.lower() or not re.search(r"[A-Za-z]", en):
        return []
    pairs = [(zh, en)]
    zh_short = re.sub(r"[（(][^）)]*[）)]", "", zh).strip()
    en_short = re.sub(r"[（(][^）)]*[）)]", " ", en)
    en_short = re.sub(r"\s+", " ", en_short).strip()
    if zh_short and en_short and (zh_short, en_short) != (zh, en):
        pairs.append((zh_short, en_short))
    return pairs


@lru_cache(maxsize=32)
def _load_game_pairs(data_dir: str, _key: tuple) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(Path(data_dir).glob("*.json")):
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for pair in _entry_pairs(entry):
                if pair not in seen:
                    seen.add(pair)
                    pairs.append(pair)
    return tuple(pairs)


def game_pairs(game_dir: str | Path) -> list[tuple[str, str]]:
    """读取某个游戏 data/*.json 的双语名，生成该游戏的动态术语表（带 mtime 缓存）。"""
    data_dir = Path(game_dir) / "data"
    try:
        files = sorted(data_dir.glob("*.json"))
        key = tuple((f.name, f.stat().st_mtime_ns) for f in files)
    except OSError:
        return []
    if not key:
        return []
    return list(_load_game_pairs(str(data_dir), key))


def expand(keyword: str, extra_pairs: list[tuple[str, str]] | None = None) -> list[str]:
    """返回关键词本身 + 双向映射到的同义词（去重）。

    extra_pairs 用于传入当前游戏 data 里自动抽出的双语名，静态表作为兜底。
    """
    kws = [keyword]
    low = keyword.lower()
    pairs = list(PAIRS)
    if extra_pairs:
        pairs.extend(extra_pairs)
    for zh, en in pairs:
        if zh in keyword:
            if en.lower() not in low:
                kws.append(en)
        if en.lower() in low and len(en) >= 4:
            if zh not in keyword:
                kws.append(zh)
    return list(dict.fromkeys(kws))
