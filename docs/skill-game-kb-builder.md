# Skill 功能与实现详解：game-kb-builder（建库主力）

> 项目：游戏攻略助手（Game Guide Assistant）
> 技能文件：`skills/game-kb-builder/SKILL.md`
> 配套代码：`scrapers/`、`scripts/build_kb.py`、`scripts/build_data.py`、`scripts/probe_sources.py`
> 适用宿主：ZCode；也可按同样流程在其他 Agent 宿主里执行

## 一句话

**`game-kb-builder` 负责“把攻略变成可问答的数据库”**：源探测 → 采集 → 结构化 →
查询层 → 装机验证。`game-guide-qa` 负责“怎么问、怎么答”；没有建库，问答就是空转。

## 1. 两个 Skill 的分工

| Skill | 角色 | 什么时候用 |
|---|---|---|
| **game-kb-builder** | **建库主力** | 给新游戏建库、给现有库扩内容、修数据缺口 |
| game-guide-qa | 问答主力 | 玩家问“XX 怎么做”“XX 在哪拿” |

一个负责**造库**，一个负责**用库**。本项目的核心资产是前者产出的
`output/<game>/data/*.json` + `guides/*.md`。

## 2. 建库的五个阶段

```text
① 源探测  →  ② 分源采集  →  ③ 结构化抽取  →  ④ 查询层  →  ⑤ 装机验证
```

### 阶段 1：源探测

不要一上来就写爬虫。先用探测脚本看每个源有没有货：

```bash
.venv\Scripts\python.exe scripts\probe_sources.py ^
  --name "游戏中文名" --name-en "Game Name" ^
  --appid <SteamAppID> --wikily-slug <wikily路径> --ali213-zone <游民专区URL>
```

输出 JSON 报告，每个源包含：

- `status`：可用 / 未建站 / 未定位 / 仅 APP
- 数量：指南数、页面数、文章数
- 样例：标题、URL，便于判断质量

**决策原则**：按报告接源，不要一次全接。一个源质量差会拉低整个库的信噪比。

公开版支持的源：

| 源 | 适合内容 | 状态 |
|---|---|---|
| Steam 社区指南 | 中文叙事、成就、机制 | ✅ 自动管线 |
| Wikily.gg | 结构化数据、角色/剧情 | ✅ 自动管线 |
| 游民星空 | 中文短攻略、NPC/结局 | ✅ 自动管线 |
| B站 | 专栏/字幕，量大质优 | ⚠️ 手动，公开版不含登录态采集器 |
| 小黑盒 | 社区攻略 | ⚠️ 手动，公开版不含签名中继采集器 |
| biligame | 有 wiki 时 | 探测即可 |

### 阶段 2：分源采集

#### 自动管线（公开版）

在 `games/<slug>.json` 里写游戏配置：

```json
{
  "game": "your-game",
  "name_zh": "游戏中文名",
  "name_en": "Game Name",
  "steam_appid": 123456,
  "wikily_slug": "your-game",
  "ali213_zone": "https://gl.ali213.net/z/xxxxx",
  "sources": [
    {"id": "steam", "pipeline": true},
    {"id": "wikily", "pipeline": true},
    {"id": "ali213", "pipeline": true}
  ]
}
```

跑：

```bash
.venv\Scripts\python.exe scripts\build_kb.py --game your-game
```

产物：

```text
output/your-game/
  guides/steam/*.md
  guides/wikily/*.md
  guides/ali213/*.md
  _index.json        # 源状态、数量、抓取时间
  README.md
```

采集基座 `scrapers/base.py` 负责：

- 本地缓存（按 URL SHA1）
- 限速（默认 1.2s/域名）
- User-Agent 标识
- robots.txt 检查
- 日志走 stderr，stdout 保持 JSON 干净

#### 手动源

公开版不提供登录态/验证码/签名中继采集器。你可以：

- 用浏览器手动保存合法可访问的正文；
- 转成 Markdown，放到 `output/<game>/guides/<source>/`；
- 文件名建议 `<id>-<标题>.md`，文首写标题，文末保留原始 URL。

`build_kb.py` 会把非自动管线目录当手动源，自动统计进 `_index.json`。

#### 采集纪律

- 请求间隔 ≥1s；批量更保守；
- 明示 UA，尊重 robots.txt；
- 只采公开页面，不碰登录态内容；
- 遇到验证码/风控立即停止，不绕过；
- 图片不下载，保留原图 URL。

### 阶段 3：结构化抽取

统一字段：

```json
{
  "id": "unique-id",
  "name": "中文名",
  "name_en": "English Name",
  "category": "quests",
  "prerequisites": ["前置条件"],
  "steps": ["步骤 1", "步骤 2"],
  "cautions": ["注意事项"],
  "source_url": "https://...",
  "verified_date": "2026-11-16",
  "game_version": "1.0.0.13"
}
```

六类：

