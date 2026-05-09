"""Utilities for crawling public COMSOL website pages on demand."""

from __future__ import annotations

import re
from collections import deque
from html import unescape
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlparse

import requests

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_TAG_RE = re.compile(r"<[^>]+>")
_HREF_RE = re.compile(r'href=["\'](?P<href>[^"\']+)["\']', re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>(?P<value>[\s\S]*?)</title>", re.IGNORECASE)
_OG_TITLE_RE = re.compile(
    r'<meta\s+property=["\']og:title["\']\s+content=["\'](?P<value>[^"\']+)["\']',
    re.IGNORECASE,
)
_OG_DESC_RE = re.compile(
    r'<meta\s+property=["\']og:description["\']\s+content=["\'](?P<value>[^"\']+)["\']',
    re.IGNORECASE,
)
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>[\s\S]*?</\1>", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")

_DOWNLOAD_SUFFIXES = (".mph", ".mphbin", ".pdf", ".txt", ".zip")
_MODEL_PATH_HINTS = ("/model/", "/models", "/learning-center", "/support", "/forum")


def _clean_html_text(value: str) -> str:
    text = unescape(value or "")
    text = _SCRIPT_STYLE_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_comsol_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        value = "https://" + value.lstrip("/")
    return value


def is_allowed_comsol_url(url: str, *, allowed_hosts: Optional[Sequence[str]] = None) -> bool:
    parsed = urlparse(normalize_comsol_url(url))
    host = (parsed.netloc or "").lower()
    if not host:
        return False
    hosts = [h.lower() for h in (allowed_hosts or ("comsol.com",))]
    return any(host == allowed or host.endswith("." + allowed) for allowed in hosts)


def extract_page_links(html: str, base_url: str) -> List[str]:
    seen = set()
    output: List[str] = []
    for match in _HREF_RE.finditer(html or ""):
        href = (match.group("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        output.append(url)
    return output


def _page_title(html: str) -> str:
    og = _OG_TITLE_RE.search(html or "")
    if og:
        return _clean_html_text(og.group("value"))
    title = _TITLE_RE.search(html or "")
    if title:
        return _clean_html_text(title.group("value"))
    return ""


def _page_summary(html: str) -> str:
    meta = _OG_DESC_RE.search(html or "")
    if meta:
        return _clean_html_text(meta.group("value"))
    text = _clean_html_text(html or "")
    return text[:280].strip()


def _classify_link(url: str) -> str:
    lowered = url.lower()
    if lowered.endswith(_DOWNLOAD_SUFFIXES) or "/model/download/" in lowered:
        return "download"
    if any(hint in lowered for hint in _MODEL_PATH_HINTS):
        return "content"
    return "other"


def crawl_comsol_site(
    url: str,
    *,
    max_pages: int = 4,
    same_host: bool = True,
    timeout: float = 20.0,
    keyword: Optional[str] = None,
    allowed_hosts: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Crawl public COMSOL pages and extract text, downloads, and useful links."""

    start_url = normalize_comsol_url(url)
    if not start_url:
        return {"status": "error", "message": "missing url"}
    if not is_allowed_comsol_url(start_url, allowed_hosts=allowed_hosts):
        return {
            "status": "error",
            "message": "url is outside the allowed COMSOL domains",
        }

    parsed_start = urlparse(start_url)
    start_host = (parsed_start.netloc or "").lower()
    keyword_lower = (keyword or "").strip().lower()
    max_pages = max(1, int(max_pages or 1))

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    )

    queue: Deque[str] = deque([start_url])
    seen_urls = set()
    pages: List[Dict[str, Any]] = []
    downloads: List[Dict[str, str]] = []
    related_links: List[Dict[str, str]] = []
    seen_downloads = set()
    seen_related = set()

    while queue and len(pages) < max_pages:
        current = queue.popleft()
        if current in seen_urls:
            continue
        seen_urls.add(current)

        response = session.get(current, timeout=max(5.0, float(timeout or 20.0)))
        response.raise_for_status()
        html = response.text
        title = _page_title(html) or current
        summary = _page_summary(html)
        text = _clean_html_text(html)

        if keyword_lower:
            haystack = f"{title}\n{summary}\n{text}".lower()
            if keyword_lower not in haystack:
                pass

        page_links = extract_page_links(html, current)
        page_downloads: List[str] = []
        page_related: List[str] = []

        for link in page_links:
            if not is_allowed_comsol_url(link, allowed_hosts=allowed_hosts):
                continue
            parsed = urlparse(link)
            host = (parsed.netloc or "").lower()
            if same_host and host != start_host:
                continue

            kind = _classify_link(link)
            if kind == "download":
                page_downloads.append(link)
                if link not in seen_downloads:
                    seen_downloads.add(link)
                    downloads.append({"url": link, "source_page": current})
                continue

            if kind == "content":
                page_related.append(link)
                if link not in seen_related:
                    seen_related.add(link)
                    related_links.append({"url": link, "source_page": current})
                if link not in seen_urls and link not in queue and len(pages) + len(queue) < max_pages * 3:
                    queue.append(link)

        pages.append(
            {
                "url": current,
                "title": title,
                "summary": summary,
                "text_excerpt": text[:2000],
                "downloads": page_downloads[:20],
                "related_links": page_related[:20],
            }
        )

    matched_pages = pages
    if keyword_lower:
        matched_pages = [
            page
            for page in pages
            if keyword_lower
            in f"{page.get('title', '')}\n{page.get('summary', '')}\n{page.get('text_excerpt', '')}".lower()
        ]

    return {
        "status": "success",
        "message": f"crawled {len(pages)} page(s)",
        "query_url": start_url,
        "visited_pages": len(pages),
        "pages": matched_pages,
        "downloads": downloads[:50],
        "related_links": related_links[:50],
        "same_host": same_host,
        "keyword": keyword or "",
    }
