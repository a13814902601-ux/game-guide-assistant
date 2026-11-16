# -*- coding: utf-8 -*-
"""游民星空（游侠网）攻略专区采集器：专区列表页 → 文章正文。"""
import re

from bs4 import BeautifulSoup

from .base import Fetcher
from .htmlutil import clean_node


def discover_articles(fetcher: Fetcher, zone_url: str) -> list[dict]:
    """从专区页收集文章链接与标题。"""
    html = fetcher.fetch(zone_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, dict] = {}
    for a in soup.find_all("a", href=re.compile(r"^/html/\d+")):
        title = a.get_text(strip=True)
        if len(title) < 6 or a["href"] in seen:
            continue
        seen[a["href"]] = {"path": a["href"], "title": title}
    return list(seen.values())


def fetch_article(fetcher: Fetcher, path: str) -> dict | None:
    url = f"https://gl.ali213.net{path}"
    html = fetcher.fetch(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else path
    if h1:
        h1.decompose()
    node = soup.select_one(".content") or soup.select_one(".main")
    if node is None:
        return None
    md = clean_node(soup, node)
    # 正文到「查看xx攻略大全」为止，后面全是站内导航噪音（相关攻略/本周人气/热门推荐）
    for marker in ("查看深空当铺", "分享至", "相关攻略", "本周人气攻略", "48小时热点"):
        pos = md.find(marker)
        if pos > 0:
            md = md[:pos]
    md = md.strip()
    if not md or len(md) < 60:
        return None
    return {"id": path.rsplit("/", 1)[-1].split(".")[0], "url": url, "title": title, "body": md}


def article_to_markdown(article: dict) -> str:
    return (
        f"# {article['title']}\n\n"
        f"- 来源: {article['url']}\n"
        f"- 语言: 中文\n\n"
        f"{article['body']}\n"
    )
