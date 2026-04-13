"""Prompt injection for local skills and the optional COMSOL documentation KB."""

from pathlib import Path
from typing import List, Optional
import re

from agent.doc_knowledge import format_doc_hits_for_prompt, search_doc_kb
from agent.skills.api_catalog_builder import ApiCapabilityEntry, build_api_capability_entries
from agent.skills.loader import Skill, SkillLoader
from agent.skills.vector_store import SkillVectorStore
from agent.utils.logger import get_logger

logger = get_logger(__name__)

MARKER = "=== RELEVANT SKILLS (请采纳以下隐性知识) ==="
RUNTIME_MARKER = "=== RELEVANT RUNTIME CAPABILITIES (prefer these actions/wrappers) ==="


class SkillInjector:
    """
    Select relevant local skills and optional imported COMSOL documentation snippets,
    then prepend them to the prompt before an LLM call.
    """

    def __init__(
        self,
        loader: Optional[SkillLoader] = None,
        vector_store: Optional[SkillVectorStore] = None,
        top_k: int = 5,
        doc_kb_path: Optional[Path] = None,
        doc_top_k: int = 3,
    ):
        self.loader = loader or SkillLoader()
        self.vector_store = vector_store
        self.top_k = max(1, top_k)
        self.doc_kb_path = Path(doc_kb_path) if doc_kb_path else None
        self.doc_top_k = max(0, doc_top_k)
        self._last_used: List[str] = []
        self._last_used_capabilities: List[str] = []
        self._last_used_docs: List[str] = []
        # Lazy-load API capability entries only when vector indexing is enabled.
        self._api_entries: Optional[List[ApiCapabilityEntry]] = None

    def _get_api_entries(self) -> List[ApiCapabilityEntry]:
        """Build API capability entries from JavaAPIController wrappers."""

        if self._api_entries is None:
            try:
                self._api_entries = build_api_capability_entries()
            except Exception:
                self._api_entries = []
        return self._api_entries or []

    def get_api_capability_docs(self) -> List[Skill]:
        """Expose runtime capability entries as in-memory skill-like documents."""

        skills: List[Skill] = []
        for entry in self._get_api_entries():
            skills.append(
                Skill(
                    name=entry.name,
                    description=entry.title,
                    instructions=entry.instructions,
                    version=None,
                    author=None,
                    tags=[
                        "comsol-api",
                        "java-api",
                        "runtime-capability",
                        entry.invoke_mode,
                        entry.category,
                        entry.recommended_action,
                    ],
                    triggers=list(entry.keywords or []),
                    prerequisites=[],
                    path=None,
                )
            )
        return skills

    @staticmethod
    def _query_terms(query: str) -> List[str]:
        lowered = (query or "").lower()
        terms = re.findall(r"[a-z0-9_]+", lowered)
        for segment in re.findall(r"[\u4e00-\u9fff]{2,}", lowered):
            terms.append(segment)
            max_len = min(4, len(segment))
            for size in range(2, max_len + 1):
                for index in range(0, len(segment) - size + 1):
                    terms.append(segment[index : index + size])
        seen: set[str] = set()
        output: List[str] = []
        for term in terms:
            if len(term) < 2 or term in seen:
                continue
            seen.add(term)
            output.append(term)
        return output

    def _search_capability_entries(self, query: str, limit: int = 3) -> List[ApiCapabilityEntry]:
        terms = self._query_terms(query)
        if not terms:
            self._last_used_capabilities = []
            return []
        scored = []
        for entry in self._get_api_entries():
            haystack = " ".join(
                [
                    entry.name,
                    entry.title,
                    entry.description,
                    entry.category,
                    entry.recommended_action,
                    entry.wrapper_name,
                    entry.owner,
                    entry.method_name,
                    " ".join(entry.keywords or []),
                ]
            ).lower()
            score = 0
            for term in terms:
                if term in haystack:
                    score += 4
            if score > 0 and entry.invoke_mode == "native":
                score += 1
            if score > 0:
                scored.append((score, entry))
        scored.sort(
            key=lambda item: (
                -item[0],
                0 if item[1].invoke_mode == "native" else 1,
                item[1].title,
            )
        )
        results = [entry for _score, entry in scored[: max(1, int(limit))]]
        self._last_used_capabilities = [entry.name for entry in results]
        return results

    def _get_skills_block(self, query: str) -> tuple[str, List[str]]:
        """Return selected skill instructions and skill names."""

        block_parts: List[str] = []
        names_used: List[str] = []

        # 1) Prefer vector search when configured and indexed.
        if self.vector_store and query:
            all_skills: List[Skill] = self.loader.list_skills() + self.get_api_capability_docs()
            self.vector_store.ensure_indexed(all_skills)
            hits = self.vector_store.search(query, top_k=self.top_k)
            if hits:
                for name, content, _distance in hits:
                    if content and name not in names_used:
                        block_parts.append(content)
                        names_used.append(name)
                if block_parts:
                    self._last_used = names_used
                    return "\n\n".join(block_parts), self._last_used

        # 2) Fall back to trigger/tag matching.
        skills = self.loader.get_skills_by_triggers(query)
        if not skills:
            skills = self.loader.list_skills()[: self.top_k]
        else:
            skills = skills[: self.top_k]
        if not skills:
            self._last_used = []
            return "", []
        self._last_used = [skill.name for skill in skills]
        block = "\n\n".join(
            skill.instructions for skill in skills if skill.instructions and skill.instructions.strip()
        )
        return block, self._last_used

    def _get_runtime_capabilities_block(self, query: str) -> tuple[str, List[str]]:
        """Return runtime-native/action wrapper guidance for the current query."""

        entries = self._search_capability_entries(query, limit=min(3, self.top_k))
        if not entries:
            self._last_used_capabilities = []
            return "", []
        block = "\n\n".join(entry.instructions for entry in entries if entry.instructions.strip())
        return block, self._last_used_capabilities

    def _get_doc_block(self, query: str) -> tuple[str, List[str]]:
        """Return selected local COMSOL documentation snippets and their sources."""

        self._last_used_docs = []
        if not query or self.doc_top_k <= 0:
            return "", []
        try:
            hits = search_doc_kb(query, limit=self.doc_top_k, db_path=self.doc_kb_path)
        except Exception as exc:
            logger.debug("COMSOL doc KB search failed: %s", exc)
            return "", []
        if not hits:
            return "", []
        self._last_used_docs = [
            str(hit.get("source_url") or hit.get("source_path") or hit.get("id") or "")
            for hit in hits
        ]
        return format_doc_hits_for_prompt(hits), self._last_used_docs

    def _get_injection_blocks(self, query: str) -> List[str]:
        blocks: List[str] = []
        skills_block, _ = self._get_skills_block(query)
        if skills_block:
            blocks.append(f"{MARKER}\n{skills_block}")
        runtime_block, _ = self._get_runtime_capabilities_block(query)
        if runtime_block:
            blocks.append(f"{RUNTIME_MARKER}\n{runtime_block}")
        doc_block, _ = self._get_doc_block(query)
        if doc_block:
            blocks.append(doc_block)
        return blocks

    def inject(self, query: str, system_prompt: str) -> str:
        """Return the enhanced system prompt."""

        blocks = self._get_injection_blocks(query)
        if not blocks:
            return system_prompt
        return f"{system_prompt}\n\n" + "\n\n".join(blocks)

    def inject_into_prompt(self, query: str, user_prompt: str) -> str:
        """Prepend selected knowledge to a single user prompt."""

        blocks = self._get_injection_blocks(query)
        if not blocks:
            return user_prompt
        return "\n\n".join(blocks) + f"\n\n---\n\n{user_prompt}"

    def last_used_skills(self) -> List[str]:
        """Return skill names used in the last injection."""

        return list(self._last_used)

    def last_used_capabilities(self) -> List[str]:
        """Return runtime capability names used in the last injection."""

        return list(self._last_used_capabilities)

    def last_used_docs(self) -> List[str]:
        """Return COMSOL documentation source paths/URLs used in the last injection."""

        return list(self._last_used_docs)
