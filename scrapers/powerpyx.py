# -*- coding: utf-8 -*-
"""PowerPyx 攻略采集器：GTA6 攻略枢纽页 → 各攻略正文。

枢纽 https://www.powerpyx.com/gta-6/ 列出全部攻略（任务通关/100%清单/全收集位置）；
文章是 WordPress，正文容器 .entry-content。robots 全站 Allow。
"""
import re

from bs4 import BeautifulSoup

from .base import Fetcher
from .htmlutil import clean_node

ARTICLE_RE = re.compile(r"^https?://www\.powerpyx\.com/gta-6-[a-z0-9-]+/?$")


def discover_articles(fetcher: Fetcher, hub_url: str) -> list[dict]:
    """从枢纽页收集攻略链接（去 #锚点、去评论跳转）。"""
    html = fetcher.fetch(hub_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, dict] = {}
    for a in soup.find_all("a", href=re.compile(r"^https?://www\.powerpyx\.com/gta-6-[a-z0-9-]+/")):
        url = a["href"].split("#")[0].rstrip("/") + "/"
        if not ARTICLE_RE.match(url):
            continue
        title = (a.get_text(strip=True) or "").strip()
        if url in seen:
            # 标题取最长的非空文本（侧栏截断文本兜底）
            if len(title) > len(seen[url]["title"]):
                seen[url]["title"] = title
            continue
        seen[url] = {"path": url, "title": title}
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
    node = soup.select_one(".entry-content")
    if node is None:
        return None
    # 去掉站内跳转/评论/打赏噪音
    for bad in node.select(".code-block-comment, .wp-block-buttons, .post-navigation, [class*=related]"):
        bad.decompose()
    md = clean_node(soup, node)
    for marker in (
        "Filed Under", "About PowerPyx", "Post navigation", "Next Guides",
        "Leave a Comment", "Show all posts", "Share this post",
    ):
        pos = md.find(marker)
        if pos > 0:
            md = md[:pos]
    md = md.strip()
    if not md or len(md) < 100:
        return None
    aid = url.rstrip("/").rsplit("/", 1)[-1]
    return {"id": aid, "url": url, "title": title, "body": md}


def article_to_markdown(article: dict) -> str:
    return (
        f"# {article['title']}\n\n"
        f"- 来源: {article['url']}\n"
        f"- 语言: 英文\n\n"
        f"{article['body']}\n"
    )
