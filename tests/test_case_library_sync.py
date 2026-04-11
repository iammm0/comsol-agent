import time
from pathlib import Path

from agent.case_library import save_case_library
from agent.run import actions


def test_do_case_library_sync_updates_state_and_index(tmp_path, monkeypatch):
    output_path = tmp_path / "comsol_cn_model_index.json"

    with actions._CASE_LIBRARY_SYNC_LOCK:
        actions._CASE_LIBRARY_SYNC_STATE.clear()
        actions._CASE_LIBRARY_SYNC_STATE.update(
            {
                "running": False,
                "status": "idle",
                "message": "",
                "saved_items": 0,
                "total_shallow_records": 0,
            }
        )

    monkeypatch.setattr(actions, "get_default_case_library_path", lambda: output_path)

    import scripts.sync_comsol_case_library as crawler

    def fake_sync_case_library(config):
        config.progress(
            {
                "event": "sync_progress",
                "message": "saving first item",
                "saved_items": 1,
                "total_shallow_records": 1,
                "completed": 1,
                "total": 1,
            }
        )
        save_case_library(
            [
                {
                    "id": "473",
                    "application_id": "473",
                    "title": "Heat Sink 3D",
                    "summary": "demo",
                    "category": "传热",
                    "official_url": "https://www.comsol.com/model/heat-sink-3d-473",
                    "download_url": "https://www.comsol.com/model/download/473",
                    "tags": ["传热", "3D"],
                }
            ],
            metadata={"saved_items": 1, "total_shallow_records": 1, "sync_status": "completed"},
            path=Path(config.output),
        )
        return {
            "output": str(config.output),
            "saved_items": 1,
            "total_shallow_records": 1,
            "metadata": {"sync_status": "completed"},
        }

    monkeypatch.setattr(crawler, "sync_case_library", fake_sync_case_library)

    ok, message, state = actions.do_case_library_sync(limit=1)

    assert ok is True
    assert "启动" in message
    assert state["running"] is True

    final_state = None
    for _ in range(50):
        _, _, final_state = actions.do_case_library_sync_status()
        if final_state["running"] is False:
            break
        time.sleep(0.02)

    assert final_state is not None
    assert final_state["running"] is False
    assert final_state["status"] == "completed"
    assert final_state["indexed_items"] == 1
    assert output_path.exists()
