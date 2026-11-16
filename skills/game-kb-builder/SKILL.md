---
name: game-kb-builder
description: "给一个游戏搭建攻略知识库（源探测→分源采集→结构化→MCP 查询→装机验证）。当用户说「给XX游戏建攻略库」「把XX的攻略抓进来」「加一个新游戏到攻略助手」「攻略数据太少要扩充」时使用。只采公开页面、尊重 robots.txt 与平台条款，不绕过登录/验证码；不适用于单纯查攻略（那是 game-guide-qa）。"
---

# 游戏攻略知识库搭建器（公开版）

把任意游戏的公开攻略变成可问答的本地知识库。
命令都在仓库根目录执行，使用项目 `.venv`（Python 3.11）。

> **公开版范围**：本技能包含通用的五阶段流程、Steam / Wikily / 游民星空自动采集管线、
> 结构化规范和质量门槛。B站登录态、小黑盒签名中继等平台特定采集器**不在公开版**，
> 需要自行实现并遵守对应平台条款；详见 `scrapers/README.md`。

## 阶段 1 · 源探测（先看清哪里有货，别盲抓）

```bash
.venv\Scripts\python.exe scripts\probe_sources.py ^
  --name "游戏中文名" --name-en "Game Name" ^
  --appid <SteamAppID> --wikily-slug <wikily路径> --ali213-zone <游民专区URL>
```

输出 JSON 报告：每个源的 `status` / 数量 / 样例。**按报告决定接哪些源，不要一次全接。**

| 源 | 探测方式 | 适合做什么 | 公开版状态 |
|---|---|---|---|
| Steam 社区指南 | appid → 指南中心 | 中文叙事、成就、机制 | ✅ 自动管线 |
| Wikily.gg | slug → 顶层页 + 二级页 | 结构化数据、角色/剧情详情 | ✅ 自动管线 |
| 游民星空 | 专区 URL | 中文短攻略、NPC/结局/机制 | ✅ 自动管线 |
| B站专栏/字幕 | 浏览器渲染 | 量大质优、视频攻略 | ⚠️ 手动，公开版不含登录态采集器 |
| biligame | 搜游戏名 | 有 wiki 时可用 | 探测即可 |
| 社区自建 wiki | B站视频简介等 | 少数游戏有价值 | 视情况手动 |
| 小黑盒 | 公开分享页 | 社区攻略 | ⚠️ 手动，公开版不含签名中继采集器 |

探测结论写进 `games/<slug>.json` 的 `sources`，记录哪些源可用、哪些跳过、为什么。

## 阶段 2 · 采集

### 自动管线（HTTP，带缓存/限速/robots/UA）

1. **新增游戏配置**：在 `games/<slug>.json` 写：

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

缺哪个源的键，就自动跳过哪个源；新游戏不用一次接齐。

2. **跑建库**：

```bash
.venv\Scripts\python.exe scripts\build_kb.py --game your-game
```

3. **产物**：

```text
output/your-game/
  guides/steam/        # Steam 中文指南
  guides/wikily/       # Wikily 页面（含二级详情页）
  guides/ali213/       # 游民文章
  _index.json          # 源状态、数量、抓取时间
  README.md            # 数据说明
```

### 手动源

公开版不包含登录态/验证码/签名中继采集器。你可以：

- 用浏览器手动保存合法可访问的攻略正文；
- 转成 Markdown，放到 `output/<slug>/guides/<source>/`；
- 命名建议：`<id>-<标题>.md`，首行写标题，文末保留原始 URL。

`build_kb.py` 会把 `guides/` 下非自动管线目录当作手动源，自动统计进 `_index.json`。

**采集纪律**（所有源通用）：

- 请求间隔 ≥1s；批量时更保守；
- 明示 User-Agent，尊重 `robots.txt`；
- 只采公开页面，不碰登录态内容；
- 遇到验证码/风控立即停止，不绕过；
- 图片不下载，正文里保留图片原始 URL 即可。

## 阶段 3 · 结构化抽取

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

六类数据：

| 分类 | 文件 | 内容要求 |
|---|---|---|
| quests | `data/quests.json` | 主线目标、机制、新手开荒路线 |
| items | `data/items.json` | 道具获取；**主流玩法流派单独成条** |
| bosses | `data/bosses.json` | 强敌/危机/治安系统 |
| achievements | `data/achievements.json` | 全量成就，一条不少 |
| characters | `data/characters.json` | NPC/通缉犯**核对名单总数**；机制条目单列 |
| recipes | `data/recipes.json` | 配方；有 wiki 表格时用 `build_data.py` 生成 |

硬规则：

- 每条必须带 `source_url` + `verified_date`；
- demo/测试版数据必须标 `game_version`；
- **列表/数量类内容必须核对汇总页总数**（“9 名通缉犯”“21 个成就”），缺一条就会答错；
- 英文术语可用 `scripts/translate_terms.py` 批量翻译（免费 Index-Translate 接口），
  中文名优先查中文攻略站，不要直接机翻当官方译名；
- 不确定的内容宁可不收，不要编。

