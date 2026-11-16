# 知识库数据说明

本目录只包含 **结构化攻略数据**（`data/*.json`），不包含第三方攻略全文。

- 游戏：深空当铺：可能是偷的 / Probably Stolen（Steam appid 4348910）
- 结构化数据：135 条
  - 成就 21 / 危机 3 / 角色 14 / 道具 12 / 任务 11 / 配方 74
- 每条数据包含：名称、前置条件、步骤、注意事项、`source_url`、`verified_date`

## 为什么没有攻略全文

攻略全文来自 Steam 社区指南、Wikily.gg、游民星空、B站、小黑盒等公开来源，
版权归原作者/平台所有。公开仓库只保留结构化摘要与来源链接，不分发全文。

如需启用“全文检索兜底”，请按 `_index.json` 里的来源 URL 自行采集，
把 Markdown 文件放到 `guides/<source>/` 下；查询层会自动发现。

## 数据来源

- Steam 社区指南：https://steamcommunity.com/app/4348910/guides/
- Wikily.gg：https://wikily.gg/probably-stolen
- 游民星空：https://gl.ali213.net/z/157497
- B站专栏/视频字幕：https://www.bilibili.com/
- 小黑盒社区：https://www.xiaoheihe.cn/
