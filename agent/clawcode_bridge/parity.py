"""``parity_audit`` + 端口清单（commands/tools）轻量包装。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from agent.clawcode.commands import PORTED_COMMANDS
from agent.clawcode.parity_audit import run_parity_audit
from agent.clawcode.tools import PORTED_TOOLS


def render_parity_report(*, include_backlog: bool = True) -> Dict[str, Any]:
    """对外友好的字典形式 parity report，便于 doctor / cli 直接 print。"""

    audit = run_parity_audit()
    payload: Dict[str, Any] = {
        "archive_present": audit.archive_present,
        "root_file_coverage": list(audit.root_file_coverage),
        "directory_coverage": list(audit.directory_coverage),
        "total_file_ratio": list(audit.total_file_ratio),
        "command_entry_ratio": list(audit.command_entry_ratio),
        "tool_entry_ratio": list(audit.tool_entry_ratio),
        "missing_root_targets": list(audit.missing_root_targets),
        "missing_directory_targets": list(audit.missing_directory_targets),
        "markdown": audit.to_markdown(),
    }
    if include_backlog:
        payload["commands"] = {
            "ported_count": len(PORTED_COMMANDS),
            "items": list_ported_commands(),
        }
        payload["tools"] = {
            "ported_count": len(PORTED_TOOLS),
            "items": list_ported_tools(),
        }
    return payload


def list_ported_commands() -> List[Dict[str, str]]:
    return [asdict(item) for item in PORTED_COMMANDS]


def list_ported_tools() -> List[Dict[str, str]]:
    return [asdict(item) for item in PORTED_TOOLS]