## 阶段 4 · 查询层（新游戏通常零改动）

- `kb/query.py` 自动发现 `output/*/`，新游戏不用改代码；
- 中英术语桥在 `kb/glossary.py`：新游戏出现“中文问题搜不中英文 wiki”时，往 `PAIRS` 加词对；
- 加减分类要同步改 `kb/query.py` 的 `CATEGORIES` 和 `mcp_server/server.py` 的工具描述；
- 攻略源变多后注意“同分挤压”：英文 wiki 体量大时，中文攻略可能被挤出 top-N；
  `search_guides` 已对标题行命中加权，必要时按源限流（每源 top-N）。

## 阶段 5 · 装机与验收

1. 全量重建后跑回归：

```bash
.venv\Scripts\python.exe scripts\test_mcp_smoke.py
```

2. 四问实测：成就 ×1、道具/流派 ×1、任务 ×1、**反例 ×1**（别的游戏，必须回答“未收录”）。
3. 每个新分类至少问一次，验证第一条命中符合预期。
4. 装 MCP 和 `game-guide-qa` 技能（见根目录 README），重启宿主后真机验证。
5. 自动化不能替代驾驶员验收：列表数量、来源、剧透、拒答都要人工看一遍。

## 坑表（通用版）

| # | 坑 | 正确做法 |
|---|---|---|
| 1 | Steam 指南中心默认 10 条，`?p=N` 无效 | 用 `?browsefilter=trend&numperpage=30&p=N` |
| 2 | Steam RSS 被 302 到 JS 页 | 不要用 RSS |
| 3 | Steam 旧指南没有统一正文容器 | 先试 `div.subSectionDesc`，兜底 `.guideTopContent` |
| 4 | Steam API 的 `file_description` 为空 | 正文只能抓 HTML |
| 5 | Steam 成就页 302 登录墙 | 成就数据从公开指南文章整理 |
| 6 | 中文占比被图片 URL 稀释；日文汉字与中文同码位 | 只统计可见文本；假名占比 >3% 判日文排除 |
| 7 | Wikily 大表只抓第一页 | 按服务端 `?page=N` 翻页 |
| 8 | Wikily 角色/剧情详情页漏抓 | 扫描二级路径；排除 robots 禁止的路径 |
| 9 | biligame“已收录”≠ 有 wiki | 探测有没有实际首页链接 |
| 10 | 中文关键词搜不中英文 wiki | 维护术语表桥接（通缉犯↔Wanted） |
| 11 | 游民文章尾部有站内导航 | 在“相关攻略/本周人气/分享至”等标记处截断 |
| 12 | Index-Translate 412 风控 | 浏览器 UA、批次 ≤25、间隔 ≥3s、失败退避 |
| 13 | Windows stdio 中文乱码 | `PYTHONUTF8=1` + 服务器 `reconfigure(utf-8)` |
| 14 | 结构化只有 1 条却答“只有 1 个” | 列表问题声明“知识库共收录 N 条”，并核对汇总页 |
| 15 | 采集日志混进 JSON 输出 | 日志走 stderr，stdout 只留结构化输出 |
| 16 | 热门排序列表翻页重复/漂移 | 按条目 id 全程去重，不依赖 offset 绝对位置 |
| 17 | 触发验证码/风控 | 立即停止，不绕过；只采公开页面 |

## 复用资产

| 文件 | 作用 |
|---|---|
| `scrapers/base.py` | Fetcher：缓存/限速/UA/robots |
| `scrapers/steam_guide.py` | Steam 指南发现 + 正文 + 语言判定 |
| `scrapers/wikily.py` | Wikily 顶层 + 二级页 + 分页 |
| `scrapers/ali213.py` | 游民专区 + 正文截断 |
| `scripts/probe_sources.py` | 新游戏源探测 |
| `scripts/build_kb.py` | 建库入口（读 `games/*.json`） |
| `scripts/build_data.py` | wiki 表格 → `recipes.json`（示例，按游戏适配） |
| `scripts/translate_terms.py` | 批量术语翻译 |
| `scripts/test_mcp_smoke.py` | MCP 冒烟回归 |
| `kb/query.py` / `kb/glossary.py` | 查询核心 + 术语桥 |
| `mcp_server/server.py` | MCP 工具层 |

## 新游戏端到端示例

```bash
# 1. 建 venv
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 2. 探测
.venv\Scripts\python.exe scripts\probe_sources.py --name "游戏名" --name-en "Game" --appid 123456

# 3. 写 games/your-game.json（填可用源）

# 4. 采集
.venv\Scripts\python.exe scripts\build_kb.py --game your-game

# 5. 结构化：按 data/*.json 规范补条目（每条带 source_url + verified_date）

# 6. 查询层：跑 CLI 验证
.venv\Scripts\python.exe scripts\kb_query.py --list-games
.venv\Scripts\python.exe scripts\kb_query.py --game your-game --query "新手"

# 7. 回归
.venv\Scripts\python.exe scripts\test_mcp_smoke.py
```

建好后，`game-guide-qa` 技能会自动通过 `list_games` 发现新游戏，不需要改问答代码。
