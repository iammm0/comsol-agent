from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


JSONDict = dict[str, Any]


@dataclass(frozen=True)
class TranscriptEntry:
    content: str
    kind: str = 'message'
    metadata: JSONDict = field(default_factory=dict)


@dataclass
class TranscriptStore:
    entries: list[TranscriptEntry] = field(default_factory=list)
    flushed: bool = False
    compaction_count: int = 0

    def __post_init__(self) -> None:
        normalized: list[TranscriptEntry] = []
        for entry in self.entries:
            if isinstance(entry, TranscriptEntry):
                normalized.append(entry)
            elif isinstance(entry, str):
                normalized.append(TranscriptEntry(content=entry))
        self.entries = normalized

    def append(
        self,
        entry: str,
        *,
        kind: str = 'message',
        metadata: JSONDict | None = None,
    ) -> None:
        self.entries.append(
            TranscriptEntry(
                content=entry,
                kind=kind,
                metadata=dict(metadata or {}),
            )
        )
        self.flushed = False

    def compact(self, keep_last: int = 10) -> None:
        if len(self.entries) <= keep_last:
            return
        trimmed = self.entries[:-keep_last]
        kept = self.entries[-keep_last:]
        self.compaction_count += 1
        summary_metadata = {
            'kind': 'compact_summary',
            'compaction_index': self.compaction_count,
            'compacted_entries': len(trimmed),
            'compacted_kinds': self._kind_counts(trimmed),
        }
        summary = TranscriptEntry(
            content=self._render_compaction_summary(trimmed, self.compaction_count),
            kind='compact_summary',
            metadata=summary_metadata,
        )
        self.entries[:] = [summary, *kept]

    def replay(self) -> tuple[str, ...]:
        return tuple(entry.content for entry in self.entries)

    def flush(self) -> None:
        self.flushed = True

    def summary_lines(self) -> list[str]:
        lines = [
            f'- Transcript entries: {len(self.entries)}',
            f'- Transcript compactions: {self.compaction_count}',
        ]
        kind_counts = self._kind_counts(self.entries)
        if kind_counts:
            lines.append(
                '- Transcript kinds: '
                + ', '.join(
                    f'{name}={count}' for name, count in sorted(kind_counts.items())
                )
            )
        return lines

    def structured_replay(self) -> tuple[JSONDict, ...]:
        return tuple(
            {
                'kind': entry.kind,
                'content': entry.content,
                'metadata': dict(entry.metadata),
            }
            for entry in self.entries
        )

    def _render_compaction_summary(
        self,
        trimmed: list[TranscriptEntry],
        compaction_index: int,
    ) -> str:
        lines = [
            f'[transcript-compaction {compaction_index}]',
            f'Compacted {len(trimmed)} older transcript entries.',
        ]
        kind_counts = self._kind_counts(trimmed)
        if kind_counts:
            lines.append(
                'Kinds: '
                + ', '.join(
                    f'{name}={count}' for name, count in sorted(kind_counts.items())
                )
            )
        previews: list[str] = []
        for entry in trimmed[-3:]:
            preview = ' '.join(entry.content.split())
            if len(preview) > 72:
                preview = preview[:69] + '...'
            previews.append(f'{entry.kind}: {preview or "(empty)"}')
        if previews:
            lines.append('Recent compacted previews:')
            lines.extend(f'- {preview}' for preview in previews)
        return '\n'.join(lines)

    @staticmethod
    def _kind_counts(entries: list[TranscriptEntry]) -> JSONDict:
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry.kind] = counts.get(entry.kind, 0) + 1
        return counts
