"""Fetch the COMSOL CN model library into the local case-library index."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from threading import local
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import requests

from agent.case_library import (
    CASE_LIBRARY_TARGET_VERSION,
    DEFAULT_SOURCE_BASE_URL,
    get_default_case_library_path,
    merge_case_record,
    parse_detail_page,
    parse_downloads_html,
    parse_list_page,
    save_case_library,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
LIST_SORT = "popularity"

_thread_local = local()
ProgressCallback = Callable[[Dict[str, Any]], None]


@dataclass
class CrawlConfig:
    start_page: int
    end_page: Optional[int]
    limit: Optional[int]
    workers: int
    timeout: float
    delay_ms: int
    output: Path
    refresh: bool
    sort: str = LIST_SORT
    progress: Optional[ProgressCallback] = field(default=None, repr=False, compare=False)


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    )
    return session


def get_session() -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = _make_session()
        _thread_local.session = session
    return session


def fetch_text(url: str, *, timeout: float, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> str:
    session = get_session()
    if method.upper() == "POST":
        response = session.post(
            url,
            data=data or {},
            timeout=timeout,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": url,
            },
        )
    else:
        response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def list_page_url(page: int, *, sort: str) -> str:
    if page <= 1:
        return f"{DEFAULT_SOURCE_BASE_URL}/models?sort={sort}"
    return f"{DEFAULT_SOURCE_BASE_URL}/models/page/{page}?sort={sort}"


def _notify(config: CrawlConfig, **payload: Any) -> None:
    if config.progress is not None:
        config.progress(payload)
        return
    message = str(payload.get("message") or "").strip()
    if message:
        print(message)


def crawl_list_pages(config: CrawlConfig) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    first_html = fetch_text(list_page_url(config.start_page, sort=config.sort), timeout=config.timeout)
    first_items, first_meta = parse_list_page(
        first_html,
        page=config.start_page,
        base_url=DEFAULT_SOURCE_BASE_URL,
        sort=config.sort,
    )

    end_page = config.end_page or first_meta.get("last_page") or config.start_page
    seen = {item["official_url"] for item in first_items}
    items = list(first_items)
    _notify(
        config,
        event="list_page",
        page=config.start_page,
        added=len(first_items),
        total_items=len(items),
        site_last_page=first_meta.get("last_page"),
        site_total_items=first_meta.get("total_items"),
        message=(
            f"[list] page {config.start_page}: {len(first_items)} items "
            f"(site last_page={first_meta.get('last_page')}, total={first_meta.get('total_items')})"
        ),
    )

    for page in range(config.start_page + 1, end_page + 1):
        html = fetch_text(list_page_url(page, sort=config.sort), timeout=config.timeout)
        page_items, _page_meta = parse_list_page(
            html,
            page=page,
            base_url=DEFAULT_SOURCE_BASE_URL,
            sort=config.sort,
        )
        added = 0
        for item in page_items:
            if item["official_url"] in seen:
                continue
            seen.add(item["official_url"])
            items.append(item)
            added += 1
        _notify(
            config,
            event="list_page",
            page=page,
            added=added,
            total_items=len(items),
            site_last_page=first_meta.get("last_page"),
            site_total_items=first_meta.get("total_items"),
            message=f"[list] page {page}: +{added} items",
        )
        if config.limit and len(items) >= config.limit:
            items = items[: config.limit]
            break
        if config.delay_ms > 0:
            time.sleep(config.delay_ms / 1000.0)

    metadata = {
        "source": "COMSOL CN Model Library",
        "base_url": DEFAULT_SOURCE_BASE_URL,
        "sort": config.sort,
        "start_page": config.start_page,
        "end_page": min(end_page, config.end_page or end_page),
        "last_page": first_meta.get("last_page"),
        "site_total_items": first_meta.get("total_items"),
    }
    return items, metadata


def fetch_downloads(application_id: str, *, timeout: float, official_url: str) -> List[Dict[str, str]]:
    session = get_session()
    response = session.post(
        f"{DEFAULT_SOURCE_BASE_URL}/models/get-the-files",
        data={"id": application_id},
        timeout=timeout,
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": official_url,
            "User-Agent": USER_AGENT,
        },
    )
    response.raise_for_status()
    payload = response.json()
    html = ""
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            html = str(data.get("html") or "")
    return parse_downloads_html(html, base_url=DEFAULT_SOURCE_BASE_URL)


def crawl_detail(record: Dict[str, Any], *, timeout: float) -> Dict[str, Any]:
    application_id = str(record.get("application_id") or record.get("id") or "").strip()
    detail_html = fetch_text(str(record["official_url"]), timeout=timeout)
    detail = parse_detail_page(detail_html, base_url=DEFAULT_SOURCE_BASE_URL)
    if not application_id:
        application_id = str(detail.get("application_id") or "")
        record = {**record, "application_id": application_id, "id": application_id or record.get("id")}
    downloads = fetch_downloads(application_id, timeout=timeout, official_url=str(record["official_url"]))
    return merge_case_record(record, detail=detail, downloads=downloads)


def crawl_details(
    shallow_records: Iterable[Dict[str, Any]],
    *,
    timeout: float,
    workers: int,
    delay_ms: int,
    progress: Optional[ProgressCallback] = None,
    on_item: Optional[Callable[[Dict[str, Any], int, int], None]] = None,
) -> List[Dict[str, Any]]:
    records = list(shallow_records)
    total = len(records)
    if total == 0:
        return []

    output: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        future_map = {
            pool.submit(crawl_detail, record, timeout=timeout): record
            for record in records
        }
        for idx, future in enumerate(as_completed(future_map), start=1):
            record = future_map[future]
            label = str(record.get("official_url") or record.get("id") or "")
            try:
                merged = future.result()
                if on_item is not None:
                    on_item(merged, idx, total)
                if merged.get("target_version_available") is False:
                    if progress is not None:
                        progress(
                            {
                                "event": "detail_filtered",
                                "completed": idx,
                                "total": total,
                                "title": merged.get("title"),
                                "official_url": merged.get("official_url"),
                                "target_version": CASE_LIBRARY_TARGET_VERSION,
                                "message": (
                                    f"[detail] {idx}/{total} skipped {merged.get('title')} "
                                    f"(missing {CASE_LIBRARY_TARGET_VERSION} downloads)"
                                ),
                            }
                        )
                    else:
                        print(
                            f"[detail] {idx}/{total} skipped {merged.get('title')} "
                            f"(missing {CASE_LIBRARY_TARGET_VERSION} downloads)"
                        )
                    continue
                key = str(merged.get("official_url") or merged.get("id") or label)
                output[key] = merged
                if progress is not None:
                    progress(
                        {
                            "event": "detail_success",
                            "completed": idx,
                            "total": total,
                            "title": merged.get("title"),
                            "official_url": merged.get("official_url"),
                            "target_version": CASE_LIBRARY_TARGET_VERSION,
                            "message": f"[detail] {idx}/{total} ok {merged.get('title')}",
                        }
                    )
                else:
                    print(f"[detail] {idx}/{total} ok {merged.get('title')}")
            except Exception as exc:
                if progress is not None:
                    progress(
                        {
                            "event": "detail_failed",
                            "completed": idx,
                            "total": total,
                            "official_url": label,
                            "message": f"[detail] {idx}/{total} failed {label}: {exc}",
                        }
                    )
                else:
                    print(f"[detail] {idx}/{total} failed {label}: {exc}")
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

    ordered: List[Dict[str, Any]] = []
    for record in records:
        key = str(record.get("official_url") or record.get("id") or "")
        if key in output:
            ordered.append(output[key])
    return ordered


def parse_args() -> CrawlConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch the COMSOL CN model library into a local JSON index filtered to "
            f"{CASE_LIBRARY_TARGET_VERSION} downloads."
        )
    )
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int, default=0, help="0 means auto-detect from the site")
    parser.add_argument("--limit", type=int, default=0, help="0 means no explicit cap")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--delay-ms", type=int, default=100)
    parser.add_argument("--output", type=Path, default=get_default_case_library_path())
    parser.add_argument("--refresh", action="store_true")
    ns = parser.parse_args()
    return CrawlConfig(
        start_page=max(1, ns.start_page),
        end_page=max(1, ns.end_page) if ns.end_page else None,
        limit=max(1, ns.limit) if ns.limit else None,
        workers=max(1, ns.workers),
        timeout=max(5.0, ns.timeout),
        delay_ms=max(0, ns.delay_ms),
        output=ns.output,
        refresh=bool(ns.refresh),
    )


def sync_case_library(config: CrawlConfig) -> Dict[str, Any]:
    sync_started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    config.output.parent.mkdir(parents=True, exist_ok=True)

    save_case_library(
        [],
        metadata={
            "source": "COMSOL CN Model Library",
            "base_url": DEFAULT_SOURCE_BASE_URL,
            "sort": config.sort,
            "target_version": CASE_LIBRARY_TARGET_VERSION,
            "sync_started_at": sync_started_at,
            "sync_status": "starting",
            "saved_items": 0,
            "total_shallow_records": 0,
        },
        path=config.output,
    )

    shallow_records, metadata = crawl_list_pages(config)
    if config.limit:
        shallow_records = shallow_records[: config.limit]

    total_shallow_records = len(shallow_records)
    record_order = {
        str(record.get("official_url") or record.get("id") or ""): idx
        for idx, record in enumerate(shallow_records)
    }
    partial_records: Dict[str, Dict[str, Any]] = {
        str(record.get("official_url") or record.get("id") or ""): record
        for record in shallow_records
    }
    filtered_out_keys: set[str] = set()
    save_case_library(
        list(partial_records.values()),
        metadata={
            **metadata,
            "target_version": CASE_LIBRARY_TARGET_VERSION,
            "sync_started_at": sync_started_at,
            "sync_status": "running",
            "saved_items": len(partial_records),
            "total_shallow_records": total_shallow_records,
            "filtered_out_items": 0,
        },
        path=config.output,
    )
    _notify(
        config,
        event="sync_stage",
        stage="list_complete",
        total_shallow_records=total_shallow_records,
        saved_items=len(partial_records),
        target_version=CASE_LIBRARY_TARGET_VERSION,
        message=(
            f"[list] total shallow records: {total_shallow_records} "
            f"(target {CASE_LIBRARY_TARGET_VERSION})"
        ),
    )

    def save_partial(item: Dict[str, Any], completed: int, total: int) -> None:
        key = str(item.get("official_url") or item.get("id") or "")
        partial_records[key] = item
        if item.get("target_version_available") is False:
            filtered_out_keys.add(key)
        else:
            filtered_out_keys.discard(key)
        ordered = sorted(
            partial_records.values(),
            key=lambda record: record_order.get(
                str(record.get("official_url") or record.get("id") or ""),
                len(record_order) + 1,
            ),
        )
        saved_count = sum(1 for record in ordered if record.get("target_version_available", True))
        save_case_library(
            ordered,
            metadata={
                **metadata,
                "target_version": CASE_LIBRARY_TARGET_VERSION,
                "sync_started_at": sync_started_at,
                "sync_status": "running",
                "saved_items": saved_count,
                "total_shallow_records": total_shallow_records,
                "detail_completed": completed,
                "detail_total": total,
                "last_item_title": str(item.get("title") or ""),
                "filtered_out_items": len(filtered_out_keys),
            },
            path=config.output,
        )
        _notify(
            config,
            event="sync_progress",
            completed=completed,
            total=total,
            total_shallow_records=total_shallow_records,
            saved_items=saved_count,
            title=item.get("title"),
            official_url=item.get("official_url"),
            target_version=CASE_LIBRARY_TARGET_VERSION,
            message=(
                f"[sync] saved {saved_count} {CASE_LIBRARY_TARGET_VERSION} items "
                f"({completed}/{total} details, filtered={len(filtered_out_keys)})"
            ),
        )

    detailed_records = crawl_details(
        shallow_records,
        timeout=config.timeout,
        workers=config.workers,
        delay_ms=config.delay_ms,
        progress=config.progress,
        on_item=save_partial,
    )
    final_records = sorted(
        detailed_records,
        key=lambda record: record_order.get(
            str(record.get("official_url") or record.get("id") or ""),
            len(record_order) + 1,
        ),
    )
    payload_meta = {
        **metadata,
        "target_version": CASE_LIBRARY_TARGET_VERSION,
        "sync_started_at": sync_started_at,
        "crawled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "saved_items": len(final_records),
        "total_shallow_records": total_shallow_records,
        "sync_status": "completed",
        "detail_success_count": len(detailed_records),
        "filtered_out_items": len(filtered_out_keys),
    }
    save_case_library(final_records, metadata=payload_meta, path=config.output)
    return {
        "output": str(config.output),
        "saved_items": int(payload_meta["saved_items"]),
        "total_shallow_records": total_shallow_records,
        "metadata": payload_meta,
    }


def main() -> int:
    config = parse_args()
    _notify(
        config,
        event="sync_stage",
        stage="start",
        message=(
            f"[start] start_page={config.start_page} end_page={config.end_page or 'auto'} "
            f"workers={config.workers} output={config.output} "
            f"target_version={CASE_LIBRARY_TARGET_VERSION}"
        ),
    )
    result = sync_case_library(config)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
