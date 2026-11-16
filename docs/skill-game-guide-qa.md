# Skill 功能与实现详解：game-guide-qa

> 项目：游戏攻略助手（Game Guide Assistant）
> 技能文件：`skills/game-guide-qa/SKILL.md`
> 适用宿主：ZCode（也适用于任何支持 Markdown 指令的 Agent 宿主）

## 一句话

**Skill 是这个项目的“策略层”**：它不存攻略、不实现查询，但规定 AI 在什么情况下查、
先查什么、怎么组织答案、什么时候必须承认“不知道”。

MCP 是工具，知识库是数据，悬浮窗是界面；**Skill 是让它们按同一套规程工作的操作手册**。

## 1. 它解决什么问题

没有 Skill 时，一个通用模型即使接了攻略库，也很容易出现这些问题：

| 问题 | 例子 | 后果 |
|---|---|---|
| 凭记忆补数值 | 房租“大概 300 吧” | 玩家按错数值规划，坏档 |
| 单条命中当全集 | 只搜到 1 个通缉犯就说“就这些” | 漏掉 8 个，答案错误 |
| 格式自由发挥 | 写成散文，没有来源 | 无法核对，不敢信 |
| 无来源 | 不标 `source_url` | 无法判断是攻略还是模型编的 |
| 剧透不警告 | 直接讲结局 | 破坏体验 |
| 知识库没有也硬答 | 问联机，答“支持” | 纯幻觉 |

`game-guide-qa` 把这些写成**可执行的硬规则**，让“有工具”变成“知道何时用、怎么用、用完怎么答”。

## 2. 文件结构与 frontmatter

`skills/game-guide-qa/SKILL.md` 由两部分组成：

```markdown
---
name: game-guide-qa
description: "游戏攻略问答。当用户询问任何游戏的任务怎么做、道具/配方怎么获取、
成就怎么解锁、Boss/危机/通缉犯/角色怎么应对、机制怎么玩时使用。先查 game-guide-kb
MCP 工具的结构化数据，再全文检索攻略库；按 前置条件/步骤/注意事项/来源 回答；
列表问题必须报告知识库收录数量；知识库没有就如实说不知道并给建议来源，禁止编造。"
---

# 游戏攻略问答
...
```

- `name`：技能标识，安装目录同名。
- `description`：**路由依据**。宿主根据这段描述判断“这个问题该不该用这个技能”。
  所以它必须写清楚触发场景（任务、道具、成就、Boss、机制）和核心约束（先查库、按格式、不编造）。
- 正文：真正给模型看的操作规程，包含问答流程、输出格式、硬规则。

> Skill 不是可执行插件，也不是 hook；它是一份宿主加载的 Markdown 指令。
> 真正“执行”的是宿主里的模型 + MCP 工具。

## 3. 在 ZCode 里怎么生效

### 安装

把整个目录复制到 ZCode 的全局技能目录：

```text
%USERPROFILE%\.zcode\skills\game-guide-qa\SKILL.md
```

然后**重启 ZCode 会话**（技能在会话启动时加载，改文件后不重启不会重新读取）。

### 触发

ZCode 读取 `description` 后，遇到这类问题会自动选择该技能：

- 「通缉犯有哪几个？」
- 「水商怎么玩？」
- 「头奖成就怎么拿？」
- 「改造人怎么识别？」
- 「房租什么时候交？」

如果没触发，优先检查：

1. 目录是否真的是 `...\.zcode\skills\game-guide-qa\SKILL.md`
2. frontmatter 是否完整（`name` / `description` 不能少）
3. 是否重启了会话
4. 宿主是否支持 Skill 机制（ZCode 支持）

## 4. 一次问答的执行流程

Skill 规定**严格按顺序**执行：

### 第一步：确认游戏

调 MCP 工具：

```text
list_games()
```

返回知识库里已收录的游戏、分类、数据量、全文篇数。

- 问题里的游戏不在列表里 → 说明只收录了哪些游戏，不假装会答。
- 游戏在列表里 → 继续。

### 第二步：先查结构化数据

```text
search_data(game, keyword, category?)
```

- `category` 可选：`quests`（任务/委托/事件/结局）、`items`（道具获取）、
  `bosses`（危机/强敌/治安）、`achievements`（成就）、`recipes`（配方）、
  `characters`（角色/通缉犯/NPC）
- 关键词会经过 `kb/glossary.py` 做中英双向扩展：
  「通缉犯」→ `wanted`、「改造人」→ `aug`、「结局」→ `ending`
