"""Build runtime capability documents from native actions and COMSOL API wrappers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from agent.executor.java_api_controller import JavaAPIController


@dataclass
class ApiCapabilityEntry:
    """Runtime capability entry used by vector search and prompt injection."""

    name: str
    title: str
    description: str
    invoke_mode: str
    category: str
    recommended_action: str
    params_schema: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    wrapper_name: str = ""
    owner: str = ""
    method_name: str = ""
    keywords: List[str] = field(default_factory=list)

    @property
    def instructions(self) -> str:
        lines = [
            f"[Runtime capability] {self.title}",
            f"category: {self.category}",
            f"invoke_mode: {self.invoke_mode}",
            f"recommended_action: {self.recommended_action}",
        ]

        if self.invoke_mode == "wrapper":
            lines.extend(
                [
                    f"wrapper_name: {self.wrapper_name}",
                    f"owner: {self.owner}",
                    f"method_name: {self.method_name}",
                    "",
                    "Use this via ActionExecutor action `call_official_api` with `params.wrapper` "
                    "or `params.wrapper_name`. Do not invent a raw Java call when this wrapper covers "
                    "the operation.",
                ]
            )
            preferred_call: Dict[str, Any] = {
                "action": "call_official_api",
                "params": {
                    "wrapper": self.wrapper_name,
                    "args": [],
                    "target_path": "<COMSOL object path, if the method is not on model root>",
                },
            }
        else:
            lines.append("")
            lines.append(
                "Use this built-in native action first. It is still backed by COMSOL Java API calls, "
                "but it contains the repo's validation, planning, and save-path handling."
            )
            preferred_call = {"action": self.recommended_action}

        if self.description:
            lines.extend(["", f"description: {self.description}"])
        if self.params_schema:
            lines.extend(
                [
                    "",
                    "params_schema:",
                    json.dumps(self.params_schema, ensure_ascii=False, sort_keys=True),
                ]
            )
        if self.examples:
            lines.extend(
                [
                    "",
                    "catalog_examples:",
                    json.dumps(self.examples[:2], ensure_ascii=False, sort_keys=True),
                ]
            )
        lines.extend(
            [
                "",
                "preferred_call:",
                json.dumps(preferred_call, ensure_ascii=False, sort_keys=True),
            ]
        )
        if self.keywords:
            lines.extend(["", f"keywords: {', '.join(self.keywords)}"])
        return "\n".join(lines).strip()


def _wrapper_meta_from_item(item: Dict[str, Any]) -> tuple[str, str, str]:
    wrapper_name = str(item.get("label") or "")
    owner = ""
    method_name = ""
    examples = item.get("examples") or []
    if isinstance(examples, list) and examples:
        first = examples[0] if isinstance(examples[0], dict) else {}
        owner = str(first.get("owner") or "")
        method_name = str(first.get("method_name") or "")
    return wrapper_name, owner, method_name


def _keywords_for_entry(
    *,
    name: str,
    title: str,
    category: str,
    recommended_action: str,
    wrapper_name: str,
    owner: str,
    method_name: str,
) -> List[str]:
    raw = [name, title, category, recommended_action, wrapper_name, owner, method_name]
    if "mesh" in " ".join(raw).lower() or "网格" in " ".join(raw):
        raw.extend(["mesh", "网格", "boundary layer", "边界层"])
    if "geom" in " ".join(raw).lower() or "几何" in " ".join(raw):
        raw.extend(["geometry", "几何", "work plane", "工作面"])
    if "material" in " ".join(raw).lower() or "材料" in " ".join(raw):
        raw.extend(["material", "材料", "property", "属性"])
    if any(k in " ".join(raw).lower() for k in ["physics", "boundary", "heattransfer"]):
        raw.extend(["physics", "物理场", "boundary condition", "边界条件", "heat transfer", "传热"])
    if any(k in " ".join(raw).lower() for k in ["study", "solver", "solution", "solv"]):
        raw.extend(["study", "solver", "研究", "求解"])
    if any(k in " ".join(raw).lower() for k in ["result", "plot", "export"]):
        raw.extend(["result", "plot", "export", "结果", "导出"])

    seen: set[str] = set()
    keywords: List[str] = []
    for value in raw:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        keywords.append(text)
    return keywords


def _entry_from_ops_item(item: Dict[str, Any]) -> ApiCapabilityEntry:
    invoke_mode = str(item.get("invoke_mode") or "native")
    category = str(item.get("category") or "")
    recommended_action = str(item.get("recommended_action") or "")
    label = str(item.get("label") or recommended_action or "runtime capability")
    params_schema = item.get("params_schema") if isinstance(item.get("params_schema"), dict) else {}
    examples = item.get("examples") if isinstance(item.get("examples"), list) else []

    wrapper_name = ""
    owner = ""
    method_name = ""
    if invoke_mode == "wrapper":
        wrapper_name, owner, method_name = _wrapper_meta_from_item(item)
        name = wrapper_name or label
        title = f"{category} wrapper: {name}" if category else f"COMSOL API wrapper: {name}"
        description = (
            f"COMSOL Java API wrapper for {owner}.{method_name}; call it through "
            "`call_official_api` with `params.wrapper`."
        ).strip()
    else:
        name = f"native:{recommended_action or label}"
        title = label
        description = (
            "Native ActionExecutor operation. It should be preferred for regular modeling steps "
            "because it wraps COMSOL API calls with repo-specific schema handling."
        )

    return ApiCapabilityEntry(
        name=name,
        title=title,
        description=description,
        invoke_mode=invoke_mode,
        category=category,
        recommended_action=recommended_action,
        params_schema=params_schema,
        examples=examples,
        wrapper_name=wrapper_name,
        owner=owner,
        method_name=method_name,
        keywords=_keywords_for_entry(
            name=name,
            title=title,
            category=category,
            recommended_action=recommended_action,
            wrapper_name=wrapper_name,
            owner=owner,
            method_name=method_name,
        ),
    )


def build_api_capability_entries() -> List[ApiCapabilityEntry]:
    """
    Build native-action and wrapper capability entries from JavaAPIController.

    The result is intentionally runtime-facing: it tells the model which action or
    wrapper the current repo can execute, instead of only listing raw COMSOL API
    method names.
    """

    ctrl = JavaAPIController()
    result = ctrl.get_ops_catalog(limit=10_000, offset=0)
    items = result.get("items", []) if isinstance(result, dict) else []
    entries: List[ApiCapabilityEntry] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        entry = _entry_from_ops_item(item)
        if not entry.name or entry.name in seen:
            continue
        seen.add(entry.name)
        entries.append(entry)
    return entries

