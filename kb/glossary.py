# -*- coding: utf-8 -*-
"""中英游戏术语表：查询时自动把中文关键词桥接到英文同义词，反之亦然。

知识库里有大量英文 wiki 内容（Wikily），中文关键词直接搜会漏——
「通缉犯」搜不中 "Wanted"。这里维护人工核对过的核心术语映射。
"""

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


def expand(keyword: str) -> list[str]:
    """返回关键词本身 + 双向映射到的同义词（去重）。"""
    kws = [keyword]
    low = keyword.lower()
    for zh, en in PAIRS:
        if zh in keyword:
            if en.lower() not in low:
                kws.append(en)
        if en.lower() in low and len(en) >= 4:
            if zh not in keyword:
                kws.append(zh)
    return list(dict.fromkeys(kws))
