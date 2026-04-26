# PyInstaller spec for mph-agent-bridge (desktop 安装包内嵌的 Python 后端)
# 在项目根目录执行: pyinstaller desktop/scripts/bridge.spec

import sys
from pathlib import Path

# 项目根（spec 在 desktop/scripts/bridge.spec，SPECPATH = desktop/scripts）
ROOT = Path(SPECPATH).resolve().parent.parent

a = Analysis(
    [str(ROOT / "bridge_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "prompts"), "prompts"),
        (str(ROOT / "agent" / "clawcode" / "reference_data"), "agent/clawcode/reference_data"),
        (str(ROOT / "agent" / "clawcode" / "gui" / "static"), "agent/clawcode/gui/static"),
    ],
    hiddenimports=[
        "agent",
        "agent.run",
        "agent.run.tui_bridge",
        "agent.run.actions",
        "agent.core",
        "agent.executor",
        "agent.executor.clawcode_dispatcher",
        "agent.executor.comsol_ops_cli",
        "agent.clawcode",
        "agent.clawcode.agent_runtime",
        "agent.clawcode.agent_tools",
        "agent.clawcode.agent_types",
        "agent.clawcode.openai_compat",
        "agent.clawcode.plugin_runtime",
        "agent.clawcode.mcp_runtime",
        "agent.clawcode.gui.server",
        "agent.planner",
        "agent.react",
        "agent.utils",
        "agent.utils.config",
        "agent.utils.java_runtime",
        "scripts.sync_comsol_case_library",
        "schemas",
        "dotenv",
        "pydantic",
        "pydantic_settings",
        "openai",
        "requests",
        "jpype",
        "_jpype",
        "loguru",
        "questionary",
        "fastapi",
        "uvicorn",
        "starlette",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch", "tensorflow", "transformers", "sentence_transformers",
        "IPython", "jupyter", "matplotlib", "PIL", "cv2",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="mph-agent-bridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不弹控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
