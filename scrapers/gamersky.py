# -*- coding: utf-8 -*-
"""游民星空攻略采集器：专区攻略 tab 页 → 文章正文。

入口是专区页攻略 tab（如 https://www.gamersky.com/z/gta6/390549_33233/），
文章 URL 模式 www.gamersky.com/handbook/YYYYMM/NNNNNN.shtml，正文容器 .Mid2L_con。
"""
import re

from bs4 import BeautifulSoup

from .base import Fetcher
from .htmlutil import clean_node

ARTICLE_RE = re.compile(r"^https?://www\.gamersky\.com/handbook/\d+/\d+\.shtml$")
# 标题预筛：KEEP 命中才收，SKIP 命中一律跳（如「预告片及官网载具图鉴汇总」两者都中→跳）
KEEP_RE = re.compile(
    r"攻略|方法|位置|流程|指南|教学|汇总|大全|说明|开启|领取|技巧|图文|图鉴|介绍|一览"
    r"|奖励|作弊码|解谜|代码|密码|隐藏|获得|获取|如何|怎么|排行榜|全收集")
SKIP_RE = re.compile(
    r"预告|解析|评测|爆料|投票|跳票|延期|截图|壁纸|销量|评分|盘点|新线索|传闻|热度|二手价格")


def is_guide_title(title: str) -> bool:
    """新闻/预告分析不放进来；宁缺毋滥，漏的后续人工复审增量补。"""
    return bool(KEEP_RE.search(title)) and not SKIP_RE.search(title)


def discover_articles(fetcher: Fetcher, tab_url: str) -> list[dict]:
    """从攻略 tab 页收集文章链接与标题（title 属性优先，兜底链接文本）。"""
    html = fetcher.fetch(tab_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, dict] = {}
    for a in soup.find_all("a", href=ARTICLE_RE):
        title = (a.get("title") or a.get_text(strip=True) or "").strip()
        if len(title) < 6 or a["href"] in seen:
            continue
        seen[a["href"]] = {"path": a["href"], "title": title}
    return list(seen.values())


def fetch_article(fetcher: Fetcher, url: str) -> dict | None:
    html = fetcher.fetch(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else url
    if h1:
        h1.decompose()
    node = soup.select_one(".Mid2L_con")
    if node is None:
        return None
    md = clean_node(soup, node)
    # 正文到站内推广/互动区为止，后面全是模板噪音（坑表 #13 的游民版）
    for marker in (
        "全收集互动地图", "更多相关内容请关注", "更多相关资讯请关注",
        "责任编辑：", "本文是否解决", "游民星空APP", "相关阅读", "相关攻略",
    ):
        pos = md.find(marker)
        if pos > 0:
            md = md[:pos]
    # JS 分页残渣：「第1页： 展开」
    md = re.sub(r"^第\d+页[：:]\s*(?:展开)?\s*", "", md.strip())
    md = re.sub(r"\s+展开\s*$", "", md)
    md = md.strip()
    if not md or len(md) < 60:
        return None
    aid = url.rsplit("/", 1)[-1].split(".")[0]
    return {"id": aid, "url": url, "title": title, "body": md}


def fetch_roadbook(fetcher: Fetcher, url: str) -> dict | None:
    """全任务流程 roadbook 页（tools/guide-map/roadbooks/N）。

    静态 HTML 只含已渲染章节的任务卡片（reader-node-card），分章靠 JS 动态
    加载——抓到的正文需标注覆盖范围，后续章节用浏览器渲染补采。
    """
    html = fetcher.fetch(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else "全任务流程图文攻略"
    cards = []
    for card in soup.select(".reader-node-card"):
        t = card.select_one(".reader-node-card__title")
        c = card.select_one(".reader-node-card__content")
        if not t or not c:
            continue
        md = clean_node(soup, c)
        if len(md) > 30:
            cards.append((t.get_text(strip=True), md))
    if not cards:
        return None
    body = "\n\n".join(f"## {t}\n\n{md}" for t, md in cards)
    return {"title": title, "url": url, "body": body, "tasks": [t for t, _ in cards]}


def article_to_markdown(article: dict) -> str:
    return (
        f"# {article['title']}\n\n"
        f"- 来源: {article['url']}\n"
        f"- 语言: 中文\n\n"
        f"{article['body']}\n"
    )
