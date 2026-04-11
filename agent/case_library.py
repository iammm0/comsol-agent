"""Local COMSOL case library index and parsers."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlparse

from agent.utils.config import get_project_root
from agent.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_SOURCE_BASE_URL = "https://cn.comsol.com"
CASE_LIBRARY_SCHEMA_VERSION = 1

_TAG_RE = re.compile(r"<[^>]+>")
_CARD_RE = re.compile(
    r"<!--\s*Model Card\s*-->(?P<card>[\s\S]*?)<!--\s*/Model Card\s*-->",
    re.IGNORECASE,
)
_HREF_RE = re.compile(r'href="(?P<href>/model/[^"#?]+)"', re.IGNORECASE)
_MODEL_ID_RE = re.compile(r"(?:Model Id:|Application ID:)\s*(?P<id>\d+)", re.IGNORECASE)
_MODEL_ID_FROM_SLUG_RE = re.compile(r"-(?P<id>\d+)$")
_MODEL_TITLE_RE = re.compile(
    r'<a[^>]*class="[^"]*\bmodel_db__title\b[^"]*"[^>]*>(?P<title>[\s\S]*?)</a>',
    re.IGNORECASE,
)
_MODEL_DESC_RE = re.compile(
    r'<p[^>]*class="[^"]*\bmodel_db__model_desc\b[^"]*"[^>]*>(?P<desc>[\s\S]*?)</p>',
    re.IGNORECASE,
)
_IMAGE_RE = re.compile(
    r'<img[^>]+(?:data-original|src)="(?P<src>[^"]+)"',
    re.IGNORECASE,
)
_OG_RE_TEMPLATE = r'<meta\s+property="{name}"\s+content="(?P<value>[^"]*)"'


def get_default_case_library_path() -> Path:
    """Return the default local index path."""

    return get_project_root() / "data" / "case_library" / "comsol_cn_model_index.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_html_text(value: str) -> str:
    """Strip HTML tags/entities and normalize whitespace."""

    text = unescape(value or "")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub(" ", text)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url: str, base_url: str = DEFAULT_SOURCE_BASE_URL) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    return urljoin(base_url.rstrip("/") + "/", url)


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def extract_model_id(value: str) -> str:
    text = value or ""
    m = _MODEL_ID_RE.search(text)
    if m:
        return m.group("id")
    slug = slug_from_url(text) if "/" in text else text
    m = _MODEL_ID_FROM_SLUG_RE.search(slug)
    return m.group("id") if m else ""


def _first_match(pattern: str | re.Pattern[str], text: str, group: str = "value") -> str:
    regex = re.compile(pattern, re.IGNORECASE | re.DOTALL) if isinstance(pattern, str) else pattern
    m = regex.search(text or "")
    if not m:
        return ""
    try:
        return m.group(group)
    except IndexError:
        return m.group(1)


def _meta_property(html: str, name: str) -> str:
    pattern = re.compile(_OG_RE_TEMPLATE.format(name=re.escape(name)), re.IGNORECASE)
    return clean_html_text(_first_match(pattern, html, "value"))


def _strip_read_more(desc_html: str) -> str:
    return re.sub(
        r'<a[^>]*>\s*<em[^>]*class="[^"]*\bmodel_db__read_more\b[^"]*"[\s\S]*?</a>',
        " ",
        desc_html or "",
        flags=re.IGNORECASE,
    )


def parse_list_page(
    html: str,
    *,
    page: int,
    base_url: str = DEFAULT_SOURCE_BASE_URL,
    sort: str = "popularity",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Parse one COMSOL model-list page into shallow case records."""

    records: List[Dict[str, Any]] = []
    text = unescape(html or "")
    for pos, match in enumerate(_CARD_RE.finditer(text), start=1):
        card = match.group("card")
        href = _first_match(_HREF_RE, card, "href")
        if not href:
            continue
        official_url = normalize_url(href, base_url)
        slug = slug_from_url(official_url)
        model_id = extract_model_id(slug)

        title = clean_html_text(_first_match(_MODEL_TITLE_RE, card, "title"))
        if not title:
            title = clean_html_text(_first_match(r'alt="(?P<value>[^"]+)"', card))
        summary = clean_html_text(_strip_read_more(_first_match(_MODEL_DESC_RE, card, "desc")))
        image = normalize_url(_first_match(_IMAGE_RE, card, "src"), base_url)

        records.append(
            {
                "id": model_id or slug,
                "application_id": model_id,
                "slug": slug,
                "title": title or slug.replace("-", " ").title(),
                "summary": summary,
                "official_url": official_url,
                "image_url": image,
                "source_page": page,
                "source_position": pos,
                "sort": sort,
            }
        )

    last_page = 1
    m_last = re.search(
        r'<div[^>]*class="[^"]*\bpageLast\b[^"]*"[\s\S]*?/models/page/(?P<page>\d+)',
        text,
        re.IGNORECASE,
    )
    if m_last:
        last_page = int(m_last.group("page"))
    elif page > 1:
        last_page = page

    total_items = 0
    m_total = re.search(
        r'pageCount_total">\s*(?P<total>[0-9,]+)\s*<',
        text,
        re.IGNORECASE,
    )
    if m_total:
        total_items = int(m_total.group("total").replace(",", ""))

    meta = {
        "page": page,
        "last_page": last_page,
        "total_items": total_items,
        "count": len(records),
    }
    return records, meta


