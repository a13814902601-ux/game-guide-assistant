# 采集器（公开版）

公开版包含三个公开源：

- `steam_guide.py`：Steam 社区指南（中文为主）
- `wikily.py`：Wikily.gg 页面
- `ali213.py`：游民星空攻略专区
- `base.py` / `htmlutil.py`：限速、缓存、robots、HTML→Markdown 基座

**不包含** B站登录态采集器、小黑盒签名中继采集器。请只采集公开可访问的页面，
遵守 robots.txt 与平台服务条款，不绕过登录、验证码或访问控制。

手动采集的合法正文可放到 `output/<game>/guides/<source>/`，`build_kb.py` 会统计。
