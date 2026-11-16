# -*- coding: utf-8 -*-
"""采集基座：带本地缓存、限速、UA 标识与 robots.txt 尊重的抓取器。"""
import hashlib
import sys
import time
import urllib.robotparser as robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

UA = "game-guide-assistant/0.1 (personal offline knowledge base; contact: local-user)"


def cache_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def cjk_ratio(text: str) -> float:
    """中文字符占比，用于语言判定。"""
    if not text:
        return 0.0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    cjk += sum(1 for ch in text if "\u3000" <= ch <= "\u303f")
    return cjk / max(len(text), 1)


def kana_ratio(text: str) -> float:
    """日文假名占比——日文汉字与中文同码位，用假名区分日文。"""
    if not text:
        return 0.0
    kana = sum(1 for ch in text if "\u3040" <= ch <= "\u30ff")
    return kana / max(len(text), 1)


def looks_chinese(text: str) -> bool:
    """中文文本：汉字占比足够且假名占比低（排除日文）。"""
    return cjk_ratio(text) > 0.15 and kana_ratio(text) < 0.03


class Fetcher:
    def __init__(self, cache_dir: Path, min_interval: float = 1.2, timeout: int = 25):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.timeout = timeout
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self.log: list[str] = []

    def _note(self, msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, file=sys.stderr, flush=True)  # 日志走 stderr，保持 stdout 可当 JSON 输出
        self.log.append(line)

    def _throttle(self, host: str) -> None:
        last = self._last_hit.get(host, 0.0)
        wait = self.min_interval - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_hit[host] = time.time()

    def _robots_ok(self, url: str) -> bool:
        host = urlparse(url).netloc
        if host not in self._robots:
            rp = robotparser.RobotFileParser()
            robots_url = f"https://{host}/robots.txt"
            try:
                resp = self.session.get(robots_url, timeout=self.timeout)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp.parse([])  # 无 robots 视为允许
            except requests.RequestException:
                rp.parse([])
            self._robots[host] = rp
        return self._robots[host].can_fetch(UA, url)

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{cache_key(url)}.html"

    def fetch(self, url: str, force: bool = False) -> str | None:
        """抓取页面文本；命中缓存直接返回。robots 禁止或请求失败返回 None。"""
        cp = self._cache_path(url)
        if cp.exists() and not force:
            return cp.read_text(encoding="utf-8", errors="ignore")
        if not self._robots_ok(url):
            self._note(f"robots 禁止，跳过 {url}")
            return None
        self._throttle(urlparse(url).netloc)
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                self._note(f"HTTP {resp.status_code} {url}")
                return None
            resp.encoding = resp.apparent_encoding or "utf-8"
            text = resp.text
        except requests.RequestException as exc:
            self._note(f"请求失败 {url}: {exc}")
            return None
        cp.write_text(text, encoding="utf-8")
        return text
