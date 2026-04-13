"""Local COMSOL documentation knowledge base.

The importer intentionally targets documentation already present on the user's
machine, typically under a licensed COMSOL installation. It builds a local
SQLite/FTS index used at prompt-injection time; it does not vendor COMSOL's
documentation into this repository or distribution.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import quote, urljoin

from agent.utils.config import get_project_root
from agent.utils.logger import get_logger

logger = get_logger(__name__)

DOC_KB_SCHEMA_VERSION = 1
DEFAULT_COMSOL_DOC_VERSION = "6.3"
DEFAULT_REMOTE_DOC_BASE_URL = "https://doc.comsol.com/{version}/doc/"
DOC_KB_MARKER = "=== RELEVANT COMSOL DOCS (local imported snippets) ==="

_HTML_SUFFIXES = {".html", ".htm", ".xhtml"}
_TEXT_SUFFIXES = {".txt", ".md"}
_INDEXED_SUFFIXES = _HTML_SUFFIXES | _TEXT_SUFFIXES
_SKIPPED_DIR_NAMES = {
    ".git",
    "__pycache__",
    "images",
    "image",
    "css",
    "js",
    "javascript",
    "scripts",
    "styles",
    "resources",
    "vaadin",
}
_DEFAULT_CHUNK_CHARS = 2400
_DEFAULT_CHUNK_OVERLAP = 240
_QUERY_ALIASES = {
    "边界层": ["boundary", "layer"],
    "网格": ["mesh"],
    "传热": ["heat", "transfer"],
    "热传导": ["heat", "transfer"],
    "温度": ["temperature"],
    "材料": ["material"],
    "几何": ["geometry"],
    "求解": ["solve", "solver"],
    "稳态": ["stationary", "steady"],
    "瞬态": ["transient", "time"],
    "流体": ["fluid", "flow"],
}

ProgressCallback = Callable[[Dict[str, Any]], None]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_default_doc_kb_path() -> Path:
    """Return the default local COMSOL documentation DB path."""

    return get_project_root() / "data" / "doc_knowledge" / "comsol_docs.db"


def _normalize_space(value: str) -> str:
    text = unescape(value or "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _normalize_lines(value: str) -> str:
    text = unescape(value or "").replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def clean_html_text(value: str) -> str:
    """Strip HTML tags/entities and normalize whitespace."""

    html = value or ""
    html = re.sub(r"(?is)<(script|style|svg|object|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    return _normalize_space(html)


def _extract_title_from_html(html: str, fallback: str) -> str:
    patterns = [
        r"(?is)<title[^>]*>(?P<value>.*?)</title>",
        r"(?is)<h1[^>]*>(?P<value>.*?)</h1>",
        r"(?is)<h2[^>]*>(?P<value>.*?)</h2>",
        r'(?is)<div[^>]+class="[^"]*\b(?:Head|Title)[^"]*"[^>]*>(?P<value>.*?)</div>',
    ]
    for pattern in patterns:
        match = re.search(pattern, html or "")
        if not match:
            continue
        title = clean_html_text(match.group("value"))
        if title:
            return title[:240]
    return fallback


def extract_html_document(html: str, *, fallback_title: str) -> tuple[str, str]:
    """Extract a title and text body from a COMSOL-style HTML document."""

    title = _extract_title_from_html(html, fallback_title)
    body = re.sub(r"(?is)<!--.*?-->", " ", html or "")
    body = re.sub(r"(?is)<head[^>]*>.*?</head>", " ", body)
    body = re.sub(r"(?is)<(script|style|svg|object|noscript)[^>]*>.*?</\1>", " ", body)
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)
    body = re.sub(
        r"(?i)</(p|div|h[1-6]|li|td|th|tr|table|section|article|blockquote)>",
        "\n",
        body,
    )
    body = re.sub(r"(?is)<[^>]+>", " ", body)
    text = _normalize_lines(body)
    return title, text


def _first_nonempty_line(text: str, fallback: str) -> str:
    for line in (text or "").splitlines():
        cleaned = _normalize_space(line)
        if cleaned:
            return cleaned[:240]
    return fallback


def _read_document(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    fallback_title = path.stem.replace("_", " ").replace("-", " ").strip() or path.name
    suffix = path.suffix.lower()
    if suffix in _HTML_SUFFIXES:
        return extract_html_document(raw, fallback_title=fallback_title)
    text = _normalize_lines(raw)
    return _first_nonempty_line(text, fallback_title), text


def chunk_text(
    text: str,
    *,
    max_chars: int = _DEFAULT_CHUNK_CHARS,
    overlap_chars: int = _DEFAULT_CHUNK_OVERLAP,
) -> List[str]:
    """Split text into overlapping chunks sized for prompt injection."""

    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    max_chars = max(400, int(max_chars or _DEFAULT_CHUNK_CHARS))
    overlap_chars = max(0, min(int(overlap_chars or 0), max_chars // 3))
    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks: List[str] = []
    start = 0
    min_step = max_chars - overlap_chars
    while start < len(cleaned):
        hard_end = min(start + max_chars, len(cleaned))
        end = hard_end
        if hard_end < len(cleaned):
            soft_floor = start + int(max_chars * 0.68)
            space = cleaned.rfind(" ", soft_floor, hard_end)
            if space > soft_floor:
                end = space
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(end - overlap_chars, start + min_step)
    return chunks


def _has_indexable_files(path: Path) -> bool:
    try:
        for item in path.rglob("*"):
            if item.is_file() and item.suffix.lower() in _INDEXED_SUFFIXES:
                return True
    except OSError:
        return False
    return False


def resolve_comsol_doc_root(source_path: str | Path) -> Path:
    """Resolve a COMSOL installation/plugins/doc path to the documentation root."""

    raw = Path(source_path).expanduser().resolve()
    if raw.is_file():
        return raw.parent
    if not raw.exists():
        raise FileNotFoundError(f"COMSOL documentation path does not exist: {raw}")

    candidates = [
        raw,
        raw / "doc",
        raw / "Multiphysics" / "doc",
        raw.parent / "doc",
        raw.parent.parent / "doc",
    ]
    if raw.name.lower() == "plugins":
        candidates.insert(0, raw.parent / "doc")

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists() and resolved.is_dir() and _has_indexable_files(resolved):
            return resolved

    raise FileNotFoundError(
        "No COMSOL documentation HTML/TXT files were found. "
        "Pass the COMSOL Multiphysics installation root, plugins directory, or doc directory."
    )


def _iter_doc_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _INDEXED_SUFFIXES:
            continue
        lower_parts = {part.lower() for part in path.relative_to(root).parts[:-1]}
        if lower_parts & _SKIPPED_DIR_NAMES:
            continue
        yield path


def _doc_id_for_relative_path(relative_path: Path) -> str:
    raw = relative_path.as_posix()
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", relative_path.stem).strip("-_.")
    if not slug:
        slug = "doc"
    return f"{slug}-{digest}"


def _source_url_for_relative_path(base_url: str, relative_path: Path) -> str:
    if not base_url:
        return ""
    quoted = "/".join(quote(part) for part in relative_path.parts)
    return urljoin(base_url.rstrip("/") + "/", quoted)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _create_schema(conn: sqlite3.Connection) -> bool:
    conn.execute("DROP TABLE IF EXISTS doc_chunks_fts")
    conn.execute("DROP TABLE IF EXISTS doc_chunks")
    conn.execute("DROP TABLE IF EXISTS doc_kb_meta")
    conn.execute(
        """
        CREATE TABLE doc_kb_meta(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE doc_chunks(
            id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            title TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_url TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX idx_doc_chunks_doc_id ON doc_chunks(doc_id)")
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE doc_chunks_fts USING fts5(
                id UNINDEXED,
                doc_id UNINDEXED,
                title,
                source_path UNINDEXED,
                source_url UNINDEXED,
                chunk_index UNINDEXED,
                text,
                tokenize='unicode61 remove_diacritics 2'
            )
            """
        )
        return True
    except sqlite3.OperationalError as exc:
        logger.warning("SQLite FTS5 unavailable, COMSOL doc search will use LIKE fallback: %s", exc)
        return False


def _set_meta(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO doc_kb_meta(key, value) VALUES (?, ?)",
        (key, json.dumps(value, ensure_ascii=False)),
    )


def _get_meta(conn: sqlite3.Connection) -> Dict[str, Any]:
    try:
        rows = conn.execute("SELECT key, value FROM doc_kb_meta").fetchall()
    except sqlite3.Error:
        return {}
    metadata: Dict[str, Any] = {}
    for row in rows:
        try:
            metadata[str(row["key"])] = json.loads(str(row["value"]))
        except (TypeError, json.JSONDecodeError):
            metadata[str(row["key"])] = row["value"]
    return metadata


def import_comsol_docs(
    source_path: str | Path,
    *,
    db_path: Optional[Path] = None,
    version: str = DEFAULT_COMSOL_DOC_VERSION,
    remote_doc_base_url: Optional[str] = None,
    limit: Optional[int] = None,
    max_chunk_chars: int = _DEFAULT_CHUNK_CHARS,
    overlap_chars: int = _DEFAULT_CHUNK_OVERLAP,
    progress: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """Import local COMSOL HTML/TXT documentation into the local searchable DB."""

    doc_root = resolve_comsol_doc_root(source_path)
    output = Path(db_path or get_default_doc_kb_path()).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    base_url = (
        remote_doc_base_url
        if remote_doc_base_url is not None
        else DEFAULT_REMOTE_DOC_BASE_URL.format(version=version)
    )
    files = sorted(_iter_doc_files(doc_root), key=lambda p: p.relative_to(doc_root).as_posix())
    if limit is not None:
        files = files[: max(0, int(limit))]

    conn = _connect(output)
    fts_enabled = _create_schema(conn)
    started_at = utc_now_iso()
    imported_docs = 0
    imported_chunks = 0
    skipped_files = 0

    try:
        _set_meta(conn, "schema_version", DOC_KB_SCHEMA_VERSION)
        _set_meta(conn, "source_kind", "local_comsol_docs")
        _set_meta(conn, "source_path", str(Path(source_path).expanduser().resolve()))
        _set_meta(conn, "resolved_doc_root", str(doc_root))
        _set_meta(conn, "version", version)
        _set_meta(conn, "remote_doc_base_url", base_url)
        _set_meta(conn, "started_at", started_at)
        _set_meta(conn, "generated_at", None)
        _set_meta(conn, "documents", 0)
        _set_meta(conn, "chunks", 0)
        _set_meta(conn, "skipped_files", 0)
        _set_meta(conn, "fts_enabled", fts_enabled)
        conn.commit()

        for file_index, path in enumerate(files, start=1):
            relative_path = path.relative_to(doc_root)
            try:
                title, text = _read_document(path)
            except OSError as exc:
                logger.warning("Skipping unreadable COMSOL doc file %s: %s", path, exc)
                skipped_files += 1
                continue

            chunks = chunk_text(
                text,
                max_chars=max_chunk_chars,
                overlap_chars=overlap_chars,
            )
            if not chunks:
                skipped_files += 1
                continue

            doc_id = _doc_id_for_relative_path(relative_path)
            source_path_value = relative_path.as_posix()
            source_url = _source_url_for_relative_path(base_url, relative_path)
            for chunk_index, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}-{chunk_index:04d}"
                row = (
                    chunk_id,
                    doc_id,
                    title,
                    source_path_value,
                    source_url,
                    chunk_index,
                    chunk,
                )
                conn.execute(
                    """
                    INSERT INTO doc_chunks(
                        id, doc_id, title, source_path, source_url, chunk_index, text
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
                if fts_enabled:
                    conn.execute(
                        """
                        INSERT INTO doc_chunks_fts(
                            id, doc_id, title, source_path, source_url, chunk_index, text
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        row,
                    )
                imported_chunks += 1
            imported_docs += 1

            if progress is not None:
                progress(
                    {
                        "event": "doc_import_progress",
                        "completed": file_index,
                        "total": len(files),
                        "documents": imported_docs,
                        "chunks": imported_chunks,
                        "source_path": source_path_value,
                        "message": (
                            f"[docs] {file_index}/{len(files)} {source_path_value} "
                            f"({len(chunks)} chunks)"
                        ),
                    }
                )
            if file_index % 200 == 0:
                conn.commit()

        generated_at = utc_now_iso()
        _set_meta(conn, "generated_at", generated_at)
        _set_meta(conn, "documents", imported_docs)
        _set_meta(conn, "chunks", imported_chunks)
        _set_meta(conn, "skipped_files", skipped_files)
        conn.commit()
    finally:
        conn.close()

    return {
        "db_path": str(output),
        "source_path": str(Path(source_path).expanduser().resolve()),
        "resolved_doc_root": str(doc_root),
        "version": version,
        "documents": imported_docs,
        "chunks": imported_chunks,
        "skipped_files": skipped_files,
        "fts_enabled": fts_enabled,
        "generated_at": generated_at if "generated_at" in locals() else None,
    }


def load_doc_kb_status(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load metadata and row counts for the local documentation KB."""

    path = Path(db_path or get_default_doc_kb_path()).resolve()
    if not path.exists():
        return {
            "exists": False,
            "db_path": str(path),
            "documents": 0,
            "chunks": 0,
            "metadata": {},
        }
    conn = _connect(path)
    try:
        metadata = _get_meta(conn)
        chunks = conn.execute("SELECT COUNT(*) FROM doc_chunks").fetchone()[0]
        documents = conn.execute("SELECT COUNT(DISTINCT doc_id) FROM doc_chunks").fetchone()[0]
    finally:
        conn.close()
    return {
        "exists": True,
        "db_path": str(path),
        "documents": int(documents or 0),
        "chunks": int(chunks or 0),
        "generated_at": metadata.get("generated_at"),
        "metadata": metadata,
    }


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _query_terms(query: str) -> List[str]:
    lowered = (query or "").lower()
    tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", lowered)
    for needle, aliases in _QUERY_ALIASES.items():
        if needle in lowered:
            tokens.extend(aliases)
    seen: set[str] = set()
    terms: List[str] = []
    for token in tokens:
        token = token.strip()
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def _build_fts_query(query: str) -> str:
    terms = _query_terms(query)
    if not terms:
        return ""
    quoted = [f'"{term.replace(chr(34), chr(34) + chr(34))}"' for term in terms[:12]]
    return " OR ".join(quoted)


def _row_to_hit(row: sqlite3.Row, *, score: float = 0.0) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "doc_id": row["doc_id"],
        "title": row["title"],
        "source_path": row["source_path"],
        "source_url": row["source_url"],
        "chunk_index": int(row["chunk_index"]),
        "text": row["text"],
        "score": score,
    }


def _search_like(conn: sqlite3.Connection, query: str, limit: int) -> List[Dict[str, Any]]:
    terms = _query_terms(query)[:8]
    raw_query = _normalize_space(query).lower()
    if raw_query and raw_query not in terms:
        terms.insert(0, raw_query)
    if not terms:
        return []

    conditions = []
    params: List[str] = []
    for term in terms:
        pattern = f"%{term}%"
        conditions.append("(lower(title) LIKE ? OR lower(text) LIKE ?)")
        params.extend([pattern, pattern])
    params.append(str(max(1, int(limit))))
    rows = conn.execute(
        f"""
        SELECT id, doc_id, title, source_path, source_url, chunk_index, text
        FROM doc_chunks
        WHERE {' OR '.join(conditions)}
        LIMIT ?
        """,
        params,
    ).fetchall()

    hits = []
    for row in rows:
        text = f"{row['title']}\n{row['text']}".lower()
        score = sum(text.count(term) for term in terms)
        hits.append(_row_to_hit(row, score=float(score)))
    hits.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return hits[:limit]


def search_doc_kb(
    query: str,
    *,
    limit: int = 3,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Search the local COMSOL documentation KB."""

    path = Path(db_path or get_default_doc_kb_path()).resolve()
    if not query or not path.exists():
        return []
    conn = _connect(path)
    try:
        if not _table_exists(conn, "doc_chunks"):
            return []

        hits: List[Dict[str, Any]] = []
        fts_query = _build_fts_query(query)
        if fts_query and _table_exists(conn, "doc_chunks_fts"):
            try:
                rows = conn.execute(
                    """
                    SELECT id, doc_id, title, source_path, source_url, chunk_index, text,
                           bm25(doc_chunks_fts) AS rank
                    FROM doc_chunks_fts
                    WHERE doc_chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, max(1, int(limit))),
                ).fetchall()
                hits = [_row_to_hit(row, score=float(row["rank"])) for row in rows]
            except sqlite3.OperationalError as exc:
                logger.debug("COMSOL doc FTS search failed, falling back to LIKE: %s", exc)

        if not hits:
            hits = _search_like(conn, query, max(1, int(limit)))
        return hits
    finally:
        conn.close()


def _trim_for_prompt(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def format_doc_hits_for_prompt(
    hits: List[Dict[str, Any]],
    *,
    max_chars_per_hit: int = 900,
    max_total_chars: int = 3600,
) -> str:
    """Format search hits as a compact prompt block."""

    if not hits:
        return ""
    lines = [
        DOC_KB_MARKER,
        "Use these local documentation snippets as background. Prefer the official source path/URL when citing facts.",
    ]
    total = sum(len(line) for line in lines)
    for index, hit in enumerate(hits, start=1):
        title = _normalize_space(str(hit.get("title") or "COMSOL documentation"))
        source = str(hit.get("source_url") or hit.get("source_path") or "").strip()
        excerpt = _trim_for_prompt(str(hit.get("text") or ""), max_chars_per_hit)
        block = [
            f"[{index}] {title}",
            f"Source: {source}",
            f"Excerpt: {excerpt}",
        ]
        block_size = sum(len(line) for line in block) + 8
        if total + block_size > max_total_chars and index > 1:
            break
        lines.extend(block)
        total += block_size
    return "\n".join(lines)