def parse_detail_page(
    html: str,
    *,
    base_url: str = DEFAULT_SOURCE_BASE_URL,
) -> Dict[str, Any]:
    """Parse a COMSOL model detail page."""

    text = unescape(html or "")
    title = _meta_property(text, "og:title")
    if not title:
        title = clean_html_text(
            _first_match(
                r'<h2[^>]*class="[^"]*\bmodel_db_card_heading\b[^"]*"[^>]*>(?P<value>[\s\S]*?)</h2>',
                text,
            )
        )

    summary = clean_html_text(
        _first_match(
            r'<div[^>]*class="[^"]*\babstractSingleModel\b[^"]*"[^>]*>[\s\S]*?<p>(?P<value>[\s\S]*?)</p>',
            text,
        )
    )
    if not summary:
        summary = _meta_property(text, "og:description")

    application_id = extract_model_id(text)
    image_url = normalize_url(_first_match(r'<img[^>]+src="(?P<value>/model/image/[^"]+)"', text), base_url)
    if not image_url:
        image_url = normalize_url(_meta_property(text, "og:image"), base_url)

    alternates: Dict[str, str] = {}
    for m in re.finditer(
        r'<link\s+rel="alternate"\s+href="(?P<href>[^"]+)"\s+hreflang="(?P<lang>[^"]+)"',
        text,
        re.IGNORECASE,
    ):
        alternates[m.group("lang")] = normalize_url(m.group("href"), base_url)

    products = parse_products_from_detail_html(text)
    return {
        "application_id": application_id,
        "title": title,
        "summary": summary,
        "image_url": image_url,
        "alternate_urls": alternates,
        "english_url": alternates.get("en", ""),
        "products": products,
    }


def parse_products_from_detail_html(html: str) -> List[Dict[str, str]]:
    """Extract product/module links from the detail page products tab."""

    text = unescape(html or "")
    start = text.find('id="products"')
    if start < 0:
        return []
    end = text.find("<!-- /downloads row -->", start)
    if end < 0:
        end = text.find("<script", start)
    chunk = text[start : end if end > start else len(text)]

    skipped_hrefs = {
        "/products/specifications",
        "/contact",
    }
    products: List[Dict[str, str]] = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href="(?P<href>/[^"]+)"[^>]*>(?P<label>[\s\S]*?)</a>', chunk):
        href = m.group("href").rstrip("/")
        if href in skipped_hrefs:
            continue
        name = clean_html_text(m.group("label"))
        if not name:
            continue
        key = (name, href)
        if key in seen:
            continue
        seen.add(key)
        products.append({"name": name, "url": normalize_url(href)})
    return products


