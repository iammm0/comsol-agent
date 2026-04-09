"""Conversation-scoped persistence utilities."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agent.utils.config import get_install_dir
from agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConversationEntry:
    """A single history record."""

    timestamp: str
    user_input: str
    plan: Optional[Dict[str, Any]] = None
    model_path: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class ContextSummary:
    """Light-weight summary used as planner memory."""

    summary: str
    last_updated: str
    total_conversations: int
    recent_shapes: List[str]
    preferences: Dict[str, Any]


class ContextManager:
    """Persistence under `.context/<conversation_id>/`."""

    def __init__(self, context_dir: Optional[Path] = None, conversation_id: Optional[str] = None):
        if context_dir is not None:
            self.context_dir = Path(context_dir)
        else:
            base = get_install_dir() / ".context"
            self.context_dir = base / (conversation_id or "default")

        self.context_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.context_dir / "history.json"
        self.summary_file = self.context_dir / "summary.json"
        self.latest_model_file = self.context_dir / "latest_model.txt"
        self.operations_file = self.context_dir / "operations.md"
        self.plan_file = self.context_dir / "plan.json"
        self.plan_readable_file = self.context_dir / "plan_readable.md"
        self.discussion_file = self.context_dir / "discussion.json"
        self.cases_dir = self.context_dir / "cases"
        self.dialog_logs_dir = self.context_dir / "dialog_logs"

    # ---- Dialog logs ----

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(k): ContextManager._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [ContextManager._json_safe(v) for v in value]
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        return str(value)

    @staticmethod
    def _compact_text(value: Any, max_len: int = 1000) -> str:
        text = value if isinstance(value, str) else json.dumps(
            ContextManager._json_safe(value),
            ensure_ascii=False,
        )
        if len(text) <= max_len:
            return text
        return f"{text[:max_len]}...(truncated)"

    def _dialog_log_paths(self, log_id: str) -> tuple[Path, Path]:
        return (
            self.dialog_logs_dir / f"{log_id}.md",
            self.dialog_logs_dir / f"{log_id}.jsonl",
        )

    def start_dialog_log(
        self,
        command: str,
        user_input: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        safe_command = re.sub(r"[^a-zA-Z0-9_-]+", "-", (command or "dialog").strip()) or "dialog"
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        log_id = f"{ts}-{safe_command}-{uuid4().hex[:8]}"
        markdown_path, jsonl_path = self._dialog_log_paths(log_id)
        self.dialog_logs_dir.mkdir(parents=True, exist_ok=True)

        started_at = datetime.now().isoformat()
        header_lines = [
            "# 对话动作日志",
            "",
            f"- 会话目录: `{self.context_dir}`",
            f"- 日志ID: `{log_id}`",
            f"- 命令: `{command or 'dialog'}`",
            f"- 开始时间: `{started_at}`",
            "",
            "## 用户输入",
            "",
            (user_input or "").strip() or "（空）",
            "",
            "## 元数据",
            "",
            "```json",
            json.dumps(self._json_safe(metadata or {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "## 动作流水",
            "",
        ]
        markdown_path.write_text("\n".join(header_lines) + "\n", encoding="utf-8")
        jsonl_path.write_text("", encoding="utf-8")
        self._append_dialog_jsonl(
            log_id,
            {
                "event": "dialog_start",
                "timestamp": started_at,
                "command": command or "dialog",
                "user_input": user_input or "",
                "metadata": self._json_safe(metadata or {}),
            },
        )
        return {
            "log_id": log_id,
            "markdown_path": str(markdown_path),
            "jsonl_path": str(jsonl_path),
        }

    def _append_dialog_jsonl(self, log_id: str, payload: Dict[str, Any]) -> None:
        _, jsonl_path = self._dialog_log_paths(log_id)
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(self._json_safe(payload), ensure_ascii=False) + "\n")

    def append_dialog_action(
        self,
        log_id: str,
        action: str,
        detail: str = "",
        *,
        level: str = "INFO",
        source: str = "runtime",
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        ts = datetime.now().isoformat()
        markdown_path, _ = self._dialog_log_paths(log_id)
        safe_data = self._json_safe(data or {})
        preview = self._compact_text(safe_data)
        line = (
            f"- `{ts}` [{(level or 'INFO').upper()}] `{source}` `{action}`"
            + (f": {detail}" if detail else "")
        )
        with open(markdown_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            if safe_data:
                f.write(f"  - data: `{preview}`\n")
        self._append_dialog_jsonl(
            log_id,
            {
                "event": "action",
                "timestamp": ts,
                "level": (level or "INFO").upper(),
                "source": source,
                "action": action,
                "detail": detail or "",
                "data": safe_data,
            },
        )

    def finish_dialog_log(
        self,
        log_id: str,
        success: bool,
        summary: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        status = "SUCCESS" if success else "FAILED"
        ts = datetime.now().isoformat()
        markdown_path, _ = self._dialog_log_paths(log_id)
        with open(markdown_path, "a", encoding="utf-8") as f:
            f.write("\n## 结束状态\n\n")
            f.write(f"- 状态: `{status}`\n")
            f.write(f"- 时间: `{ts}`\n")
            f.write(f"- 摘要: {summary or '（空）'}\n")
            if data:
                f.write(f"- 数据: `{self._compact_text(self._json_safe(data))}`\n")
        self._append_dialog_jsonl(
            log_id,
            {
                "event": "dialog_end",
                "timestamp": ts,
                "success": bool(success),
                "summary": summary or "",
                "data": self._json_safe(data or {}),
            },
        )

    # ---- Model pointer ----

    def set_latest_model(self, model_path: str) -> None:
        if not model_path:
            return
        try:
            self.latest_model_file.write_text(model_path.strip(), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to write latest_model.txt: %s", e)

    def get_latest_model_path(self) -> Optional[str]:
        if not self.latest_model_file.exists():
            return None
        try:
            return self.latest_model_file.read_text(encoding="utf-8").strip() or None
        except Exception:
            return None

    # ---- Plan persistence ----

    def load_plan(self) -> Optional[Dict[str, Any]]:
        if not self.plan_file.exists():
            return None
        try:
            return json.loads(self.plan_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load plan.json: %s", e)
            return None

    def save_plan(self, plan_dict: Dict[str, Any]) -> None:
        try:
            self.plan_file.write_text(
                json.dumps(plan_dict, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Failed to save plan.json: %s", e)

    def load_plan_readable(self) -> Optional[str]:
        if not self.plan_readable_file.exists():
            return None
        try:
            return self.plan_readable_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to load plan_readable.md: %s", e)
            return None

    def save_plan_readable(self, content: str) -> None:
        try:
            self.plan_readable_file.write_text((content or "").strip() + "\n", encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save plan_readable.md: %s", e)

    # ---- Discussion persistence ----

    def load_discussion_card(self) -> Optional[Dict[str, Any]]:
        if not self.discussion_file.exists():
            return None
        try:
            return json.loads(self.discussion_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load discussion.json: %s", e)
            return None

    def save_discussion_card(self, card: Dict[str, Any]) -> None:
        try:
            self.discussion_file.write_text(
                json.dumps(card, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Failed to save discussion.json: %s", e)

    # ---- Case persistence ----

    def get_cases_dir(self) -> Path:
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        return self.cases_dir

    def save_case_file(self, case_dict: Dict[str, Any], model_stem: str) -> Path:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{model_stem}-{ts}.json"
        path = self.get_cases_dir() / filename
        path.write_text(json.dumps(case_dict, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    # ---- Operation log ----

    def start_run_log(self, user_input: str) -> None:
        try:
            if not self.operations_file.exists():
                self.operations_file.write_text("# 建模操作记录\n\n", encoding="utf-8")
            with open(self.operations_file, "a", encoding="utf-8") as f:
                f.write(
                    "\n---\n\n"
                    f"## {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 运行\n\n"
                    f"**用户输入**: {user_input}\n\n"
                )
        except Exception as e:
            logger.warning("Failed to append run header: %s", e)

    def append_operation(
        self,
        step_type: str,
        message: str,
        result_summary: str = "",
        model_path: Optional[str] = None,
    ) -> None:
        try:
            line = f"- **{step_type}** ({datetime.now().strftime('%H:%M:%S')}): {message}"
            if result_summary:
                line += f" - {result_summary}"
            if model_path:
                line += f"\n  - 模型: `{model_path}`"
            line += "\n"
            with open(self.operations_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            logger.warning("Failed to append operations.md: %s", e)

    # ---- Conversation history ----

    def add_conversation(
        self,
        user_input: str,
        plan: Optional[Dict[str, Any]] = None,
        model_path: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> ConversationEntry:
        entry = ConversationEntry(
            timestamp=datetime.now().isoformat(),
            user_input=user_input,
            plan=plan,
            model_path=str(model_path) if model_path else None,
            success=success,
            error=error,
        )
        history = self.load_history()
        history.append(asdict(entry))
        if len(history) > 100:
            history = history[-100:]
        self.save_history(history)
        self.update_summary()
        if model_path:
            self.set_latest_model(str(model_path))
        return entry

    def load_history(self) -> List[Dict[str, Any]]:
        if not self.history_file.exists():
            return []
        try:
            return json.loads(self.history_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load history.json: %s", e)
            return []

    def save_history(self, history: List[Dict[str, Any]]) -> None:
        try:
            self.history_file.write_text(
                json.dumps(history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to save history.json: %s", e)

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.load_history()[-limit:]

    # ---- Summary ----

    def load_summary(self) -> Optional[ContextSummary]:
        if not self.summary_file.exists():
            return None
        try:
            return ContextSummary(**json.loads(self.summary_file.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning("Failed to load summary.json: %s", e)
            return None

    def save_summary(self, summary: ContextSummary) -> None:
        try:
            self.summary_file.write_text(
                json.dumps(asdict(summary), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to save summary.json: %s", e)

    def set_summary_text(self, text: str) -> None:
        current = self.load_summary()
        history_len = len(self.load_history())
        summary = ContextSummary(
            summary=(text or "").strip(),
            last_updated=datetime.now().isoformat(),
            total_conversations=current.total_conversations if current else history_len,
            recent_shapes=current.recent_shapes if current else [],
            preferences=current.preferences if current else {},
        )
        self.save_summary(summary)

    def update_summary(self) -> None:
        history = self.load_history()
        if not history:
            return

        recent_shapes: List[str] = []
        unit_counter: Dict[str, int] = {}
        for entry in history[-20:]:
            plan = entry.get("plan") or {}
            for shape in plan.get("shapes", []) if isinstance(plan, dict) else []:
                shape_type = str(shape.get("type", "")).strip()
                if shape_type and shape_type not in recent_shapes:
                    recent_shapes.append(shape_type)
            if isinstance(plan, dict):
                unit = str(plan.get("units", "")).strip()
                if unit:
                    unit_counter[unit] = unit_counter.get(unit, 0) + 1

        preferences: Dict[str, Any] = {}
        if unit_counter:
            preferences["preferred_unit"] = max(unit_counter.items(), key=lambda x: x[1])[0]

        summary = ContextSummary(
            summary=self._generate_summary_text(history, recent_shapes, preferences),
            last_updated=datetime.now().isoformat(),
            total_conversations=len(history),
            recent_shapes=recent_shapes,
            preferences=preferences,
        )
        self.save_summary(summary)

    def _generate_summary_text(
        self,
        history: List[Dict[str, Any]],
        recent_shapes: List[str],
        preferences: Dict[str, Any],
    ) -> str:
        total = len(history)
        successful = sum(1 for e in history if e.get("success", True))
        lines = [f"总计 {total} 次对话，成功 {successful} 次。"]
        if recent_shapes:
            lines.append(f"最近形状类型: {', '.join(recent_shapes)}。")
        if preferences.get("preferred_unit"):
            lines.append(f"常用单位: {preferences['preferred_unit']}。")
        lines.append("最近活动:")
        for entry in history[-5:]:
            user_input = str(entry.get("user_input", "")).strip()[:50]
            status = "成功" if entry.get("success", True) else "失败"
            lines.append(f"  - {user_input}... ({status})")
        return "\n".join(lines)

    def get_context_for_planner(self) -> str:
        summary = self.load_summary()
        if not summary:
            return ""
        lines: List[str] = []
        if summary.recent_shapes:
            lines.append(f"最近形状类型: {', '.join(summary.recent_shapes)}")
        if summary.preferences.get("preferred_unit"):
            lines.append(f"常用单位: {summary.preferences['preferred_unit']}")
        return "\n".join(lines)

    # ---- Misc ----

    def clear_history(self) -> None:
        for p in (
            self.history_file,
            self.summary_file,
            self.latest_model_file,
            self.plan_file,
            self.plan_readable_file,
            self.discussion_file,
        ):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass

    def delete_conversation_and_models(self) -> List[str]:
        deleted_paths: List[str] = []
        for entry in self.load_history():
            path = entry.get("model_path")
            if not path:
                continue
            p = Path(path)
            if p.exists() and p.suffix.lower() == ".mph":
                try:
                    p.unlink()
                    deleted_paths.append(path)
                except Exception as e:
                    logger.warning("Failed to delete model %s: %s", path, e)
        self.clear_history()
        if self.context_dir.exists():
            shutil.rmtree(self.context_dir, ignore_errors=True)
        return deleted_paths

    def get_stats(self) -> Dict[str, Any]:
        history = self.load_history()
        summary = self.load_summary()
        return {
            "total_conversations": len(history),
            "successful": sum(1 for e in history if e.get("success", True)),
            "failed": sum(1 for e in history if not e.get("success", True)),
            "summary": summary.summary if summary else "暂无摘要",
            "recent_shapes": summary.recent_shapes if summary else [],
            "preferences": summary.preferences if summary else {},
        }

    def get_recent_models(self, limit: int = 20) -> List[Dict[str, Any]]:
        history = self.load_history()
        out: List[Dict[str, Any]] = []
        seen = set()
        latest_path = self.get_latest_model_path()
        for entry in reversed(history[-100:]):
            path = entry.get("model_path")
            if not path or path in seen or not Path(path).exists():
                continue
            seen.add(path)
            title = (entry.get("user_input") or Path(path).stem or path)[:50]
            out.append(
                {
                    "path": path,
                    "title": title.strip() or Path(path).name,
                    "timestamp": entry.get("timestamp", ""),
                    "is_latest": path == latest_path,
                }
            )
            if len(out) >= limit:
                break
        return out


def get_all_models_from_context(limit: int = 50) -> List[Dict[str, Any]]:
    """Aggregate models from all conversation folders."""

    base = get_install_dir() / ".context"
    if not base.exists():
        return []
    collected: List[Dict[str, Any]] = []
    seen = set()
    conv_dirs = sorted(
        [p for p in base.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for conv_dir in conv_dirs:
        hist_file = conv_dir / "history.json"
        latest_file = conv_dir / "latest_model.txt"
        latest_path = None
        if latest_file.exists():
            try:
                latest_path = latest_file.read_text(encoding="utf-8").strip() or None
            except Exception:
                latest_path = None
        if not hist_file.exists():
            continue
        try:
            history = json.loads(hist_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        for entry in reversed(history):
            path = entry.get("model_path")
            if not path or path in seen or not Path(path).exists():
                continue
            seen.add(path)
            title = (entry.get("user_input") or Path(path).stem or path)[:50]
            collected.append(
                {
                    "path": path,
                    "title": title.strip() or Path(path).name,
                    "timestamp": entry.get("timestamp", ""),
                    "is_latest": path == latest_path,
                }
            )
            if len(collected) >= limit:
                return collected
    return collected


_context_manager: Optional[ContextManager] = None


def get_context_manager(conversation_id: Optional[str] = None) -> ContextManager:
    """Get default manager or conversation-scoped manager."""

    global _context_manager
    if conversation_id:
        return ContextManager(conversation_id=conversation_id)
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
