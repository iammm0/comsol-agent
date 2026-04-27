"""Embedded claw-code dispatcher for COMSOL operations."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from agent.clawcode.agent_runtime import LocalCodingAgent
from agent.clawcode.agent_types import AgentPermissions, AgentRuntimeConfig, ModelConfig
from agent.utils.config import get_project_root, get_settings
from agent.utils.logger import get_logger
from schemas.task import ExecutionStep, ReActTaskPlan

logger = get_logger(__name__)
COMSOL_API_INDEX_URL = "https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/api/index.html"
COMSOL_API_ALL_INDEX_URL = "https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/api/index-all.html"


class ClawCodeComsolDispatcher:
    """Delegate a single COMSOL operation to the embedded Python claw-code library."""

    def __init__(self, project_root: Optional[Path] = None):
        self.settings = get_settings()
        self.project_root = Path(project_root or get_project_root()).resolve()

    def dispatch(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        thought: Dict[str, Any],
        *,
        target_output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run embedded claw-code for one step and return its normalized JSON result."""

        prompt = self._build_prompt(plan, step, thought, target_output_path=target_output_path)
        env = self._build_env()
        old_env = {key: os.environ.get(key) for key in env}
        os.environ.update(env)

        try:
            run_result = self._build_agent().run(prompt)
        except Exception as exc:
            logger.error("claw-code COMSOL 调度失败: %s", exc)
            return {
                "status": "error",
                "message": f"claw-code COMSOL 调度失败: {exc}",
                "details": {"exception": type(exc).__name__},
            }
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        final_output = run_result.final_output or ""
        if run_result.stop_reason:
            return {
                "status": "error",
                "message": f"claw-code COMSOL 调度未正常完成: {run_result.stop_reason}",
                "details": {
                    "stop_reason": run_result.stop_reason,
                    "final_output": final_output[-4000:],
                    "turns": run_result.turns,
                    "tool_calls": run_result.tool_calls,
                },
            }

        parsed = self._extract_json(final_output)
        if parsed is None:
            return {
                "status": "error",
                "message": "claw-code 输出中未找到有效 JSON 结果",
                "details": {
                    "final_output": final_output[-4000:],
                    "turns": run_result.turns,
                    "tool_calls": run_result.tool_calls,
                },
            }
        result = self._normalize_result(parsed, final_output=final_output)
        result.setdefault(
            "details",
            {},
        )
        if isinstance(result.get("details"), dict):
            result["details"].setdefault("turns", run_result.turns)
            result["details"].setdefault("tool_calls", run_result.tool_calls)
        return result

    def _build_agent(self) -> LocalCodingAgent:
        model_config = self._resolve_model_config()
        return LocalCodingAgent(
            model_config=model_config,
            runtime_config=AgentRuntimeConfig(
                cwd=self.project_root,
                max_turns=int(self.settings.claw_code_max_turns),
                command_timeout_seconds=float(self.settings.claw_code_timeout_seconds),
                permissions=AgentPermissions(
                    allow_file_write=True,
                    allow_shell_commands=True,
                    allow_destructive_shell_commands=False,
                ),
                session_directory=self.project_root / ".port_sessions" / "agent",
                scratchpad_root=self.project_root / ".port_sessions" / "scratchpad",
            ),
        )

    def _resolve_model_config(self) -> ModelConfig:
        """Resolve embedded claw-code's OpenAI-compatible model endpoint.

        CLAW_CODE_* remains the explicit override. Without it, the embedded
        executor follows the desktop-selected LLM backend so users do not need
        to configure a second, local OpenAI-compatible server.
        """

        if self.settings.claw_code_model or self.settings.claw_code_base_url:
            return ModelConfig(
                model=self.settings.claw_code_model
                or self.settings.get_model_for_backend(self.settings.llm_backend),
                base_url=self.settings.claw_code_base_url or "http://127.0.0.1:8000/v1",
                api_key=self.settings.claw_code_api_key or "local-token",
                timeout_seconds=float(self.settings.claw_code_timeout_seconds),
            )

        backend = (self.settings.llm_backend or "").strip().lower()
        model = self.settings.get_model_for_backend(backend)
        api_key = self.settings.get_api_key_for_backend(backend) or "local-token"

        if backend == "deepseek":
            base_url = "https://api.deepseek.com"
        elif backend == "kimi":
            base_url = "https://api.moonshot.ai/v1"
        elif backend == "openai-compatible":
            base_url = self.settings.openai_compatible_base_url or "http://127.0.0.1:8000/v1"
        elif backend == "ollama":
            base_url = (self.settings.ollama_url or "http://localhost:11434").rstrip("/") + "/v1"
        else:
            base_url = "http://127.0.0.1:8000/v1"
            model = model or self.settings.openai_compatible_model

        return ModelConfig(
            model=model or "gpt-3.5-turbo",
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=float(self.settings.claw_code_timeout_seconds),
        )

    def _build_env(self) -> Dict[str, str]:
        env = {}
        env["MPH_AGENT_ROOT"] = str(self.project_root)
        return env

    def _build_prompt(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        thought: Dict[str, Any],
        *,
        target_output_path: Optional[str],
    ) -> str:
        payload = {
            "plan": self._dump_model(plan),
            "step": self._dump_model(step),
            "thought": thought or {},
            "current_model_path": getattr(plan, "model_path", None),
            "target_output_path": target_output_path,
            "project_root": str(self.project_root),
        }
        return (
            "你是 mph-agent 内置的 claw-code COMSOL 执行库。只负责执行下面这个单步 COMSOL 操作。\n"
            "必须使用当前仓库中已有的 Python 模块完成操作，例如 "
            "agent.executor.comsol_runner.COMSOLRunner 或 "
            "agent.executor.java_api_controller.JavaAPIController；你当前已作为 mph-agent 进程内库运行，不要再启动外部 claw-code 子进程。\n"
            "优先使用 JSON CLI：python -m agent.executor.comsol_ops_cli。可用命令包括：\n"
            "- catalog --include-official：列出原生操作与从 COMSOL 6.3 官方 API 索引生成的包装调用。\n"
            "- create-model --payload-json '{...}'：按 GeometryPlan 创建模型。\n"
            "- call <operation> --payload-json '{...}'：调用 JavaAPIController 任意公开操作。\n"
            "- official --payload-json '{model_path, method, args, target_path}'：兜底调用模型对象/节点的 Java API 方法。\n"
            "- official-static --payload-json '{class_name, method, args}'：兜底调用静态 Java API。\n"
            f"COMSOL 6.3 Java API 入口：{COMSOL_API_INDEX_URL}；完整索引：{COMSOL_API_ALL_INDEX_URL}。\n"
            "只要 COMSOL Java API 支持的操作，都应通过 native operation、official/wrapper API 或静态 API 完成。\n"
            "允许读写项目文件和运行必要 shell 命令。完成后只输出一个 JSON 对象，不要输出 Markdown。\n"
            "JSON 格式必须为："
            "{\"status\":\"success|error\",\"message\":\"...\","
            "\"model_path\":\"可选当前最新 .mph 路径\","
            "\"saved_path\":\"可选保存路径\",\"artifacts\":[],\"details\":{}}。\n"
            "如果失败，status 必须为 error，并在 message/details 说明原因。\n"
            "单步任务载荷如下：\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _dump_model(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if hasattr(value, "dict"):
            return value.dict()
        return value

    @staticmethod
    def _extract_json(output: str) -> Optional[Dict[str, Any]]:
        fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", output, flags=re.DOTALL)
        for candidate in reversed(fenced):
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

        decoder = json.JSONDecoder()
        for index, char in reversed(list(enumerate(output))):
            if char != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(output[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    @staticmethod
    def _normalize_result(parsed: Dict[str, Any], *, final_output: str) -> Dict[str, Any]:
        status = parsed.get("status")
        if status not in {"success", "error"}:
            return {
                "status": "error",
                "message": "claw-code JSON 结果缺少有效 status",
                "details": {"result": parsed, "final_output": final_output[-4000:]},
            }

        result = dict(parsed)
        result.setdefault("message", "claw-code COMSOL 调度完成" if status == "success" else "claw-code COMSOL 调度失败")
        result.setdefault("artifacts", [])
        result.setdefault("details", {})
        return result