| 分类 | 文件 | 内容要求 |
|---|---|---|
| quests | `data/quests.json` | 主线目标、机制、新手开荒路线 |
| items | `data/items.json` | 道具获取；主流玩法流派单独成条 |
| bosses | `data/bosses.json` | 强敌/危机/治安系统 |
| achievements | `data/achievements.json` | 全量成就，一条不少 |
| characters | `data/characters.json` | NPC/通缉犯核对名单总数；机制条目单列 |
| recipes | `data/recipes.json` | 配方；有 wiki 表格时用 `build_data.py` 生成 |

**硬规则**：

- 每条必须带 `source_url` + `verified_date`；
- demo/测试版数据标 `game_version`；
- 列表/数量类内容必须核对汇总页总数（9 名通缉犯、21 个成就）；
- 英文术语可用 `scripts/translate_terms.py` 批量翻译（免费 Index-Translate 接口），
  中文名优先查中文攻略站，不要直接机翻当官方译名；
- 不确定的内容宁可不收。

#### 为什么“列表总数”是硬规则

攻略库最常见的翻车不是“没抓到”，而是“只抓到 1 条就当成全集”：

- `search_data` 只返回 top-N；
- 结构化数据可能只补了部分角色；
- 英文 wiki 的汇总页可能比结构化条目更全。

所以建库时必须回到汇总页核对数量；问答时 `game-guide-qa` 会再检查一次。

### 阶段 4：查询层

- `kb/query.py` 自动发现 `output/*/`，新游戏通常零改动；
- `kb/glossary.py` 维护中英术语桥；新游戏出现“中文问题搜不中英文 wiki”时加词对；
- 分类增减要同步改 `CATEGORIES` 和 `mcp_server/server.py` 的工具描述；
- 攻略源变多后注意“同分挤压”：英文 wiki 体量大时，中文攻略可能被挤出 top-N；
  `search_guides` 已对标题行命中加权，必要时按源限流。

### 阶段 5：装机与验收

1. 回归：

```bash
.venv\Scripts\python.exe scripts\test_mcp_smoke.py
```

2. 四问实测：成就、道具/流派、任务、**反例**（别的游戏必须“未收录”）。
3. 每个新分类至少问一次，验证第一条命中。
4. 装 MCP + `game-guide-qa` 技能，重启宿主真机验证。
5. 驾驶员人工验收：列表数量、来源、剧透、拒答。

## 3. 公开版与完整版的区别

| 内容 | 公开仓库 | 本地完整版 |
|---|---|---|
| 五阶段流程/结构化规范/通用坑表 | ✅ | ✅ |
| Steam / Wikily / 游民自动采集器 | ✅ | ✅ |
| B站登录态采集器 | ❌ | ✅（仅本地） |
| 小黑盒签名中继/风控处理 | ❌ | ✅（仅本地） |
| 696 篇第三方攻略全文 | ❌ | ✅（本地） |
| 135 条结构化数据 | ✅ | ✅ |
| MCP / 查询层 / 两个 Skill | ✅ | ✅ |

公开版只分发**公开可访问来源**的采集代码和结构化摘要；平台特定/登录态流程不公开，
避免绕过访问控制，也避免把第三方全文二次分发。

## 4. 怎么加一个新源（代码层）

1. 在 `scrapers/` 新增一个模块，复用 `Fetcher`：

```python
from scrapers.base import Fetcher

def discover(fetcher: Fetcher, entry_url: str):
    html = fetcher.get(entry_url)   # 自带缓存/限速/robots/UA
    ...
```

2. 在 `games/<slug>.json` 加对应配置键。
3. 在 `scripts/build_kb.py` 的“按配置启用各源”处加分支。
4. 产物写 `output/<game>/guides/<source>/`，每个条目带 `url/title/file`。
5. 更新 `_index.json` 的 sources 统计。

## 5. 排障

| 现象 | 检查 |
|---|---|
| 探测报告全是 skipped | 游戏名/英文名/appid 是否正确；源是否真的建站 |
| build_kb 抓不到正文 | 缓存是否过期；`--force` 重抓；页面结构是否改版 |
| 中文指南被判成日文 | 假名检测；确认是纯可见文本，不是图片 URL 稀释 |
| 新采的中文攻略搜不到 | 是否被英文 wiki“同分挤压”；检查 `search_guides` 标题加权 |
| 结构化数量对不上 | 回汇总页核对；`_index.json` 是否只统计了部分源 |
| MCP 冒烟失败 | `PYTHONUTF8=1`；`tools` 是否注册；数据目录是否正确 |
| 问答时列表少 | 数据缺口；回到阶段 3 补全并核对总数 |

## 6. 验证这套 Skill 是否生效

- 在 ZCode 里说「给某游戏建攻略库」→ 应触发 `game-kb-builder`，先跑源探测，而不是直接写爬虫；
- 说「通缉犯有哪几个」→ 应触发 `game-guide-qa`，走 MCP 查询和固定答案格式；
- 两个技能的路由描述不同：builder 面向“建库/扩库”，qa 面向“查攻略”。

## 7. 隐私与合规

- Skill 和采集器不含 API Key、Cookie、账号；
- 只读公开页面；遵守 robots.txt 和平台条款；
- 不绕过登录、验证码、付费墙；
- 第三方全文只保存在本地，公开仓库只放结构化摘要和来源链接；
- 采集日志不进入仓库。