- 命中后可用 `get_entry(game, category, name)` 取整条数据
  （前置条件、步骤、注意事项、来源、版本、核对日期）

### 第三步：结构化没命中，再查全文

```text
search_guides(game, keyword)
→ get_guide(game, path)
```

- 中文没命中时，Skill 要求把关键词换算成英文再搜一次（库里一半内容是英文 wiki）。
- 从原文整理答案，必须注明文件路径或原始 URL。

### 第四步：两处都没有 → 拒答

回答固定格式：

```text
### 知识库暂未收录

没有在《游戏名》攻略库里找到和「问题」直接相关的内容，所以我不能凭记忆编答案。

**可以试试**
- 换个关键词：...
- 或者先问「新手怎么开荒」，再顺着问具体任务

**来源**：本地知识库（未命中）
```

**关键点：拒答不调用模型编造**。在悬浮窗实现里，检索为空时直接返回这段话，
连 LLM 请求都不发（见 `overlay/core/kb_bridge.py` 的 `refusal_text` 与
`overlay/ui/main_window.py` 的 `AskWorker`）。

## 5. 输出格式（固定）

```markdown
### <问题主题>（<游戏名>）

**前置条件**
- ...

**步骤**
1. ...

**注意事项**
- ...

**来源**：<攻略名/数据条目>（<source_url 或 文件路径>）
```

设计理由：

- **前置条件**：让玩家先判断“我现在能不能做”。
- **步骤**：游戏过程中快速照做，短句优先。
- **注意事项**：坑、版本差异、不可逆操作。
- **来源**：可核对，防幻觉；悬浮窗里会把 http(s) 网址自动变成可点击链接。

## 6. 硬规则与实现位置

| 硬规则 | 具体要求 | 实现/体现 |
|---|---|---|
| 列表/数量问题 | 必须写「知识库共收录 N 条 X」；单条命中要声明“可能不全”；中英文各搜一次 | Skill 硬规则；`overlay/core/kb_bridge.py` 的 `is_list_question` / `category_index` |
| 来源 | 每个答案必须有来源；数据条目用 `source_url`，全文用文件路径/URL | Skill 硬规则；数据字段 `source_url` |
| 剧透 | 剧情/结局先写 `[剧透警告]` | Skill 硬规则 |
| 版本 | 如实转述 `game_version`、`verified_date`，过期要提醒 | Skill 硬规则；数据字段 |
| 数值 | 价格、天数、案值、悬赏只能来自知识库 | Skill 硬规则；检索上下文 |
| 未知游戏 | 说明知识库只收录哪些，不假装会答 | Skill 硬规则；`list_games` |
| MCP 不可用 | 降级到 `python scripts/kb_query.py ...` | Skill 硬规则 |
| 禁止编造 | 查不到说“暂未收录”，不给记忆答案 | Skill 硬规则；拒答分支不调 LLM |

### 为什么列表规则要单独写

列表问题最容易翻车：

- `search_data` 只返回 top-N，单条命中看起来像“全集”。
- 结构化数据可能只收录了部分（例如 9 名通缉犯里只结构化了 1 名）。
- 全文里可能还有汇总页。

所以 Skill 要求：

1. 先取全量（`search_data` 不限分类 + `search_guides` 中英文各一次）；
2. 回答必须报“知识库共收录 N 条”；
3. 只搜到 1 条时，必须声明“知识库只收录了这 1 条，可能不全”；
4. 数量与用户说法不一致时，如实报告两侧，让用户判断。

悬浮窗还额外做了“分类全量名单”：`kb_bridge.py` 在列表类问题里把该分类所有条目名
放进上下文，避免模型漏数。

## 7. 悬浮窗如何复用同一份 Skill

这是本项目的一个关键设计：**Skill 不只服务 ZCode，也被悬浮窗复用**。

### ZCode 路径

```text
用户提问
  → ZCode 按 description 选择 game-guide-qa
  → 模型按 SKILL.md 流程调用 MCP 工具
  → 模型按固定格式组织答案
```

### 悬浮窗路径

```text
用户提问
  → overlay/core/kb_bridge.py 先在本地检索（结构化 + 全文）
  → overlay/core/prompt.py 读取 SKILL.md（去掉 frontmatter）+ 悬浮窗补充规则
  → 把检索结果作为上下文，连同系统提示词发给 LLM
  → LLM 只负责“按规程组织答案”，不负责决定查什么
```

对应代码：

- `overlay/core/prompt.py`
  - `load_skill_text()`：读取 `skills/game-guide-qa/SKILL.md`，去掉 YAML frontmatter
  - `system_prompt()`：拼接 Skill 正文 + 悬浮窗补充规则
  - `build_messages()`：把 `retrieval.context()` 放进用户消息