def parse_downloads_html(
    html: str,
    *,
    base_url: str = DEFAULT_SOURCE_BASE_URL,
) -> List[Dict[str, str]]:
    """Parse the /models/get-the-files HTML fragment."""

    text = unescape(html or "")
    version_labels: Dict[str, str] = {}
    for m in re.finditer(
        r'<a\s+href="#(?P<key>comsol\d+)"[^>]*class="[^"]*\bswitchVersion\b[^"]*"[^>]*>(?P<label>[\s\S]*?)</a>',
        text,
        re.IGNORECASE,
    ):
        version_labels[m.group("key")] = clean_html_text(m.group("label"))

    downloads: List[Dict[str, str]] = []
    seen = set()
    li_re = re.compile(
        r'<li\s+class="(?P<class>[^"]*)"[^>]*data-cm-model-download="(?P<data_filename>[^"]*)"[^>]*>'
        r'[\s\S]*?<a\s+href="(?P<href>[^"]+)"[^>]*>[\s\S]*?'
        r'<span[^>]*>(?P<filename>[\s\S]*?)</span>\s*-\s*(?P<size>[^<]+)',
        re.IGNORECASE,
    )
    for m in li_re.finditer(text):
        class_attr = m.group("class") or ""
        version_key = next(
            (token for token in class_attr.split() if token.startswith("comsol")),
            "",
        )
        version = version_labels.get(version_key, "unversioned")
        filename = clean_html_text(m.group("filename")) or clean_html_text(m.group("data_filename"))
        href = normalize_url(m.group("href"), base_url)
        suffix = Path(filename).suffix.lower().lstrip(".")
        size = clean_html_text(m.group("size"))
        key = (version, filename, href)
        if key in seen:
            continue
        seen.add(key)
        downloads.append(
            {
                "version": version,
                "filename": filename,
                "url": href,
                "size": size,
                "file_type": suffix,
            }
        )
    return downloads


def latest_version(downloads: Sequence[Dict[str, str]]) -> str:
    def parse_version(label: str) -> Tuple[int, ...]:
        nums = re.findall(r"\d+", label or "")
        return tuple(int(n) for n in nums) if nums else (0,)

    labels = sorted({d.get("version", "") for d in downloads}, key=parse_version, reverse=True)
    return labels[0] if labels else ""


def choose_primary_download(downloads: Sequence[Dict[str, str]]) -> str:
    if not downloads:
        return ""
    version = latest_version(downloads)
    latest = [d for d in downloads if not version or d.get("version") == version]
    candidates = latest or list(downloads)
    mph = [d for d in candidates if (d.get("file_type") or "").lower() == "mph"]
    if mph:
        preferred = [
            d
            for d in mph
            if not re.search(r"(geom|geometry|sequence|demo|app)", d.get("filename", ""), re.I)
        ]
        return (preferred or mph)[0].get("url", "")
    return candidates[0].get("url", "")


def choose_reference_pdf(downloads: Sequence[Dict[str, str]]) -> str:
    version = latest_version(downloads)
    candidates = [d for d in downloads if not version or d.get("version") == version] or list(downloads)
    for item in candidates:
        if (item.get("file_type") or "").lower() == "pdf":
            return item.get("url", "")
    return ""


_CATEGORY_RULES: Sequence[Tuple[str, Sequence[str]]] = (
    ("流体与传热", ("CFD 模块", "传热模块", "流体", "传热", "换热", "对流", "散热", "冷却", "湍流")),
    ("结构与声学", ("结构力学模块", "声学模块", "疲劳模块", "应力", "应变", "振动", "声学", "固体力学")),
    ("电磁与射频", ("AC/DC 模块", "RF 模块", "射频模块", "波动光学模块", "电磁", "电场", "磁场", "天线", "波导")),
    ("化工与电化学", ("化学反应工程模块", "电化学模块", "腐蚀模块", "电池模块", "反应", "扩散", "电化学", "电池")),
    ("多孔介质与地球物理", ("地下水流模块", "多孔介质", "地质", "地下水", "渗流")),
    ("等离子体与粒子", ("等离子体模块", "粒子追踪模块", "等离子体", "粒子")),
    ("优化与通用方法", ("优化模块", "LiveLink", "网格", "导入", "导出", "参数化", "优化")),
)


def infer_category(
    *,
    title: str = "",
    summary: str = "",
    products: Optional[Sequence[Dict[str, str]]] = None,
    fallback: str = "未分类",
) -> str:
    haystack_parts = [title or "", summary or ""]
    haystack_parts.extend(p.get("name", "") for p in products or [])
    haystack = " ".join(haystack_parts)
    for category, keywords in _CATEGORY_RULES:
        if any(keyword and keyword in haystack for keyword in keywords):
            return category
    return fallback


