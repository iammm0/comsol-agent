import time
from pathlib import Path

from agent.run import actions


def test_do_doc_kb_import_updates_state(tmp_path, monkeypatch):
    output_path = tmp_path / "comsol_docs.db"

    with actions._DOC_KB_SYNC_LOCK:
        actions._DOC_KB_SYNC_STATE.clear()
        actions._DOC_KB_SYNC_STATE.update(
            {
                "running": False,
                "status": "idle",
                "message": "",
                "documents": 0,
                "chunks": 0,
            }
        )

    monkeypatch.setattr(actions, "get_default_doc_kb_path", lambda: output_path)

    def fake_import_comsol_docs(*, source_path, db_path, version, limit, max_chunk_chars, overlap_chars, progress):
        progress(
            {
                "event": "doc_import_progress",
                "message": "indexing intro.html",
                "documents": 1,
                "chunks": 2,
                "completed": 1,
                "total": 1,
                "source_path": "com.comsol.help.comsol/intro.html",
            }
        )
        output_path.write_text("stub", encoding="utf-8")
        return {
            "db_path": str(db_path),
            "source_path": source_path,
            "resolved_doc_root": source_path,
            "version": version,
            "documents": 1,
            "chunks": 2,
            "skipped_files": 0,
            "fts_enabled": True,
            "generated_at": "2026-04-12T00:00:00+00:00",
        }

    def fake_load_doc_kb_status(db_path=None):
        return {
            "exists": True,
            "db_path": str(output_path),
            "documents": 1,
            "chunks": 2,
            "generated_at": "2026-04-12T00:00:00+00:00",
            "metadata": {"version": "6.3"},
        }

    monkeypatch.setattr(actions, "import_comsol_docs", fake_import_comsol_docs)
    monkeypatch.setattr(actions, "load_doc_kb_status", fake_load_doc_kb_status)

    ok, message, state = actions.do_doc_kb_import(source_path=str(tmp_path), limit=1)

    assert ok is True
    assert "已启动" in message
    assert state["running"] is True

    final_state = None
    for _ in range(50):
        _, _, final_state = actions.do_doc_kb_status()
        if final_state["running"] is False:
            break
        time.sleep(0.02)

    assert final_state is not None
    assert final_state["running"] is False
    assert final_state["status"] == "completed"
    assert final_state["indexed_documents"] == 1
    assert final_state["indexed_chunks"] == 2
    assert output_path.exists()
