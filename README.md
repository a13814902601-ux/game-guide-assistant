# 游戏攻略助手（Game Guide Assistant）

把单机游戏攻略变成可查询的本地知识库，并在游戏里用一个**置顶悬浮窗**直接问。
首版游戏：**《深空当铺：可能是偷的》/ Probably Stolen**（Steam appid 4348910）。

![悬浮窗截图](docs/screenshots/overlay.png)

- **悬浮窗**：置顶、半透明、可拖拽缩放，`F8` 全局显示/隐藏，不切屏问攻略
- **只依据知识库回答**：按「前置条件 / 步骤 / 注意事项 / 来源」给答案；查不到就说“知识库暂未收录”，不编造
- **来源可点击**：答案里的 http(s) 网址自动变成可点击链接
- **MCP 服务器**：5 个查询工具，ZCode / 任意 MCP 客户端可接
- **技能**：`game-guide-qa` 规定答案格式、防剧透、防编造
- **知识库外挂**：exe 不内置攻略数据，读取外部 `output/` 目录；MCP 与悬浮窗共用同一份

> **公开版说明**：本仓库包含 **135 条结构化攻略数据**、查询层、MCP 服务器、技能和悬浮窗代码；
> **不包含** 696 篇第三方攻略全文（版权原因）。因此“全文检索兜底”在公开版默认关闭，
> 需要时可按来源 URL 自行采集到 `output/<game>/guides/`。详见 [数据说明](output/deepspace-pawnshop/README.md)。

## 快速开始

### 方式 A：下载 exe（Windows）

1. 到 [Releases](../../releases) 下载：
   - `GameGuideOverlay.exe`（单文件版）
   - `game-guide-assistant-kb.zip`（公开版结构化数据，解压后得到 `output/`）
   - 如果单文件版提示 `Could not create temporary directory!`，改下 `GameGuideOverlay-onedir.zip`，
     解压后运行里面的 `GameGuideOverlay.exe`
2. 把 exe 和 `output/` 放在**同一个目录**（onedir 版把 `output/` 放在 exe 旁边）。
3. 双击 exe，点右上角 **⚙ 设置 → 模型**：
   - 填 OpenAI 兼容的 Base URL（一般以 `/v1` 结尾）和 API Key
   - 点「拉取清单」选模型，点「保存此提供商」
4. 按 **F8** 显示/隐藏；关窗口只是缩到托盘。

> exe 不含攻略库，也不含任何 API Key。知识库目录也可以在「设置 → 知识库」里手动选。
> 如果你有本地完整攻略全文，把它放进同一个 `output/<game>/guides/`，同一个 exe 会自动使用。