def build_tags(
    *,
    category: str,
    products: Optional[Sequence[Dict[str, str]]] = None,
    downloads: Optional[Sequence[Dict[str, str]]] = None,
) -> List[str]:
    tags: List[str] = []
    if category and category != "未分类":
        tags.append(category)
    for product in products or []:
        name = product.get("name", "").strip()
        if name and name not in tags:
            tags.append(name)
    for item in downloads or []:
        file_type = item.get("file_type", "").strip().lower()
        if file_type and file_type not in tags:
            tags.append(file_type)
    return tags[:12]


def merge_case_record(
    list_record: Dict[str, Any],
    detail: Optional[Dict[str, Any]] = None,
    downloads: Optional[Sequence[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Merge list-card, detail-page, and download records into one normalized item."""

    detail = detail or {}
    downloads_list = list(downloads or [])
    products = list(detail.get("products") or [])
    title = str(detail.get("title") or list_record.get("title") or "").strip()
    summary = str(detail.get("summary") or list_record.get("summary") or "").strip()
    category = infer_category(title=title, summary=summary, products=products)
    application_id = str(detail.get("application_id") or list_record.get("application_id") or list_record.get("id") or "")
    official_url = str(list_record.get("official_url") or "")

    record = {
        **list_record,
        "id": application_id or str(list_record.get("id") or ""),
        "application_id": application_id,
        "title": title,
        "summary": summary,
        "category": category,
        "official_url": official_url,
        "english_url": detail.get("english_url") or "",
        "alternate_urls": detail.get("alternate_urls") or {},
        "image_url": detail.get("image_url") or list_record.get("image_url") or "",
        "products": products,
        "downloads": downloads_list,
        "latest_version": latest_version(downloads_list),
        "download_url": choose_primary_download(downloads_list) or official_url,
        "reference_pdf_url": choose_reference_pdf(downloads_list),
        "tags": build_tags(category=category, products=products, downloads=downloads_list),
    }
    return normalize_case_item(record)


def normalize_case_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a record loaded from disk or built by the crawler."""

    item = dict(raw or {})
    item["id"] = str(item.get("id") or item.get("application_id") or item.get("slug") or "").strip()
    item["application_id"] = str(item.get("application_id") or item["id"]).strip()
    item["title"] = str(item.get("title") or item.get("slug") or item["id"]).strip()
    item["summary"] = str(item.get("summary") or "").strip()
    item["category"] = str(item.get("category") or "未分类").strip()
    item["official_url"] = str(item.get("official_url") or "").strip()
    item["download_url"] = str(item.get("download_url") or item["official_url"]).strip()
    item["reference_pdf_url"] = str(item.get("reference_pdf_url") or "").strip()
    item["english_url"] = str(item.get("english_url") or "").strip()
    item["image_url"] = str(item.get("image_url") or "").strip()
    item["latest_version"] = str(item.get("latest_version") or "").strip()
    item["tags"] = [str(t).strip() for t in item.get("tags") or [] if str(t).strip()]
    item["products"] = [
        {"name": str(p.get("name") or "").strip(), "url": str(p.get("url") or "").strip()}
        for p in item.get("products") or []
        if isinstance(p, dict) and str(p.get("name") or "").strip()
    ]
    item["downloads"] = [
        {
            "version": str(d.get("version") or "").strip(),
            "filename": str(d.get("filename") or "").strip(),
            "url": str(d.get("url") or "").strip(),
            "size": str(d.get("size") or "").strip(),
            "file_type": str(d.get("file_type") or "").strip(),
        }
        for d in item.get("downloads") or []
        if isinstance(d, dict) and str(d.get("url") or "").strip()
    ]
    return item


def save_case_library(
    items: Sequence[Dict[str, Any]],
    *,
    metadata: Optional[Dict[str, Any]] = None,
    path: Optional[Path] = None,
) -> Path:
    output_path = Path(path or get_default_case_library_path())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = [normalize_case_item(item) for item in items if item]
    payload = {
        "schema_version": CASE_LIBRARY_SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "metadata": metadata or {},
        "total": len(normalized),
        "items": normalized,
    }
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(output_path)
    return output_path


def load_case_library(path: Optional[Path] = None) -> Dict[str, Any]:
    index_path = Path(path or get_default_case_library_path())
    if not index_path.exists():
        return {
            "schema_version": CASE_LIBRARY_SCHEMA_VERSION,
            "generated_at": None,
            "metadata": {},
            "total": 0,
            "items": [],
        }
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to load case library %s: %s", index_path, e)
        return {
            "schema_version": CASE_LIBRARY_SCHEMA_VERSION,
            "generated_at": None,
            "metadata": {"load_error": str(e)},
            "total": 0,
            "items": [],
        }

    if isinstance(raw, list):
        items = raw
        metadata: Dict[str, Any] = {}
        generated_at = None
    elif isinstance(raw, dict):
        items = raw.get("items") if isinstance(raw.get("items"), list) else []
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        generated_at = raw.get("generated_at")
    else:
        items = []
        metadata = {}
        generated_at = None

    normalized = [normalize_case_item(item) for item in items if isinstance(item, dict)]
    return {
        "schema_version": CASE_LIBRARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "metadata": metadata,
        "total": len(normalized),
        "items": normalized,
    }


def _case_search_text(item: Dict[str, Any]) -> str:
    parts: List[str] = [
        item.get("title", ""),
        item.get("summary", ""),
        item.get("category", ""),
        item.get("slug", ""),
        " ".join(item.get("tags") or []),
    ]
    parts.extend(p.get("name", "") for p in item.get("products") or [] if isinstance(p, dict))
    parts.extend(d.get("filename", "") for d in item.get("downloads") or [] if isinstance(d, dict))
    return clean_html_text(" ".join(parts)).lower()


def _query_terms(query: str) -> List[str]:
    q = clean_html_text(query or "").lower()
    terms = set()
    for term in re.findall(r"[a-z0-9][a-z0-9.+/_-]{1,}", q):
        if len(term) >= 2:
            terms.add(term)
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", q):
        if len(chunk) <= 8:
            terms.add(chunk)
        for n in (2, 3, 4):
            for i in range(0, max(0, len(chunk) - n + 1)):
                terms.add(chunk[i : i + n])
    return sorted(terms, key=lambda x: (-len(x), x))


def _score_case(item: Dict[str, Any], query: str) -> float:
    text = _case_search_text(item)
    q = clean_html_text(query or "").lower()
    if not q:
        return 1.0
    score = 0.0
    title = clean_html_text(item.get("title", "")).lower()
    summary = clean_html_text(item.get("summary", "")).lower()
    if q and q in text:
        score += 200.0
    for term in _query_terms(q):
        if term not in text:
            continue
        weight = 5.0 + min(len(term), 12)
        if term in title:
            weight *= 3
        elif term in summary:
            weight *= 1.5
        score += weight
    return score


def search_case_library(
    query: str,
    *,
    limit: int = 5,
    path: Optional[Path] = None,
) -> List[Dict[str, str]]:
    """Search the local case index and return planner-friendly suggestions."""

    payload = load_case_library(path)
    items = payload.get("items") or []
    scored = [
        (_score_case(item, query), item)
        for item in items
        if isinstance(item, dict) and item.get("official_url")
    ]
    scored = [(score, item) for score, item in scored if score > 0]
    scored.sort(
        key=lambda pair: (
            -pair[0],
            int(pair[1].get("source_page") or 999999),
            int(pair[1].get("source_position") or 999999),
        )
    )
    results: List[Dict[str, str]] = []
    for _score, item in scored[: max(1, limit)]:
        results.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("official_url") or ""),
                "source": "COMSOL CN 本地案例库",
                "summary": str(item.get("summary") or ""),
                "download_url": str(item.get("download_url") or ""),
                "reference_pdf_url": str(item.get("reference_pdf_url") or ""),
            }
        )
    return results


def list_case_library_items(
    *,
    limit: int = 200,
    offset: int = 0,
    query: Optional[str] = None,
    category: Optional[str] = None,
    path: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """List UI-facing case records from the local index."""

    payload = load_case_library(path)
    items = list(payload.get("items") or [])
    if category and category != "全部":
        items = [item for item in items if item.get("category") == category]
    if query and query.strip():
        scored = [(_score_case(item, query), item) for item in items]
        items = [item for score, item in sorted(scored, key=lambda p: -p[0]) if score > 0]

    total = len(items)
    safe_offset = max(0, int(offset or 0))
    safe_limit = max(1, min(int(limit or 200), 5000))
    sliced = items[safe_offset : safe_offset + safe_limit]
    return sliced, {
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "generated_at": payload.get("generated_at"),
        "metadata": payload.get("metadata") or {},
    }
