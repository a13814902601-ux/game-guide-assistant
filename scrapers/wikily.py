# -*- coding: utf-8 -*-
"""Wikily.gg 游戏攻略 wiki 采集器（英文结构化攻略，P2 再翻译关键字段）。

大表格在站内是客户端分页的，服务端用 ?page=N 翻页（HTML 内有 "Page X of Y"），
这里逐页抓取并合并为单篇 Markdown。
"""
import re

from bs4 import BeautifulSoup

from .base import Fetcher
from .htmlutil import clean_node

BASE = "https://wikily.gg"
PAGE_MARK = re.compile(r"Page\s+(\d+)\s+of\s+(\d+)")
MAX_PAGES = 10


def discover_pages(fetcher: Fetcher, game_slug: str) -> list[str]:
    """收集攻略页路径：主页顶层 slug + 各顶层页里链接的二级子页。

    返回形如 "characters/james-bailey" 的相对路径（顶层页则只有一段）。
    robots 禁止的 /*/moderation/ 不采。
    """
    top_html = fetcher.fetch(f"{BASE}/{game_slug}")
    if not top_html:
        return []
    soup = BeautifulSoup(top_html, "html.parser")
    tops: set[str] = set()
    sub_paths: set[str] = set()
    top_pat = re.compile(rf"^/{re.escape(game_slug)}/([a-z0-9-]+)$")
    sub_pat = re.compile(rf"^/{re.escape(game_slug)}/([a-z0-9-]+)/([a-z0-9-]+)$")
    for a in soup.find_all("a", href=True):
        m = top_pat.match(a["href"])
        if m:
            tops.add(m.group(1))
            continue
        m = sub_pat.match(a["href"])
        if m and m.group(2) != "moderation":
            sub_paths.add(f"{m.group(1)}/{m.group(2)}")
    # 从已抓取的顶层页缓存里再收集二级链接（characters/storylines 详情页藏在里层）
    for slug in sorted(tops):
        html = fetcher.fetch(f"{BASE}/{game_slug}/{slug}")
        if not html:
            continue
        s2 = BeautifulSoup(html, "html.parser")
        for a in s2.find_all("a", href=True):
            m = sub_pat.match(a["href"])
            if m and m.group(2) != "moderation":
                sub_paths.add(f"{m.group(1)}/{m.group(2)}")
    return sorted(tops) + sorted(sub_paths)


def _parse_page(html: str) -> tuple[str, str, int]:
    """解析单页：返回 (标题, 正文 Markdown, 总页数)。"""
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one("div.wiki-content") or soup.find("main") or soup.body
    if node is None:
        return "", "", 1
    h1 = node.find("h1") or soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if h1:
        h1.decompose()
    md = clean_node(soup, node)
    m = PAGE_MARK.search(node.get_text(" ", strip=True))
    total = int(m.group(2)) if m else 1
    return title, md, min(total, MAX_PAGES)


def fetch_page(fetcher: Fetcher, game_slug: str, slug: str) -> dict | None:
    url = f"{BASE}/{game_slug}/{slug}"
    html = fetcher.fetch(url)
    if not html:
        return None
    title, md, total = _parse_page(html)
    if not md or len(md) < 40:
        return None
    parts = [md]
    for pageno in range(2, total + 1):
        page_url = f"{url}?page={pageno}"
        page_html = fetcher.fetch(page_url)
        if not page_html:
            fetcher._note(f"{slug} 第 {pageno}/{total} 页抓取失败，跳过")
            continue
        _, page_md, _ = _parse_page(page_html)
        if page_md:
            parts.append(page_md)
    body = "\n\n".join(parts)
    return {"id": slug, "url": url, "title": title or slug, "body": body, "pages": total}


def page_to_markdown(page: dict) -> str:
    return (
        f"# {page['title']}\n\n"
        f"- 来源: {page['url']}\n"
        f"- 语言: 英文（关键内容 P2 翻译为中文）\n\n"
        f"{page['body']}\n"
    )
