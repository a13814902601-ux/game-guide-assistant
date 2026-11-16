# -*- coding: utf-8 -*-
"""知识库查询核心：MCP 服务器与 CLI 共用。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"


def set_output_dir(path: str | Path) -> Path:
    """把知识库根目录切到外部目录（MCP 与悬浮窗共用同一份数据）。"""
    global OUTPUT
    OUTPUT = Path(path).expanduser().resolve()
    return OUTPUT


def get_output_dir() -> Path:
    return OUTPUT

from kb.glossary import expand as expand_terms

CATEGORIES = ("quests", "items", "bosses", "achievements", "recipes", "characters")


def _game_dir(game: str) -> Path:
    d = OUTPUT / game
    if not d.is_dir():
        raise FileNotFoundError(f"未知游戏：{game}（可用：{', '.join(list_games())}）")
    return d


def _load_index(game: str) -> dict:
    p = _game_dir(game) / "_index.json"
    return json.loads(p.read_text(encoding="utf-8"))


def list_games() -> list[dict]:
    games = []
    for idx in sorted(OUTPUT.glob("*/_index.json")):
        d = json.loads(idx.read_text(encoding="utf-8"))
        games.append(
            {
                "game": d.get("game", idx.parent.name),
                "name_zh": d.get("name_zh"),
                "name_en": d.get("name_en"),
                "data_total": d.get("data", {}).get("total"),
                "data_categories": d.get("data", {}).get("categories", {}),
                "guides": {k: len(v) for k, v in d.get("guides", {}).items()},
            }
        )
    return games


def _load_entries(game: str, category: str) -> list[dict]:
    if category not in CATEGORIES:
        raise ValueError(f"未知分类 {category}，可用：{', '.join(CATEGORIES)}")
    p = _game_dir(game) / "data" / f"{category}.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def _entry_text(e: dict) -> str:
    parts = [e.get("name", ""), e.get("name_en", ""), e.get("steam_description", ""),
             e.get("group", "")]
    for k in ("prerequisites", "steps", "cautions"):
        v = e.get(k)
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
        elif v:
            parts.append(str(v))
    return " ".join(parts)


def search_data(game: str, keyword: str, category: str | None = None, limit: int = 8) -> list[dict]:
    """按关键词检索结构化数据；命中名称加权，正文命中也返回。

    关键词会经术语表做中英双向扩展（通缉犯→wanted），英文内容也能被中文搜到。
    """
    kw = keyword.strip()
    if not kw:
        return []
    terms = expand_terms(kw)
    cats = [category] if category else CATEGORIES
    hits = []
    for cat in cats:
        for e in _load_entries(game, cat):
            name = e.get("name", "")
            name_en = e.get("name_en", "")
            body = _entry_text(e)
            score = 0
            for i, t in enumerate(terms):
                w = max(1, 10 - i)  # 原词权重最高，同义词递减
                t_low = t.lower()
                if t in name or t in name_en:
                    score += 10 * w
                if t_low in name.lower() or t_low in name_en.lower():
                    score += 5 * w
                score += body.lower().count(t_low) * w
            if score > 0:
                hits.append({"score": score, "entry": e})
    hits.sort(key=lambda h: (-h["score"], h["entry"].get("name", "")))
    return [h["entry"] for h in hits[:limit]]


def get_entry(game: str, category: str, name: str) -> dict | None:
    """按名称（或 id）精确/前缀匹配取整条数据。"""
    want = name.strip()
    entries = _load_entries(game, category)
    for e in entries:
        if e.get("id") == want or e.get("name") == want:
            return e
    low = want.lower()
    for e in entries:  # 前缀/包含匹配兜底
        if low in e.get("name", "").lower() or low in e.get("name_en", "").lower():
            return e
    return None


def search_guides(game: str, keyword: str, limit: int = 8) -> list[dict]:
    """全文检索攻略库，返回文件+命中行。关键词经术语表做中英双向扩展。"""
    kw = keyword.strip()
    if not kw:
        return []
    terms = expand_terms(kw)
    results = []
    for md in sorted(_game_dir(game).glob("guides/**/*.md")):
        try:
            lines = md.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        title = lines[0].lstrip("# ").strip() if lines else md.stem
        matched = []
        score = 0
        for i, line in enumerate(lines):
            line_low = line.lower()
            hit_terms = [t for t in terms if t in line or t.lower() in line_low]
            if hit_terms:
                # 标题命中加权 5：标题带关键词的攻略优先于散见多处的 wiki 页，
                # 避免 wikily 大体量页面把同分的中文攻略挤出 top-N
                score += len(hit_terms) + (5 if i == 0 else 0)
                matched.append(f"L{i + 1}: {line.strip()[:120]}")
                if len(matched) >= 3:
                    break
        if matched:
            rel = md.relative_to(_game_dir(game) / "guides").as_posix()
            results.append({"score": score, "file": rel, "title": title, "matches": matched})
    results.sort(key=lambda r: -r["score"])
    return results[:limit]


def get_guide(game: str, path: str) -> dict | None:
    """读取指定攻略全文（path 为相对 guides/ 的路径）。"""
    base = (_game_dir(game) / "guides").resolve()
    p = (base / path).resolve()
    if not str(p).startswith(str(base)) or not p.is_file():
        return None
    text = p.read_text(encoding="utf-8", errors="ignore")
    return {"file": path, "content": text}
