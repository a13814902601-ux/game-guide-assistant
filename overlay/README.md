# overlay · 游戏内悬浮窗

PySide6 桌面窗：置顶、半透明、可拖拽缩放，默认 `F8` 全局显示/隐藏。
问答复用 `kb/query.py`（与 MCP 服务器同源），只依据 `output/<game>/data` 回答；
模型走 OpenAI 兼容接口，密钥只存本机 `%APPDATA%\GameGuideAssistant\overlay-config.json`。

## 运行

```bash
python overlay/main.py
```

或双击 `启动攻略悬浮窗.vbs`（Windows，使用项目 `.venv`）。

## 测试

```bash
python scripts/test_overlay.py --skip-llm   # 本地部分
python scripts/test_overlay.py              # 含模型连通（需配置 Key）
```

无界面调试：

```bash
python overlay/main.py --ask "通缉犯有哪几个？"
python overlay/main.py --ask "通缉犯有哪几个？" --dry-run --out result.txt
python overlay/main.py --list-models
```

## 界面

- 设置 → 显示：透明度、字号、置顶、快捷键录制、重置位置大小
- 设置 → 模型：OpenAI 兼容 Base URL、API Key、模型清单、测试连接
- 设置 → 知识库：选择游戏、查看数据量、打开目录
- 关闭窗口缩到托盘；托盘右键退出
- 健康端口 `127.0.0.1:8894/health`，可给外部启动器探测

## 目录

```
overlay/
  main.py                 入口（GUI / --ask / --dry-run / --list-models）
  core/config.py          %APPDATA% 配置读写与预设
  core/kb_bridge.py       问题清洗 → 结构化 + 全文检索 → 上下文
  core/llm_client.py      OpenAI 兼容流式客户端
  core/prompt.py          注入 skills/game-guide-qa 规则
  core/hotkey.py          RegisterHotKey + WM_HOTKEY
  core/health_server.py   8894 健康端口
  ui/main_window.py       主窗口、聊天、流式、托盘配合
  ui/chat_view.py         消息气泡、Markdown、来源网址可点击
  ui/settings_dialog.py   显示 / 模型 / 知识库 / 关于
  ui/icon.py              程序图标
```

## 打包

```bat
scriptsuild_exe.bat
```

exe **不打包 `output/`**，只带界面代码和 `skills/game-guide-qa` 规则；
运行时读取 exe 旁边（或设置里指定）的 `output/` 目录。公开仓库的 `output/` 只有结构化数据；
本地补充 `guides/` 全文后，同一个 exe 会自动读到完整库。

## 已知限制

- 独占全屏（DirectX exclusive fullscreen）游戏通常盖不住，请用无边框窗口/窗口化。
- 只支持 OpenAI 兼容接口；Anthropic 原生格式未接。
- 公开仓库不含第三方攻略全文，全文兜底需要自行采集。
- 本机自动化输入可能被系统拦截；快捷键注册成功不等于物理按键一定触发，需真人验证。
