"""mph-agent ↔ clawcode 接入桥。

这里集中管理把 mph-agent 主流程和 ``agent/clawcode/`` 各 runtime 拼装到一起的胶水代码。
原则：每个子模块只做一件事，本包内部不持有 LLM/COMSOL 相关业务逻辑，纯接入层。

模块概览：
- ``runtime_config``: 把 mph-agent settings + project root 转成 ``AgentRuntimeConfig``。
- ``budget``: 给 ReasoningEngine 注入 token 预算监控（``token_budget`` + ``tokenizer_runtime``）。
- ``memory``: 用 ``compact.compact_conversation`` / ``microcompact_messages`` 替换会话记忆。
- ``plan_sync``: 把 ``ReActTaskPlan`` 双向同步到 ``PlanRuntime`` / ``TaskRuntime``。
- ``ask_user``: 把前端 clarifying_answers 装进 ``AskUserRuntime`` 队列。
- ``comsol_tools``: 把 ``ActionExecutor`` 14 个 handler 注册成 ``agent_tools.AgentTool``。
- ``workflow``: 物化 ``.claw-workflows.json`` + ``WorkflowRuntime`` 描述标准建模管线。
- ``sub_agents``: 把 planner 子 Agent 写成 ``.claude/agents/*.md`` 供 ``agent_registry`` 加载。
- ``parity``: ``run_parity_audit`` 的轻量包装，便于 doctor / cli 子命令调用。
- ``mcp_plugin``: 把 ``MCPRuntime`` / ``PluginRuntime`` 状态摘要注入主对话 system prompt。
- ``worktree``: 给 ``do_run`` 提供 ``WorktreeRuntime`` 隔离选项。
"""

from .budget import (
    BudgetSnapshot,
    estimate_prompt_budget,
    format_budget_event_payload,
)
from .memory import (
    CompactSummaryResult,
    summarize_history_with_compact,
    microcompact_history_messages,
)
from .runtime_config import build_default_runtime_config, build_default_model_config
from .plan_sync import PlanSync
from .ask_user import seed_ask_user_runtime, resolve_clarifying_answer
from .comsol_tools import build_comsol_tool_registry
from .workflow import (
    DEFAULT_WORKFLOW_MANIFEST,
    ensure_default_workflow_manifest,
    get_workflow_definition,
    list_workflow_definitions,
    load_workflow_runtime,
)
from .sub_agents import ensure_sub_agent_definitions
from .parity import render_parity_report
from .mcp_plugin import describe_mcp_plugin_state
from .worktree import worktree_session

__all__ = [
    "BudgetSnapshot",
    "CompactSummaryResult",
    "DEFAULT_WORKFLOW_MANIFEST",
    "PlanSync",
    "build_comsol_tool_registry",
    "build_default_model_config",
    "build_default_runtime_config",
    "describe_mcp_plugin_state",
    "ensure_default_workflow_manifest",
    "ensure_sub_agent_definitions",
    "estimate_prompt_budget",
    "format_budget_event_payload",
    "get_workflow_definition",
    "list_workflow_definitions",
    "load_workflow_runtime",
    "microcompact_history_messages",
    "render_parity_report",
    "resolve_clarifying_answer",
    "seed_ask_user_runtime",
    "summarize_history_with_compact",
    "worktree_session",
]
