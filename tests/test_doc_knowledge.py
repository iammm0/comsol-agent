from pathlib import Path

from agent.doc_knowledge import (
    DOC_KB_MARKER,
    import_comsol_docs,
    load_doc_kb_status,
    resolve_comsol_doc_root,
    search_doc_kb,
)
from agent.skills.injector import SkillInjector
from agent.skills.loader import SkillLoader


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_resolve_comsol_doc_root_from_plugins_dir(tmp_path):
    root = tmp_path / "COMSOL63" / "Multiphysics"
    plugins = root / "plugins"
    doc_dir = root / "doc" / "com.comsol.help.comsol"
    plugins.mkdir(parents=True)
    _write(
        doc_dir / "intro.html",
        "<html><head><title>Intro</title></head><body><h1>Intro</h1><p>Heat transfer.</p></body></html>",
    )

    resolved = resolve_comsol_doc_root(plugins)
    assert resolved == root / "doc"


def test_import_and_search_comsol_docs(tmp_path):
    doc_root = tmp_path / "doc" / "com.comsol.help.heat"
    _write(
        doc_root / "thermal.html",
        """
        <html>
          <head><title>Heat Transfer Module</title></head>
          <body>
            <h1>Heat Transfer Module</h1>
            <p>Thermal conductivity can be specified in the material model.</p>
            <p>Use heat flux or temperature boundaries depending on the problem.</p>
          </body>
        </html>
        """,
    )
    _write(
        doc_root / "geometry.txt",
        "Geometry Notes\nCreate work planes before building complex swept geometry.",
    )

    db_path = tmp_path / "doc_knowledge.db"
    result = import_comsol_docs(doc_root.parent, db_path=db_path, version="6.3")

    assert db_path.exists()
    assert result["documents"] == 2
    assert result["chunks"] >= 2

    status = load_doc_kb_status(db_path)
    assert status["exists"] is True
    assert status["documents"] == 2
    assert status["chunks"] >= 2

    hits = search_doc_kb("thermal conductivity", db_path=db_path, limit=3)
    assert hits
    assert any("Heat Transfer Module" in hit["title"] for hit in hits)
    assert any("thermal conductivity" in hit["text"].lower() for hit in hits)


def test_skill_injector_includes_doc_kb_snippets(tmp_path):
    doc_root = tmp_path / "doc" / "com.comsol.help.comsol"
    _write(
        doc_root / "mesh.html",
        """
        <html>
          <head><title>Mesh Refinement</title></head>
          <body>
            <h1>Mesh Refinement</h1>
            <p>Boundary layer meshes improve near-wall fluid and heat transfer resolution.</p>
          </body>
        </html>
        """,
    )
    db_path = tmp_path / "doc_knowledge.db"
    import_comsol_docs(doc_root.parent, db_path=db_path, version="6.3")

    injector = SkillInjector(
        loader=SkillLoader(roots=[]),
        top_k=1,
        doc_kb_path=db_path,
        doc_top_k=1,
    )
    prompt = injector.inject_into_prompt(
        "如何设置边界层网格来改善近壁面传热？",
        "user prompt",
    )

    assert DOC_KB_MARKER in prompt
    assert "Boundary layer meshes" in prompt
    assert injector.last_used_docs()