- `overlay/core/kb_bridge.py`
  - `candidate_terms()`：问题清洗、术语扩展、n-gram
  - `_search_entries()` / `_search_guides()`：结构化优先、全文兜底
  - `Retrieval.context()`：带统计、分类名单、来源的上下文
  - `refusal_text()`：未命中固定话术
- `overlay/ui/main_window.py`
  - `AskWorker`：检索为空直接拒答，不调模型
  - 把 Skill 规则和检索结果交给 `llm_client.chat_stream()`

> 差异：ZCode 里是“模型自己调 MCP 工具”；悬浮窗里是“程序先查好，模型只组织答案”。
> 两条路的**答案规则完全一致**，因为它们读的是同一份 `SKILL.md`。

## 8. 为什么不用向量 RAG

首版知识库只有 135 条结构化数据 + 可选几百篇全文，规模不大：

- 关键词 + 中英术语桥 + 结构化字段，已经能覆盖高频问题；
- 向量检索会引入 embedding 模型、索引、切块和额外依赖，收益不明显；
- 结构化数据有明确字段（前置/步骤/注意事项/来源），比向量切片更适合“攻略问答”。

当知识库规模变大、同义表达变多时，再考虑加向量召回作为补充。

## 9. 怎么扩展到新游戏

Skill 本身是通用的，不需要为新游戏改代码：

1. 建数据目录：

```text
output/<new-game>/
  data/
    quests.json
    items.json
    bosses.json
    achievements.json
    recipes.json
    characters.json
  _index.json
  guides/            # 可选
```

2. 每条数据带 `name`、`prerequisites`、`steps`、`cautions`、`source_url`、`verified_date`。
3. 在 `games/<new-game>.json` 写游戏元信息和来源。
4. `list_games` 会自动发现 `output/*/_index.json`；Skill 的流程不用改。

如果新游戏有新的分类，需要同步改：

- `kb/query.py` 的 `CATEGORIES`
- `mcp_server/server.py` 的工具说明
- `SKILL.md` 里的分类列表

## 10. 怎么扩展 Skill 本身

### 加一条回答规则

直接改 `SKILL.md` 的「硬规则」或「输出格式」，重启宿主/悬浮窗生效。

### 加一个 MCP 工具

1. 在 `mcp_server/server.py` 用 `@mcp.tool` 定义函数；
2. 在 `SKILL.md` 的流程里写清楚“什么时候调用、参数是什么、返回什么”；
3. 在悬浮窗里如需同样能力，在 `overlay/core/kb_bridge.py` 加对应检索逻辑。

### 加全文来源

把 Markdown 放到 `output/<game>/guides/<source>/`，`search_guides` 会自动发现，无需改 Skill。

## 11. 排障

| 现象 | 检查 |
|---|---|
| Skill 不触发 | 安装路径、frontmatter、是否重启会话 |
| MCP 工具不可用 | `command` 路径、`PYTHONUTF8=1`、`GGA_OUTPUT_DIR`、MCP 客户端日志 |
| `list_games` 为空 | `output/<game>/_index.json` 是否存在；exe 是否外挂了正确目录 |
| 答案没有来源 | 检查数据条目是否带 `source_url`；全文是否注明路径 |
| 列表数量不对 | 检查 `_index.json` 的分类计数；结构化数据是否只收了一部分 |
| 公开版问全文查不到 | 公开版不含 696 篇全文；按来源 URL 自行采集到 `guides/` |

## 12. 验证 Skill 是否按预期工作

安装后问这三类问题：

1. **列表题**：「通缉犯有哪几个？」
   - 应答出知识库收录数量，并列出全部初始通缉犯
2. **流程题**：「水商怎么玩？」
   - 应给前置条件、步骤、注意事项、来源
3. **反例题**：「这个游戏支持联机吗？」
   - 应回「知识库暂未收录」，不编造

悬浮窗还可以用无界面模式验证检索层：

```bash
python overlay/main.py --ask "通缉犯有哪几个？" --dry-run
```

`--dry-run` 只检索不调用模型，能直接看到命中条数、分类统计和上下文。

## 13. 安全与隐私

- Skill 文件里没有 API Key、Cookie、账号信息。
- MCP 服务器走本地 stdio；查询只读本地 `output/`。
- 悬浮窗的模型 Key 存在本机 `%APPDATA%\GameGuideAssistant\overlay-config.json`，
  不写进仓库。
- 对话只存在内存，没有遥测或云端上传。
