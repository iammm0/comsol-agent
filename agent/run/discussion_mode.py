"""Discussion stage handler for `/discuss`."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

from schemas.task import DiscussionCard

FINALIZE_KEYWORDS = (
    "结束探讨",
    "进入规划",
    "确认探讨结论",
    "探讨完成",
    "开始规划",
    "finish discuss",
    "done discuss",
)
REOPEN_KEYWORDS = ("继续探讨", "重新探讨", "reopen discuss")


def _split_points(text: str) -> List[str]:
    raw = re.split(r"[\n\r;；。.!?！？]+", text or "")
    out: List[str] = []
    for item in raw:
        s = item.strip().lstrip("-•*").strip()
        if s:
            out.append(s)
    return out


def _dedupe_keep_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        norm = item.strip()
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out


def _looks_metric(text: str) -> bool:
    return bool(re.search(r"(误差|效率|温度|应力|压降|位移|功率|频率|响应|收敛|RMS|dB|%)", text))


def _looks_risk(text: str) -> bool:
    return bool(re.search(r"(风险|不稳定|不确定|可能失败|难以收敛|发散|敏感)", text))


def _looks_unknown(text: str) -> bool:
    return "?" in text or bool(re.search(r"(未知|不确定|待定|还没|尚未|需要确认|需要澄清)", text))


def _looks_principle(text: str) -> bool:
    return bool(re.search(r"(原理|机理|守恒|热传导|对流|辐射|应力|流体|电磁|耦合|方程)", text))


def _looks_solution(text: str) -> bool:
    return bool(re.search(r"(方案|可选|建议|可以|尝试|路线|建模思路|思路)", text))


def _looks_known_input(text: str) -> bool:
    return bool(re.search(r"\d", text)) or bool(
        re.search(r"(边界条件|材料|几何|尺寸|厚度|电流|电压|温度|流速|压力)", text)
    )


class DiscussionModeHandler:
    """Incrementally builds a structured discussion card."""

    def __init__(self, context_manager):
        self.context_manager = context_manager

    def _load_or_create_card(self) -> DiscussionCard:
        current = self.context_manager.load_discussion_card()
        if current:
            try:
                return DiscussionCard.model_validate(current)
            except Exception:
                pass
        return DiscussionCard()

    def _save_card(self, card: DiscussionCard) -> None:
        payload = card.model_dump(mode="json")
        self.context_manager.save_discussion_card(payload)

    def _update_card(self, card: DiscussionCard, user_input: str) -> None:
        points = _split_points(user_input)
        for p in points:
            if _looks_risk(p):
                card.risks.append(p)
                continue
            if _looks_unknown(p):
                card.unknowns.append(p)
                continue
            if _looks_metric(p):
                card.target_metrics.append(p)
                continue
            if _looks_principle(p):
                card.physical_principles.append(p)
                continue
            if _looks_solution(p):
                card.candidate_solutions.append(p)
                continue
            if _looks_known_input(p):
                card.known_inputs.append(p)
                continue
            card.assumptions.append(p)

        card.physical_principles = _dedupe_keep_order(card.physical_principles)
        card.target_metrics = _dedupe_keep_order(card.target_metrics)
        card.known_inputs = _dedupe_keep_order(card.known_inputs)
        card.unknowns = _dedupe_keep_order(card.unknowns)
        card.assumptions = _dedupe_keep_order(card.assumptions)
        card.risks = _dedupe_keep_order(card.risks)
        card.candidate_solutions = _dedupe_keep_order(card.candidate_solutions)
        card.updated_at = datetime.now()

    def process(self, user_input: str) -> Tuple[str, Dict[str, object]]:
        text = (user_input or "").strip()
        card = self._load_or_create_card()
        lowered = text.lower()

        if any(k in lowered for k in REOPEN_KEYWORDS):
            card.finalized = False

        if card.finalized and not any(k in lowered for k in REOPEN_KEYWORDS):
            self._save_card(card)
            return (
                "讨论卡已 finalized。请进入 `/plan` 生成建模规划；若要继续讨论，请先发送“继续探讨”。",
                card.model_dump(mode="json"),
            )

        if any(k in lowered for k in FINALIZE_KEYWORDS):
            card.finalized = True
            card.updated_at = datetime.now()
            self._save_card(card)
            return (
                "探讨已确认结束，讨论卡已 finalized。现在可使用 `/plan` 进入建模规划。",
                card.model_dump(mode="json"),
            )

        self._update_card(card, text)
        self._save_card(card)
        summary = (
            "讨论卡已更新："
            f"原理 {len(card.physical_principles)} 条，指标 {len(card.target_metrics)} 条，"
            f"已知输入 {len(card.known_inputs)} 条，未知项 {len(card.unknowns)} 条。"
            "如需结束讨论，请发送“结束探讨”或“进入规划”。"
        )
        return summary, card.model_dump(mode="json")

