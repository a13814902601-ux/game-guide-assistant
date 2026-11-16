# 第三方内容与数据说明

本仓库的 **代码** 以 MIT 协议开源（见 `LICENSE`）。
`output/` 下的 **结构化攻略数据** 由公开攻略页面整理而来，版权归原作者与平台所有。

## 包含什么

- `output/<game>/data/*.json`：按「前置条件 / 步骤 / 注意事项 / 来源」整理的结构化摘要；
  每条保留原始 `source_url` 与 `verified_date`。
- `output/<game>/_index.json`：数据统计与来源清单（不含攻略全文）。
- `games/*.json`：游戏元信息与来源入口。

## 不包含什么

- **不包含** Steam 社区指南、Wikily.gg、游民星空、B站专栏/字幕、小黑盒帖子等
  第三方攻略的全文或图片。
- 公开版 `output/<game>/guides/` 为空；需要全文检索请自行采集，并遵守来源网站的
  robots.txt、服务条款和版权要求，仅用于个人学习。

## 来源

- Steam 社区指南：https://steamcommunity.com/app/4348910/guides/
- Wikily.gg：https://wikily.gg/probably-stolen
- 游民星空攻略专区：https://gl.ali213.net/z/157497
- B站：https://www.bilibili.com/
- 小黑盒：https://www.xiaoheihe.cn/

## 删除请求

如果你是权利人，认为本仓库中的结构化摘要或来源引用不当，请开 Issue 说明具体条目，
维护者会核对并删除相关内容。

## 翻译

部分英文术语的中文译名使用公开的 B 站 Index-Translate 接口辅助生成，随后人工核对。
