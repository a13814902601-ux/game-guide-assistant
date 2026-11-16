# -*- coding: utf-8 -*-
"""知识库检索桥：复用 MCP 服务器同一套 kb/query.py，不做网络请求。

检索策略：
1. 从问题里抽候选词（术语表命中、去疑问词后的短语、2~6 字 n-gram）；
2. 结构化数据按分类逐项检索并加权合并（长词/术语权重更高）；
3. 只对强候选词做全文检索，避免「土豆」这类泛词把无关攻略捞进来；
4. 组装成带来源、带统计的上下文，交给 LLM 严格照资料回答。
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kb import query as kbq  # noqa: E402
from kb.glossary import PAIRS  # noqa: E402

CATEGORIES = ("quests", "items", "bosses", "achievements", "recipes", "characters")
MIN_ENTRY_SCORE = 4.0
MAX_ENTRIES = 10
MAX_GUIDES = 3
MAX_ENTRY_CHARS = 1500
MAX_EXCERPT_CHARS = 2600
MAX_CONTEXT_CHARS = 18000

STOP_PHRASES = sorted(
    [
        "请问", "想问一下", "问一下", "帮我查一下", "帮我查", "帮我看看", "帮我",
        "告诉我", "我想知道", "想知道", "麻烦问",
        "游戏里面", "游戏里的", "游戏中的", "游戏里", "这个游戏", "本游戏",
        "怎么样", "怎么办", "怎么玩", "怎么获得", "怎么获取", "怎么拿", "怎么解锁",
        "怎么", "怎样", "如何", "在哪里", "在哪儿", "在哪", "哪里",
        "哪几个", "哪一个", "哪种", "哪个", "哪些",
        "有多少个", "有多少", "有几个", "有哪几个", "有什么", "都有什么", "都有哪些",
        "是什么", "干什么", "干嘛用的", "有什么用", "为什么",
        "能不能", "可不可以", "可以吗", "需不需要", "需要什么",
        "一下", "一点", "一些", "请问", "谢谢", "多谢",
        "吗", "呢", "吧", "啊", "呀", "哦", "嘛",
        "的", "了",
    ],
    key=len,
    reverse=True,
)

STOP_GRAMS = {
    "怎么", "如何", "什么", "哪些", "哪个", "多少", "几个", "游戏", "里面",
    "这个", "那个", "可以", "需要", "一个", "一下", "告诉", "帮我", "请问",
    "现在", "然后", "还是", "就是", "不是", "有没有", "什么样", "怎么办",
    "怎样", "哪里", "在哪", "为什么", "东西", "时候",
}

LIST_WORDS = ("几个", "哪些", "哪几个", "全部", "所有", "名单", "一览", "都有", "多少", "一共", "总共", "几种")

# 问题里出现这些词时，优先从对应分类里找详细条目
CATEGORY_HINTS = (
    ("characters", ("通缉犯", "通缉", "wanted", "bounty", "角色", "人物", "npc")),
    ("recipes", ("配方", "制作", "合成", "熔炉", "recipe", "craft")),
    ("achievements", ("成就", "achievement", "奖杯")),
    ("quests", ("任务", "委托", "剧情", "结局", "事件", "quest", "mission", "ending")),
    ("bosses", ("危机", "强敌", "boss", "治安部", "敌人")),
    ("items", ("道具", "物品", "item")),
)

CATEGORY_LABELS = {
    "quests": "任务/委托/事件",
    "items": "道具获取",
    "bosses": "危机/强敌",
    "achievements": "成就",
    "recipes": "配方",
    "characters": "角色/通缉犯",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"[^\w\u4e00-\u9fff·]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def strip_question_words(text: str) -> str:
    out = text
    for phrase in STOP_PHRASES:
        out = out.replace(phrase, " ")
    # 「熔炉配方有」这类去掉疑问词后残留的尾巴
    out = re.sub(r"(?<!\S)有(?!\S)", " ", out)
    chunks = []
    for chunk in out.split():
        if len(chunk) > 2 and chunk[-1] in "有的是了":
            chunk = chunk[:-1]
        if chunk:
            chunks.append(chunk)
    return re.sub(r"\s+", " ", " ".join(chunks)).strip()


def detect_intent_category(question: str) -> str | None:
    low = normalize(question).lower()
    for category, hints in CATEGORY_HINTS:
        for hint in hints:
            if hint.lower() in low:
                return category
    return None


def is_list_question(question: str) -> bool:
    return any(word in question for word in LIST_WORDS)


def candidate_terms(question: str) -> list[tuple[str, float]]:
    """返回 (候选词, 权重)，权重越高越可信。"""
    norm = normalize(question)
    if not norm:
        return []
    core = strip_question_words(norm)
    weighted: dict[str, float] = {}

    def add(term: str, weight: float) -> None:
        term = term.strip()
        if len(term) < 2 or term.isdigit():
            return
        weighted[term] = max(weighted.get(term, 0.0), weight)

    # 1) 术语表命中（最可信）
    low = norm.lower()
    for zh, en in PAIRS:
        if zh in norm:
            add(zh, 3.0)
            if len(en) >= 4 and en.lower() not in low:
                add(en, 2.6)
        if len(en) >= 4 and re.search(rf"\b{re.escape(en.lower())}\b", low):
            add(en, 3.0)
            if zh not in norm:
                add(zh, 2.6)

    # 2) 去疑问词后的短语
    for chunk in core.split():
        if 2 <= len(chunk) <= 24:
            add(chunk, 2.2)
            # 中文短句再切 2~6 字 n-gram，给「水商怎么玩」「熔炉配方」兜底
            for n in range(min(6, len(chunk)), 1, -1):
                for i in range(0, len(chunk) - n + 1):
                    gram = chunk[i : i + n]
                    if gram in STOP_GRAMS:
                        continue
                    add(gram, 1.0 + 0.2 * (n - 2))

    # 3) 原问题整串（允许原文精确命中）
    add(norm, 1.0)
    ordered = sorted(weighted.items(), key=lambda kv: (-kv[1], -len(kv[0])))
    return ordered[:20]


def _entry_text(entry: dict) -> str:
    parts = [entry.get("name", ""), entry.get("name_en", ""), entry.get("group", "")]
    for key in ("prerequisites", "steps", "cautions"):
        value = entry.get(key)
        if isinstance(value, list):
            parts.extend(str(x) for x in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts)


def _as_lines(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if value:
        return [str(value).strip()]
    return []


def _render_entry(category: str, entry: dict, index: int) -> str:
    lines = [f"### {index}. [{category}] {entry.get('name', '未命名')}"]
    if entry.get("name_en"):
        lines.append(f"- 英文名：{entry['name_en']}")
    if entry.get("group"):
        lines.append(f"- 分组：{entry['group']}")
    for label, key in (("前置条件", "prerequisites"), ("步骤", "steps"), ("注意事项", "cautions")):
        values = _as_lines(entry.get(key))
        if not values:
            continue
        lines.append(f"- {label}：")
        for i, value in enumerate(values, 1):
            prefix = f"{i}. " if key == "steps" else "- "
            lines.append(f"  {prefix}{value}")
    meta = []
    if entry.get("game_version"):
        meta.append(f"版本 {entry['game_version']}")
    if entry.get("verified_date"):
        meta.append(f"核对日期 {entry['verified_date']}")
    if entry.get("source_url"):
        meta.append(str(entry["source_url"]))
    if meta:
        lines.append("- 来源：" + "（" + "；".join(meta) + "）")
    text = "\n".join(lines)
    if len(text) > MAX_ENTRY_CHARS:
        text = text[:MAX_ENTRY_CHARS] + "\n…（本条已截断）"
    return text


def _excerpt(text: str, line_no: int, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    lines = text.splitlines()
    start = max(0, line_no - 1 - 12)
    end = min(len(lines), line_no - 1 + 60)
    chunk = "\n".join(lines[start:end])
    if len(chunk) > max_chars:
        chunk = chunk[:max_chars] + "\n…（摘录已截断）"
    return chunk


def _load_stats(game: str) -> dict:
    try:
        path = kbq._game_dir(game) / "_index.json"  # 与 MCP 共用同一份索引
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return data


@dataclass
class Retrieval:
    question: str
    game: str
    game_name: str = ""
    entries: list[dict] = field(default_factory=list)  # {"category", "entry", "score"}
    guides: list[dict] = field(default_factory=list)   # {"file", "title", "excerpt", "score"}
    stats: dict = field(default_factory=dict)
    terms: list[tuple[str, float]] = field(default_factory=list)
    last_question: str | None = None
    intent_category: str | None = None
    list_question: bool = False
    category_index: dict = field(default_factory=dict)  # category -> {"total","unique"}

    @property
    def empty(self) -> bool:
        return not self.entries and not self.guides

    @property
    def summary(self) -> str:
        if self.empty:
            return "知识库没有命中"
        parts = []
        if self.entries:
            parts.append(f"{len(self.entries)} 条结构化数据")
        if self.guides:
            parts.append(f"{len(self.guides)} 篇攻略全文")
        return "命中 " + " + ".join(parts)

    @property
    def total_counts(self) -> str:
        data = self.stats.get("data", {}) if self.stats else {}
        cats = data.get("categories", {}) or {}
        cat_text = "、".join(f"{k} {v}" for k, v in cats.items())
        guide_total = sum(len(v) for v in (self.stats.get("guides") or {}).values())
        total = data.get("total", "?")
        return f"结构化数据 {total} 条（{cat_text}）；攻略全文 {guide_total} 篇"

    def sources(self) -> list[str]:
        out = []
        for item in self.entries:
            entry = item["entry"]
            url = entry.get("source_url") or ""
            out.append(f"[{item['category']}] {entry.get('name', '')}" + (f" — {url}" if url else ""))
        for guide in self.guides:
            out.append(f"[攻略全文] {guide['title']} — {guide['file']}")
        return out

    def context(self) -> str:
        lines = [
            f"【游戏】{self.game_name or self.game}（知识库 slug：{self.game}）",
            f"【知识库统计】{self.total_counts}",
            f"【本次展开】结构化条目 {len(self.entries)} 条；攻略原文摘录 {len(self.guides)} 篇。"
            "回答里要引用数量时用这两个数字和上面的统计，不要自己数名单。",
            f"【玩家问题】{self.question}",
        ]
        if self.last_question and self.last_question != self.question:
            lines.append(f"【上一轮问题，仅供理解指代】{self.last_question}")
        if self.intent_category and self.list_question and self.category_index:
            info = self.category_index.get(self.intent_category)
            if info:
                label = CATEGORY_LABELS.get(self.intent_category, self.intent_category)
                names = "、".join(info["unique"])
                lines.append(
                    f"【{label}分类全量名单】共 {info['total']} 条，去重后 {len(info['unique'])} 个名称：{names}"
                )
        if self.entries:
            lines.append("\n【结构化条目】")
            for i, item in enumerate(self.entries, 1):
                lines.append(_render_entry(item["category"], item["entry"], i))
        if self.guides:
            lines.append("\n【攻略原文摘录】")
            for i, guide in enumerate(self.guides, 1):
                lines.append(f"### {i}. {guide['title']}（文件：{guide['file']}）")
                lines.append(guide["excerpt"])
        text = "\n\n".join(lines)
        if len(text) > MAX_CONTEXT_CHARS:
            text = text[:MAX_CONTEXT_CHARS] + "\n\n…（检索上下文过长，已截断）"
        return text


def _search_entries(game: str, terms: list[tuple[str, float]], preferred: str | None = None) -> list[dict]:
    scores: dict[tuple[str, str], float] = {}
    store: dict[tuple[str, str], tuple[str, dict]] = {}
    for term, weight in terms:
        for category in CATEGORIES:
            try:
                hits = kbq.search_data(game, term, category=category, limit=12)
            except (FileNotFoundError, ValueError):
                return []
            cat_boost = 1.8 if preferred and category == preferred else 1.0
            for rank, entry in enumerate(hits):
                key = (category, entry.get("id") or entry.get("name") or str(rank))
                score = weight * (1.0 + 1.0 / (rank + 1)) * cat_boost
                name = f"{entry.get('name', '')} {entry.get('name_en', '')}".lower()
                if term.lower() in name:
                    score *= 1.5
                scores[key] = scores.get(key, 0.0) + score
                store[key] = (category, entry)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    results = []
    for key, score in ranked:
        if score < MIN_ENTRY_SCORE:
            continue
        category, entry = store[key]
        results.append({"category": category, "entry": entry, "score": score})
        if len(results) >= MAX_ENTRIES:
            break
    return results


def _name_relevant(item: dict, terms: list[tuple[str, float]]) -> bool:
    entry = item["entry"]
    name = f"{entry.get('name', '')} {entry.get('name_en', '')}".lower()
    return any(term.lower() in name for term, weight in terms if weight >= 2.0 and len(term) >= 2)


def _search_guides(game: str, terms: list[tuple[str, float]]) -> list[dict]:
    strong = [(t, w) for t, w in terms if w >= 2.0 and len(t) >= 2]
    if not strong:
        return []
    merged: dict[str, dict] = {}
    for term, weight in strong[:4]:
        try:
            hits = kbq.search_guides(game, term, limit=6)
        except (FileNotFoundError, ValueError):
            return []
        for rank, hit in enumerate(hits):
            file = hit["file"]
            haystack = (hit.get("title", "") + "\n" + "\n".join(hit.get("matches", []))).lower()
            if term.lower() not in haystack:
                continue
            score = weight * (1.0 + 1.0 / (rank + 1))
            if file in merged:
                merged[file]["score"] += score
            else:
                merged[file] = {"file": file, "title": hit.get("title", file), "score": score, "line": None}
                for line in hit.get("matches", []):
                    m = re.match(r"L(\d+):", line)
                    if m:
                        merged[file]["line"] = int(m.group(1))
                        break
    ranked = sorted(merged.values(), key=lambda item: -item["score"])[:MAX_GUIDES]
    guides = []
    for item in ranked:
        data = kbq.get_guide(game, item["file"])
        if not data:
            continue
        line_no = item.get("line") or 1
        guides.append(
            {
                "file": item["file"],
                "title": item["title"],
                "score": item["score"],
                "excerpt": _excerpt(data["content"], line_no),
            }
        )
    return guides


def _category_index(game: str, category: str) -> dict:
    try:
        entries = kbq._load_entries(game, category)
    except (FileNotFoundError, ValueError):
        return {}
    names: list[str] = []
    seen = set()
    for entry in entries:
        name = str(entry.get("name") or entry.get("name_en") or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return {"total": len(entries), "unique": names}


def normalize_kb_root(path: str | Path | None) -> Path | None:
    """接受 output 根目录、项目根目录或单个游戏目录，统一成 output 根目录。"""
    if not path:
        return None
    p = Path(path).expanduser()
    if (p / "_index.json").is_file():  # 用户选中了 output/<game>
        return p.parent.resolve()
    if (p / "output").is_dir() and any((p / "output").glob("*/_index.json")):
        return (p / "output").resolve()  # 用户选中了项目根目录
    return p.resolve()


def auto_output_root() -> Path | None:
    """按优先级找外部知识库：环境变量 → exe 同目录 → 上一级 → APPDATA → 项目目录。"""
    candidates: list[Path] = []
    env = os.environ.get("GGA_OUTPUT_DIR") or os.environ.get("KB_OUTPUT_DIR")
    if env:
        candidates.append(Path(env))
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([exe_dir / "output", exe_dir.parent / "output"])
    candidates.append(Path(os.environ.get("APPDATA") or Path.home()) / "GameGuideAssistant" / "output")
    candidates.append(ROOT / "output")
    for candidate in candidates:
        root = normalize_kb_root(candidate)
        if root and root.is_dir() and any(root.glob("*/_index.json")):
            return root
    return None


def set_output_root(path: str | Path | None) -> Path | None:
    root = normalize_kb_root(path) if path else auto_output_root()
    if root is not None:
        kbq.set_output_dir(root)
    return root


def current_output_root() -> Path:
    return kbq.get_output_dir()


def games() -> list[dict]:
    try:
        return kbq.list_games()
    except Exception:
        return []


def retrieve(game: str, question: str, last_question: str | None = None) -> Retrieval:
    terms = candidate_terms(question)
    intent = detect_intent_category(question)
    list_q = is_list_question(question)
    result = Retrieval(
        question=question,
        game=game,
        terms=terms,
        last_question=last_question,
        intent_category=intent,
        list_question=list_q,
    )
    stats = _load_stats(game)
    result.stats = stats
    result.game_name = stats.get("name_zh") or stats.get("game") or game
    result.entries = _search_entries(game, terms, preferred=intent)
    if intent:
        idx = _category_index(game, intent)
        if list_q or idx.get("total", 99) <= 20:
            result.category_index[intent] = idx
    # 列表类问题只保留目标分类的详细条目，避免「配方」命中其他分类的正文
    if list_q and intent:
        preferred_entries = [item for item in result.entries if item["category"] == intent]
        if preferred_entries:
            result.entries = preferred_entries
    # 指代型追问（「那第二个呢」）单独检索为空时，带上上一轮问题再试一次
    if not result.entries and last_question and last_question != question:
        extra_terms = candidate_terms(f"{last_question} {question}")
        result.entries = _search_entries(game, extra_terms, preferred=intent)
        if result.entries:
            result.terms = extra_terms
    result.guides = _search_guides(game, result.terms)
    # 没有分类意图、条目名也不含强关键词时，结构化命中多半是正文噪音（如「存档」），
    # 有全文攻略就只给攻略，避免 LLM 拿无关条目硬答。
    if result.entries and result.guides and not intent:
        if not any(_name_relevant(item, result.terms) for item in result.entries[:3]):
            result.entries = []
    if result.empty and last_question and last_question != question:
        extra_terms = candidate_terms(f"{last_question} {question}")
        result.entries = _search_entries(game, extra_terms, preferred=intent)
        result.guides = _search_guides(game, extra_terms)
        if not result.empty:
            result.terms = extra_terms
    return result


def no_kb_text(current: str | None = None) -> str:
    where = f"\n\n当前路径：`{current}`" if current else ""
    return (
        "### 未找到攻略库\n\n"
        "悬浮窗没有加载到知识库。攻略库归 MCP 所有，exe 不内置数据，需要外挂 `output` 目录。\n\n"
        "**怎么做**\n"
        "- 打开设置 → 知识库 → 选择项目里的 `output` 目录\n"
        "- 或者把 `output` 目录放到 exe 旁边，重启悬浮窗\n"
        "- MCP 服务器也可以用 `GGA_OUTPUT_DIR` 指向同一个目录"
        f"{where}"
    )


def refusal_text(question: str, game_name: str) -> str:
    """知识库没命中时的固定回复，GUI 与 CLI 共用。"""
    return (
        f"### 知识库暂未收录\n\n"
        f"没有在《{game_name}》攻略库里找到和「{question}」直接相关的内容，"
        f"所以我不能凭记忆编答案。\n\n"
        "**可以试试**\n"
        "- 换个关键词：通缉犯、水商、成就、配方、存档、房租\n"
        "- 或者先问「新手怎么开荒」，再顺着问具体任务\n\n"
        "**来源**：本地知识库（未命中）"
    )


def suggested_questions(game: str) -> list[str]:
    """空态示例问题，按知识库实际内容给。"""
    stats = _load_stats(game)
    name = stats.get("name_zh") or "这个游戏"
    return [
        "通缉犯有哪几个？",
        "水商怎么玩？",
        "一共有多少个成就？",
        "熔炉配方有哪些？",
        f"{name}新手怎么开荒？",
    ][:4]
