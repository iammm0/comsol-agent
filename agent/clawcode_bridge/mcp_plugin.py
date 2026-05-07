"""Surface MCPRuntime / PluginRuntime / SearchRuntime state to the main loop.

mph-agent 主流程在 ``ClawCodeComsolDispatcher.dispatch`` 之前并不会去看
``.claw-mcp.json`` / ``.claw-plugins.json`` 这类 manifest，但桌面端用户希望直接
配置 MCP server 让 mph-agent 用得上。我们这里只暴露"快照"：
- 加载 ``MCPRuntime / PluginRuntime / SearchRuntime / RemoteRuntime`` 等只读运行时；
- 把摘要拼到 dispatcher 给 LocalCodingAgent 的 prompt 里，作为 context；
- 同时返回结构化数据，方便 doctor/桌面端展示。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from agent.clawcode.account_runtime import AccountRuntime
from agent.clawcode.mcp_runtime import MCPRuntime
from agent.clawcode.plugin_runtime import PluginRuntime
from agent.clawcode.remote_runtime import RemoteRuntime
from agent.clawcode.remote_trigger_runtime import RemoteTriggerRuntime
from agent.clawcode.search_runtime import SearchRuntime
from agent.clawcode.team_runtime import TeamRuntime
from agent.clawcode.workflow_runtime import WorkflowRuntime
from agent.clawcode.worktree_runtime import WorktreeRuntime
from agent.utils.logger import get_logger

logger = get_logger(__name__)


def describe_mcp_plugin_state(project_root: Path) -> Dict[str, Any]:
    """汇总 ``MCPRuntime / PluginRuntime / SearchRuntime ...`` 的状态摘要。"""

    cwd = project_root.resolve()
    snapshot: Dict[str, Any] = {}
    try:
        mcp = MCPRuntime.from_workspace(cwd)
        snapshot["mcp"] = {
            "manifests": list(mcp.manifests),
            "resource_count": len(mcp.resources),
            "server_count": len(mcp.servers),
            "summary": mcp.render_summary() if mcp.resources or mcp.servers else "",
        }
    except Exception as exc:  # pragma: no cover
        logger.debug("MCPRuntime 加载失败：%s", exc)

    try:
        plugin = PluginRuntime.from_workspace(cwd)
        snapshot["plugin"] = {
            "manifests": list(plugin.manifests),
            "summary": plugin.render_summary() if plugin.manifests else "",
        }
    except Exception as exc:  # pragma: no cover
        logger.debug("PluginRuntime 加载失败：%s", exc)

    try:
        search = SearchRuntime.from_workspace(cwd)
        snapshot["search"] = {
            "summary": (
                search.render_summary() if search.has_search_runtime() else ""
            ),
        }
    except Exception as exc:  # pragma: no cover
        logger.debug("SearchRuntime 加载失败：%s", exc)

    try:
        remote = RemoteRuntime.from_workspace(cwd)
        snapshot["remote"] = {
            "has_remote_config": remote.has_remote_config(),
            "summary": remote.render_summary() if remote.has_remote_config() else "",
        }
    except Exception as exc:  # pragma: no cover
        logger.debug("RemoteRuntime 加载失败：%s", exc)

    try:
        trigger = RemoteTriggerRuntime.from_workspace(cwd)
        snapshot["remote_trigger"] = {
            "summary": trigger.render_summary() if trigger.has_state() else "",
        }
    except Exception as exc:  # pragma: no cover
        logger.debug("RemoteTriggerRuntime 加载失败：%s", exc)

    try:
        team = TeamRuntime.from_workspace(cwd)
        snapshot["team"] = {
            "summary": team.render_summary() if team.has_team_state() else "",
        }
    except Exception as exc:  # pragma: no cover
        logger.debug("TeamRuntime 加载失败：%s", exc)

    try:
        workflow = WorkflowRuntime.from_workspace(cwd)
        snapshot["workflow"] = {
            "summary": workflow.render_summary() if workflow.has_workflows() else "",
            "manifests": list(workflow.manifests),
            "configured": len(workflow.workflows),
        }
    except Exception as exc:  # pragma: no cover
        logger.debug("WorkflowRuntime 加载失败：%s", exc)

    try:
        worktree = WorktreeRuntime.from_workspace(cwd)
        snapshot["worktree"] = {
            "active": worktree.active_session is not None,
            "summary": worktree.render_summary() if worktree.repo_root is not None else "",
        }
    except Exception as exc:  # pragma: no cover
        logger.debug("WorktreeRuntime 加载失败：%s", exc)

    try:
        account = AccountRuntime.from_workspace(cwd)
        snapshot["account"] = {
            "summary": account.render_summary() if account.has_account_state() else "",
        }
    except Exception as exc:  # pragma: no cover
        logger.debug("AccountRuntime 加载失败：%s", exc)

    return snapshot


def render_dispatcher_context_block(project_root: Path) -> str:
    """返回一段可拼到 prompt 的 markdown，列出当前 MCP / plugin / workflow 状态。"""

    state = describe_mcp_plugin_state(project_root)
    lines: list[str] = []
    for key, label in (
        ("mcp", "MCP servers"),
        ("plugin", "Plugins"),
        ("workflow", "Workflows"),
        ("worktree", "Worktree"),
        ("search", "Search providers"),
        ("remote", "Remote runtime"),
    ):
        block = state.get(key) or {}
        summary = (block.get("summary") or "").strip()
        if not summary:
            continue
        lines.append(f"### {label}")
        lines.append(summary)
        lines.append("")
    if not lines:
        return ""
    return "\n".join(["## clawcode 接入状态", "", *lines]).rstrip()
