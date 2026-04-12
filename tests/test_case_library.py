from agent.case_library import (
    CASE_LIBRARY_TARGET_VERSION,
    load_case_library,
    merge_case_record,
    save_case_library,
    search_case_library,
)


def test_merge_case_record_keeps_only_comsol_63_downloads():
    record = merge_case_record(
        {
            "id": "473",
            "application_id": "473",
            "slug": "heat-sink-3d-473",
            "title": "Heat Sink 3D",
            "summary": "legacy summary",
            "official_url": "https://cn.comsol.com/model/heat-sink-3d-473",
        },
        detail={
            "application_id": "473",
            "title": "Heat Sink 3D",
            "summary": "Steady heat transfer model.",
            "products": [{"name": "传热模块", "url": "https://cn.comsol.com/heat-transfer-module"}],
        },
        downloads=[
            {
                "version": "COMSOL 6.2",
                "filename": "heat_sink_legacy.mph",
                "url": "https://cn.comsol.com/model/download/legacy/heat_sink_legacy.mph",
                "size": "10MB",
                "file_type": "mph",
            },
            {
                "version": "COMSOL 6.3",
                "filename": "heat_sink_geometry_sequence.mph",
                "url": "https://cn.comsol.com/model/download/63/heat_sink_geometry_sequence.mph",
                "size": "3MB",
                "file_type": "mph",
            },
            {
                "version": "COMSOL 6.3",
                "filename": "heat_sink_3d.mph",
                "url": "https://cn.comsol.com/model/download/63/heat_sink_3d.mph",
                "size": "12MB",
                "file_type": "mph",
            },
            {
                "version": "COMSOL 6.3",
                "filename": "heat_sink_3d.pdf",
                "url": "https://cn.comsol.com/model/download/63/heat_sink_3d.pdf",
                "size": "1MB",
                "file_type": "pdf",
            },
            {
                "version": "COMSOL 6.4",
                "filename": "heat_sink_future.mph",
                "url": "https://cn.comsol.com/model/download/64/heat_sink_future.mph",
                "size": "13MB",
                "file_type": "mph",
            },
        ],
    )

    assert record["target_version"] == CASE_LIBRARY_TARGET_VERSION
    assert record["target_version_available"] is True
    assert record["latest_version"] == CASE_LIBRARY_TARGET_VERSION
    assert all(item["version"] == CASE_LIBRARY_TARGET_VERSION for item in record["downloads"])
    assert record["download_url"].endswith("/heat_sink_3d.mph")
    assert record["reference_pdf_url"].endswith("/heat_sink_3d.pdf")


def test_save_and_load_case_library_drop_non_target_version_items(tmp_path):
    output_path = tmp_path / "case_library.json"

    save_case_library(
        [
            {
                "id": "legacy",
                "application_id": "legacy",
                "title": "Legacy Only",
                "summary": "Only 6.4 download is available.",
                "category": "传热",
                "official_url": "https://cn.comsol.com/model/legacy-only",
                "downloads": [
                    {
                        "version": "COMSOL 6.4",
                        "filename": "legacy_only.mph",
                        "url": "https://cn.comsol.com/model/download/64/legacy_only.mph",
                        "size": "11MB",
                        "file_type": "mph",
                    }
                ],
            },
            {
                "id": "supported",
                "application_id": "supported",
                "title": "Supported 6.3",
                "summary": "Has a COMSOL 6.3 download.",
                "category": "传热",
                "official_url": "https://cn.comsol.com/model/supported-63",
                "downloads": [
                    {
                        "version": "COMSOL 6.3",
                        "filename": "supported_63.mph",
                        "url": "https://cn.comsol.com/model/download/63/supported_63.mph",
                        "size": "9MB",
                        "file_type": "mph",
                    }
                ],
            },
        ],
        metadata={"target_version": CASE_LIBRARY_TARGET_VERSION},
        path=output_path,
    )

    payload = load_case_library(output_path)

    assert payload["metadata"]["target_version"] == CASE_LIBRARY_TARGET_VERSION
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == "supported"
    assert payload["items"][0]["latest_version"] == CASE_LIBRARY_TARGET_VERSION


def test_search_case_library_reports_comsol_63_source(tmp_path):
    output_path = tmp_path / "case_library.json"
    save_case_library(
        [
            {
                "id": "473",
                "application_id": "473",
                "title": "Heat Sink 3D",
                "summary": "Steady heat transfer model.",
                "category": "传热",
                "official_url": "https://cn.comsol.com/model/heat-sink-3d-473",
                "downloads": [
                    {
                        "version": "COMSOL 6.3",
                        "filename": "heat_sink_3d.mph",
                        "url": "https://cn.comsol.com/model/download/63/heat_sink_3d.mph",
                        "size": "9MB",
                        "file_type": "mph",
                    }
                ],
            }
        ],
        metadata={"target_version": CASE_LIBRARY_TARGET_VERSION},
        path=output_path,
    )

    results = search_case_library("heat sink", path=output_path, limit=3)

    assert results
    assert results[0]["source"] == f"COMSOL CN 本地案例库（{CASE_LIBRARY_TARGET_VERSION}）"
    assert results[0]["target_version"] == CASE_LIBRARY_TARGET_VERSION
