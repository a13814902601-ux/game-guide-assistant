# -*- coding: utf-8 -*-
"""HTML → Markdown 公用工具。"""
import re

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter


def table_to_md(table) -> str:
    """表格转 Markdown 管道表（markdownify 不产标准表格）。"""
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True).replace("|", "\\|") for c in tr.find_all(["th", "td"])]
        if cells:
            rows.append("| " + " | ".join(cells) + " |")
    if not rows:
        return ""
    sep = "| " + " | ".join(["---"] * rows[0].count("|")) + " |"
    return "\n".join([rows[0], sep, *rows[1:]])


def _convert(el) -> str:
    md = MarkdownConverter(heading_style="ATX", bullets="-").convert_soup(el)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def clean_node(soup: BeautifulSoup, node) -> str:
    """移除节点内的脚本/样式/导航噪音后返回其 Markdown。"""
    for bad in node.find_all(["script", "style", "nav", "aside", "button", "iframe"]):
        bad.decompose()
    # 表格单独转换，避免 markdownify 乱输出
    tables_out = []
    for t in node.find_all("table"):
        md_tbl = table_to_md(t)
        placeholder = soup.new_tag("p")
        placeholder.string = f"@@TABLE{len(tables_out)}@@"
        tables_out.append(md_tbl)
        t.replace_with(placeholder)
    md = _convert(node)
    for i, tbl in enumerate(tables_out):
        md = md.replace(f"@@TABLE{i}@@", tbl)
    return md
