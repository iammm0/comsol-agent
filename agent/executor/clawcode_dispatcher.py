"""claw-code subprocess dispatcher for COMSOL operations."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from agent.utils.config import get_project_root, get_settings
from agent.utils.logger import get_logger
from schemas.task import ExecutionStep, ReActTaskPlan

logger = get_logger(__name__)
COMSOL_API_INDEX_URL = "https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/api/index.html"
COMSOL_API_ALL_INDEX_URL = "https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/api/index-all.html"


class ClawCodeComsolDispatcher:
    """Delegate a single COMSOL operation to the local Python claw-code shell."""

    def __init__(self, project_root: Optional[Path] = None):
        self.settings = get_settings()
        self.project_root = Path(project_root or get_project_root()).resolve()
        self.agent_root = Path(self.settings.claw_code_agent_root).expanduser().resolve()

    def dispatch(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        thought: Dict[str, Any],
        *,
        target_output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run claw-code for one step and return its normalized JSON result."""

        self._validate_agent_root()
        prompt = self._build_prompt(plan, step, thought, target_output_path=target_output_path)
        cmd = self._build_command(prompt)
        env = self._build_env()

        try:
            completed = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                env=env,
                text=True,
                capture_output=True,
                timeout=float(self.settings.claw_code_timeout_seconds),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error("claw-code COMSOL 调度超时: %s", exc)
            return {
                "status": "error",
                "message": f"claw-code COMSOL 调度超时: {exc}",
                "details": {"timeout_seconds": self.settings.claw_code_timeout_seconds},
            }

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if completed.returncode != 0:
            logger.error("claw-code COMSOL 调度失败: %s", stderr.strip() or stdout.strip())
            return {
                "status": "error",
                "message": "claw-code COMSOL 调度进程失败",
                "details": {
                    "returncode": completed.returncode,
                    "stdout": stdout[-4000:],
                    "stderr": stderr[-4000:],
                },
            }

        parsed = self._extract_json(stdout)
        if parsed is None:
            return {
                "status": "error",
                "message": "claw-code 输出中未找到有效 JSON 结果",
                "details": {"stdout": stdout[-4000:], "stderr": stderr[-4000:]},
            }
        return self._normalize_result(parsed, stdout=stdout, stderr=stderr)

    def _validate_agent_root(self) -> None:
        main_file = self.agent_root / "src" / "main.py"
        if not main_file.exists():
            raise RuntimeError(f"claw-code Python 壳不存在或路径无效: {self.agent_root}")

    def _build_command(self, prompt: str) -> list[str]:
        cmd = [
            self.settings.claw_code_python_executable or "python3",
            "-m",
            "src.main",
            "agent",
            prompt,
            "--cwd",
            str(self.project_root),
            "--allow-shell",
            "--allow-write",
            "--max-turns",
            str(int(self.settings.claw_code_max_turns)),
        ]
        if self.settings.claw_code_model:
            cmd.extend(["--model", self.settings.claw_code_model])
        if self.settings.claw_code_base_url:
            cmd.extend(["--base-url", self.settings.claw_code_base_url])
        if self.settings.claw_code_api_key:
            cmd.extend(["--api-key", self.settings.claw_code_api_key])
        return cmd

    def _build_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        paths = [str(self.agent_root)]
        if existing_pythonpath:
            paths.append(existing_pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(paths)
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
            "你是 mph-agent 的 COMSOL 执行子进程。只负责执行下面这个单步 COMSOL 操作。\n"
            "必须使用当前仓库中已有的 Python 模块完成操作，例如 "
            "agent.executor.comsol_runner.COMSOLRunner 或 "
            "agent.executor.java_api_controller.JavaAPIController；不要在父进程中直接调用。\n"
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
    def _normalize_result(parsed: Dict[str, Any], *, stdout: str, stderr: str) -> Dict[str, Any]:
        status = parsed.get("status")
        if status not in {"success", "error"}:
            return {
                "status": "error",
                "message": "claw-code JSON 结果缺少有效 status",
                "details": {"result": parsed, "stdout": stdout[-4000:], "stderr": stderr[-4000:]},
            }

        result = dict(parsed)
        result.setdefault("message", "claw-code COMSOL 调度完成" if status == "success" else "claw-code COMSOL 调度失败")
        result.setdefault("artifacts", [])
        result.setdefault("details", {})
        return result
