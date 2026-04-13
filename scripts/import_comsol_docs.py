"""Import local COMSOL documentation into the agent's searchable knowledge base."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from agent.doc_knowledge import (
    DEFAULT_COMSOL_DOC_VERSION,
    get_default_doc_kb_path,
    import_comsol_docs,
)


def _default_source_from_env() -> Optional[str]:
    load_dotenv()
    explicit = os.environ.get("COMSOL_DOC_PATH", "").strip()
    if explicit:
        return explicit

    jar_path = os.environ.get("COMSOL_JAR_PATH", "").strip()
    if jar_path:
        return jar_path
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import COMSOL HTML/TXT documentation from a local installation into the "
            "agent's local SQLite knowledge base."
        )
    )
    parser.add_argument(
        "source",
        nargs="?",
        help=(
            "COMSOL installation root, plugins directory, or doc directory. "
            "Defaults to COMSOL_DOC_PATH or COMSOL_JAR_PATH from .env/environment."
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=get_default_doc_kb_path(),
        help="Output SQLite database path.",
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_COMSOL_DOC_VERSION,
        help="COMSOL documentation version used to generate official source URLs.",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help=(
            "Optional explicit remote base URL. Defaults to "
            "https://doc.comsol.com/<version>/doc/."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit on indexed files, useful for quick dry runs.",
    )
    parser.add_argument(
        "--chunk-chars",
        type=int,
        default=2400,
        help="Maximum characters per indexed chunk.",
    )
    parser.add_argument(
        "--overlap-chars",
        type=int,
        default=240,
        help="Overlap characters between chunks.",
    )
    args = parser.parse_args()

    source = (args.source or _default_source_from_env() or "").strip()
    if not source:
        parser.error(
            "Missing source path. Pass a COMSOL installation/plugins/doc path, "
            "or set COMSOL_DOC_PATH / COMSOL_JAR_PATH."
        )

    result = import_comsol_docs(
        source,
        db_path=args.db,
        version=str(args.version or DEFAULT_COMSOL_DOC_VERSION),
        remote_doc_base_url=(args.base_url or None),
        limit=max(1, int(args.limit)) if args.limit else None,
        max_chunk_chars=max(400, int(args.chunk_chars or 2400)),
        overlap_chars=max(0, int(args.overlap_chars or 0)),
        progress=lambda payload: print(payload.get("message") or "", flush=True),
    )

    print(
        (
            "Imported COMSOL docs into {db_path}\n"
            "  source: {resolved_doc_root}\n"
            "  documents: {documents}\n"
            "  chunks: {chunks}\n"
            "  skipped_files: {skipped_files}\n"
            "  fts_enabled: {fts_enabled}\n"
            "  generated_at: {generated_at}"
        ).format(**result)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

