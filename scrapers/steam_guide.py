# -*- coding: utf-8 -*-
"""Steam 社区指南采集器：发现（指南中心翻页）→ 详情页正文 → Markdown。"""
import re

from bs4 import BeautifulSoup

from .base import Fetcher, cjk_ratio, kana_ratio, looks_chinese
from .htmlutil import clean_node

HUB_URL = "https://steamcommunity.com/app/{appid}/guides/"
DETAIL_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id={gid}"
MAX_PAGES = 15


def discover_guides(fetcher: Fetcher, appid: int) -> list[dict]:
    """翻页枚举指南中心全部条目，返回去重后的 {id, title, zh} 列表。"""
    seen: dict[str, dict] = {}
    for page in range(1, MAX_PAGES + 1):
        url = HUB_URL.format(appid=appid) + f"?browsefilter=trend&numperpage=30&p={page}"
        html = fetcher.fetch(url)
        if not html:
            break
        soup = BeautifulSoup(html, "html.parser")
        new_on_page = 0
        for a in soup.find_all("a", href=re.compile(r"filedetails/\?id=\d+")):
            m = re.search(r"id=(\d+)", a["href"])
            if not m:
                continue
            gid = m.group(1)
            if gid in seen:
                continue
            text = a.get_text(" ", strip=True)
            if len(text) < 3:  # 缩略图链接等无文字锚点
                continue
            # 预筛：标题含汉字且假名占比低（排除日文）；正文语言在 fetch_guide 里复核
            seen[gid] = {
                "id": gid,
                "title": text[:120],
                "zh": cjk_ratio(text) > 0.05 and kana_ratio(text) < 0.03,
            }
            new_on_page += 1
        fetcher._note(f"guides hub 第 {page} 页：新增 {new_on_page}，累计 {len(seen)}")
        if new_on_page == 0:
            break
    return list(seen.values())


def fetch_guide(fetcher: Fetcher, gid: str) -> dict | None:
    """抓取单篇指南详情，解析标题/作者/分节正文。"""
    url = DETAIL_URL.format(gid=gid)
    html = fetcher.fetch(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one(".workshopItemTitle")
    title = title_el.get_text(strip=True) if title_el else f"guide-{gid}"

    author_el = soup.select_one(".creatorsBlock .friendBlockContent")
    author = author_el.get_text(strip=True) if author_el else ""

    # 新版指南：div.guide_subSection 包裹；旧版单页：subSectionDesc 直接散布。
    # 统一按 div.subSectionDesc 逐节取，标题取同级/最近的 subSectionTitle。
    sections = []
    lang_text_parts: list[str] = []
    for body in soup.select("div.subSectionDesc"):
        head = None
        if body.parent:
            head = body.parent.select_one(".subSectionTitle")
        if head is None:
            head = body.find_previous(class_="subSectionTitle")
        head_text = head.get_text(" ", strip=True) if head else ""
        lang_text_parts.append(body.get_text(" ", strip=True))
        md = clean_node(soup, body)
        if md:
            sections.append((head_text, md))

    # 兜底：以上结构都没有时取指南正文区
    if not sections:
        area = soup.select_one("div.guideTopContent") or soup.select_one(".guideTopDescription")
        if area:
            lang_text_parts.append(area.get_text(" ", strip=True))
            md = clean_node(soup, area)
            if md:
                sections.append(("", md))

    # 语言判定用纯可见文本（Markdown 里的图片 URL 会稀释中文占比）
    full_text = title + "\n" + "\n".join(lang_text_parts)
    return {
        "id": gid,
        "url": url,
        "title": title,
        "author": author,
        "sections": sections,
        "zh": looks_chinese(full_text),
    }


def guide_to_markdown(guide: dict) -> str:
    lines = [
        f"# {guide['title']}",
        "",
        f"- 来源: {guide['url']}",
        f"- 作者: {guide['author'] or '未知'}",
        f"- 语言: {'中文' if guide['zh'] else '非中文'}",
        "",
    ]
    for head, body in guide["sections"]:
        if head:
            lines += [f"## {head}", ""]
        lines += [body, ""]
    return "\n".join(lines).rstrip() + "\n"
