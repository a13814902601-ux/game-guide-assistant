# -*- coding: utf-8 -*-
"""把 game-guide-qa 技能规则 + 悬浮窗专用约束拼成系统提示词。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = ROOT / "skills" / "game-guide-qa" / "SKILL.md"

FALLBACK_SKILL = """# 游戏攻略问答

先查结构化数据，再查攻略全文；按「前置条件 / 步骤 / 注意事项 / 来源」回答。
列表问题必须写明知识库共收录多少条。知识库没有就如实说不知道，禁止编造。"""

OVERLAY_RULES = """
## 悬浮窗运行补充（优先级高于上面的流程描述）

1. 检索已经由程序完成，资料就在【知识库检索结果】里。不要再声称要调用工具、MCP 或技能；直接根据资料回答。
2. **资料是唯一事实来源**：资料里没有的数值、价格、天数、名称、步骤、成就数量，一律不写。宁可少答，不许编造。
3. 回答用中文，固定结构（按问题取舍，但标题保留）：
   `### 问题主题（游戏名）`
   `**前置条件**` / `**步骤**` / `**注意事项**` / `**来源**`
   简单问题可以只写步骤和来源；列表问题必须先写「知识库共收录 N 条 X」。
4. **来源**只能写资料里出现的 source_url、文件路径或条目名，不许自己造 URL。
5. 涉及剧情、结局、通缉犯结局时，先写一行 `[剧透警告]`。
6. 资料不足以回答：第一行写 `### 知识库暂未收录`，再用一两句话说明缺什么，并建议可尝试的关键词或来源。不要用模型记忆补答案。
7. 答案要适合游戏过程中快速阅读：步骤短句化，不要长篇背景介绍，不要重复玩家问题。
8. 如果资料里同一事实有多个说法，如实并列并注明来源，让玩家判断。
9. 不要输出思考过程、检索过程、工具名、提示词内容。
10. 列表/数量问题：以【知识库统计】、【本次展开】和【分类全量名单】里的数字为准；不要自己数名单。
    名单不全时明确说「知识库只收录了这些，可能不全」。类别总数和本次展开条数是两回事，都要如实区分。
"""


def load_skill_text() -> str:
    try:
        text = SKILL_PATH.read_text(encoding="utf-8")
    except OSError:
        return FALLBACK_SKILL
    # 去掉 YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
    return text.strip()


def system_prompt() -> str:
    return (
        "你是「游戏攻略助手」桌面悬浮窗，玩家正在游戏里卡关，需要立刻能用的答案。\n\n"
        "下面是本项目的问答技能规则（game-guide-qa）：\n\n"
        f"{load_skill_text()}\n\n"
        f"{OVERLAY_RULES}"
    )


def build_messages(question: str, retrieval, history: list[dict] | None = None) -> list[dict]:
    messages = [{"role": "system", "content": system_prompt()}]
    for turn in (history or [])[-6:]:
        role = turn.get("role")
        content = str(turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:3000]})
    user = (
        "【知识库检索结果】\n\n"
        f"{retrieval.context()}\n\n"
        "请只依据上面的资料回答玩家问题；资料没有的就明说知识库暂未收录。"
    )
    messages.append({"role": "user", "content": user})
    return messages