### 方式 B：源码运行

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-overlay.txt
.venv\Scripts\python overlay\main.py
```

默认使用项目里的 `output/`；没有配置 Key 也能启动，只是问答时会提示配置模型。

### 方式 C：在 ZCode 里用 MCP + 技能

1. 安装 MCP 依赖：

```bash
.venv\Scripts\pip install -r requirements.txt
```

2. 把 MCP 服务器注册到 ZCode（示例，路径换成你的实际路径）：

```json
{
  "mcp": {
    "servers": {
      "game-guide-kb": {
        "command": "C:\\path\\to\\python.exe",
        "args": ["C:\\path\\to\\game-guide-assistant\\mcp_server\\server.py"],
        "env": {
          "PYTHONUTF8": "1",
          "GGA_OUTPUT_DIR": "C:\\path\\to\\game-guide-assistant\\output"
        }
      }
    }
  }
}
```

3. 安装技能：把 `skills/game-guide-qa/` 复制到
   `%USERPROFILE%\.zcode\skills\game-guide-qa\`，重启 ZCode。

之后在 ZCode 里问「通缉犯有哪几个？」「水商怎么玩？」这类问题，技能会自动调用 MCP 工具。

## 架构

```
公开攻略页面 ──(本地采集器，未随仓库分发)──> output/<game>/data/*.json
                                                   │  (可选) guides/*.md
                                                   │
                                         kb/query.py  ←── 查询核心
                                          │        │
                          mcp_server/server.py   overlay/core/kb_bridge.py
                                          │        │
                                   ZCode + 技能   悬浮窗 → OpenAI 兼容 LLM
```

- 攻略库归 MCP：`output/` 是唯一数据源，MCP 和悬浮窗都读它。
- exe 只打包界面、查询客户端和技能规则，**不打包 `output/`**。
- 模型走 OpenAI 兼容接口；密钥只保存在本机 `%APPDATA%\GameGuideAssistant\overlay-config.json`。

## 已实现的功能

### 悬浮窗

- 无边框置顶窗口；拖标题栏移动，拖四边/右下角缩放
- 透明度 25%–100%、字号 11–22px、置顶开关，位置/大小/透明度持久化
- 全局快捷键可录制（默认 `F8`），注册失败会明确提示
- 系统托盘；单实例；本机健康端口 `127.0.0.1:8894/health`
- 流式回答、停止生成、连续追问、生成中清空
- 答案 Markdown 渲染；来源里的纯文本网址自动转可点击链接

### 模型配置

- 任意 OpenAI 兼容接口：`/v1/models` 拉清单、`/chat/completions` 流式对话
- 「测试连接」发一条最小请求
- 推理模型只返回 `reasoning_content` 时自动加倍 `max_tokens` 重试
- 多个提供商可保存、切换

### 问答规则

- 结构：`前置条件 / 步骤 / 注意事项 / 来源`
- 列表问题声明知识库收录数量；单条命中时提示“可能不全”
- 剧情/结局先给 `[剧透警告]`
- 数值只能来自知识库；版本和核对日期如实转述
- 没有命中：确定性回复「知识库暂未收录」，不调用模型编造

## 数据

| 分类 | 条数 |
|---|---:|
| 成就 | 21 |
| 危机/强敌 | 3 |
| 角色/通缉犯 | 14 |
| 道具 | 12 |
| 任务/事件 | 11 |
| 配方 | 74 |
| **合计** | **135** |

每条数据含 `source_url` 和 `verified_date`。来源包括 Steam 社区指南、Wikily.gg、
游民星空、B站专栏/视频字幕、小黑盒社区。

**公开版不含 696 篇攻略全文**，只保留结构化摘要与来源链接；全文采集请遵守各来源的
robots.txt / 服务条款，并只用于个人学习。

## 构建 exe

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements-overlay.txt -r requirements-build.txt
scripts\build_exe.bat
```

产物：`dist\GameGuideOverlay.exe`。

- 只打包 UI 代码、图标和 `skills/game-guide-qa` 规则，**不打包 `output/`**。
- 运行时按顺序查找知识库：`GGA_OUTPUT_DIR` → exe 同目录 `output/` → exe 上一级 `output/`
  → `%APPDATA%\GameGuideAssistant\output\` → 项目 `output/`。
- 打包成单文件 exe 会有 1–3 秒启动解压时间，属正常现象。

## 目录

```
overlay/                 PySide6 悬浮窗
  core/kb_bridge.py      问题清洗 → 检索 → 上下文（复用 kb/query.py）
  core/llm_client.py     OpenAI 兼容流式客户端
  core/prompt.py         注入 skills/game-guide-qa 规则
  core/hotkey.py         全局快捷键
  ui/                    窗口、聊天、设置
kb/                      查询核心（MCP 与悬浮窗共用）
mcp_server/server.py     fastmcp stdio 服务器（5 个工具）
skills/game-guide-qa/    问答技能规则
games/                   游戏配置
output/<game>/data/      结构化攻略数据（公开版）
output/<game>/guides/    攻略全文（公开版不含，可自行补充）
scripts/                 CLI 调试、自测、打包
docs/screenshots/        界面截图
```

## 隐私

- 仓库和 Release 里**没有** API Key、Cookie、聊天记录。
- 模型 Key 只存本机 `%APPDATA%\GameGuideAssistant\overlay-config.json`。
- 对话只保存在内存里，关程序即消失；没有遥测、没有云端上传。
- 查询时只把命中的攻略片段发给用户自己配置的 LLM。

## 已知限制

- **独占全屏**（DirectX exclusive fullscreen）游戏通常盖不住，请改成「无边框窗口 / 窗口化」。
- 只支持 OpenAI 兼容接口；Anthropic 原生格式未接。
- 公开版没有攻略全文，`search_guides`/`get_guide` 会返回空；结构化问答不受影响。
- 攻略数据有版本和时效，回答会带 `verified_date`；游戏更新后可能需要重采。
- Windows 全局快捷键注册成功不代表物理按键一定触发（受前台锁/其他软件占用影响），需要真人验证。
- 单文件 exe 在个别磁盘/杀软环境下可能报 `Could not create temporary directory!`：
  改用 onedir 版，或把 exe 移到 `C:` / `E:` 等本地固定盘再运行。

## 数据来源与版权

代码以 MIT 协议开源；`output/` 里的结构化数据由公开攻略页面整理，版权归原作者/平台。
第三方攻略全文不随仓库分发。详见 [NOTICE.md](NOTICE.md)。

## License

[MIT](LICENSE)（仅代码；第三方攻略内容见 NOTICE）
