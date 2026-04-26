from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


LSP_MANIFEST_FILES = (
    Path('.claw-lsp.json'),
    Path('.claude/lsp.json'),
)
DEFAULT_SUPPORTED_EXTENSIONS = (
    '.py',
    '.pyi',
    '.js',
    '.jsx',
    '.ts',
    '.tsx',
    '.json',
)
DEFAULT_IGNORED_DIRECTORIES = (
    '.git',
    '.hg',
    '.svn',
    '.port_sessions',
    '__pycache__',
    'node_modules',
    'dist',
    'build',
    '.venv',
    'venv',
)
DEFAULT_MAX_INDEXED_FILES = 500
DEFAULT_MAX_FILE_BYTES = 1_500_000
WORD_PATTERN = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


@dataclass(frozen=True)
class LSPSymbol:
    name: str
    kind: str
    path: str
    line: int
    character: int
    end_line: int
    end_character: int
    container_name: str | None = None
    signature: str | None = None
    documentation: str | None = None

    @property
    def symbol_id(self) -> str:
        return f'{self.path}:{self.line}:{self.character}:{self.kind}:{self.name}'

    def contains(self, line: int, character: int) -> bool:
        if line < self.line or line > self.end_line:
            return False
        if line == self.line and character < self.character:
            return False
        if line == self.end_line and character > self.end_character:
            return False
        return True


@dataclass(frozen=True)
class LSPReference:
    name: str
    path: str
    line: int
    character: int
    line_text: str


@dataclass(frozen=True)
class LSPDiagnostic:
    path: str
    severity: str
    message: str
    line: int
    character: int
    code: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class LSPCallEdge:
    caller_symbol_id: str
    caller_name: str
    callee_name: str
    path: str
    line: int
    character: int


@dataclass(frozen=True)
class IndexedFile:
    path: Path
    language: str
    text: str
    symbols: tuple[LSPSymbol, ...] = ()
    diagnostics: tuple[LSPDiagnostic, ...] = ()
    call_edges: tuple[LSPCallEdge, ...] = ()


@dataclass(frozen=True)
class LSPQueryResult:
    operation: str
    content: str
    result_count: int = 0
    file_count: int = 0
    symbol_name: str | None = None


@dataclass
class LSPRuntime:
    cwd: Path
    additional_working_directories: tuple[Path, ...] = ()
    manifests: tuple[str, ...] = ()
    supported_extensions: tuple[str, ...] = DEFAULT_SUPPORTED_EXTENSIONS
    ignored_directories: tuple[str, ...] = DEFAULT_IGNORED_DIRECTORIES
    max_indexed_files: int = DEFAULT_MAX_INDEXED_FILES
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    _cache: dict[str, tuple[int, int, IndexedFile]] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_workspace(
        cls,
        cwd: Path,
        additional_working_directories: tuple[str, ...] = (),
    ) -> 'LSPRuntime':
        resolved_cwd = cwd.resolve()
        resolved_dirs = tuple(Path(path).resolve() for path in additional_working_directories)
        manifest_paths = _discover_manifest_paths(resolved_cwd, resolved_dirs)
        supported_extensions = set(DEFAULT_SUPPORTED_EXTENSIONS)
        ignored_directories = set(DEFAULT_IGNORED_DIRECTORIES)
        max_indexed_files = DEFAULT_MAX_INDEXED_FILES
        max_file_bytes = DEFAULT_MAX_FILE_BYTES
        for manifest_path in manifest_paths:
            payload = _load_manifest_payload(manifest_path)
            raw_extensions = payload.get('includeExtensions')
            if isinstance(raw_extensions, list):
                supported_extensions.update(
                    extension
                    for extension in raw_extensions
                    if isinstance(extension, str) and extension.strip()
                )
            raw_ignored = payload.get('excludeDirs')
            if isinstance(raw_ignored, list):
                ignored_directories.update(
                    item
                    for item in raw_ignored
                    if isinstance(item, str) and item.strip()
                )
            raw_max_files = payload.get('maxIndexedFiles')
            if isinstance(raw_max_files, int) and raw_max_files > 0:
                max_indexed_files = raw_max_files
            raw_max_bytes = payload.get('maxFileBytes')
            if isinstance(raw_max_bytes, int) and raw_max_bytes > 0:
                max_file_bytes = raw_max_bytes
        return cls(
            cwd=resolved_cwd,
            additional_working_directories=resolved_dirs,
            manifests=tuple(str(path) for path in manifest_paths),
            supported_extensions=tuple(sorted(supported_extensions)),
            ignored_directories=tuple(sorted(ignored_directories)),
            max_indexed_files=max_indexed_files,
            max_file_bytes=max_file_bytes,
        )

    def has_lsp_support(self) -> bool:
        return bool(self._workspace_files(limit=1))

    def render_summary(self) -> str:
        files = self._workspace_files(limit=self.max_indexed_files)
        language_counts: dict[str, int] = {}
        for path in files:
            language = _language_for_extension(path.suffix)
            language_counts[language] = language_counts.get(language, 0) + 1
        lines = [
            f'Heuristic LSP manifests: {len(self.manifests)}',
            f'LSP roots: {len(self._roots())}',
            f'Indexed candidate files: {len(files)}',
            f'Supported extensions: {", ".join(self.supported_extensions)}',
        ]
        if language_counts:
            lines.append('- Languages:')
            for language, count in sorted(language_counts.items()):
                lines.append(f'  - {language}: {count}')
        return '\n'.join(lines)

    def render_document_symbols(self, file_path: str) -> str:
        indexed = self._indexed_from_user_path(file_path)
        lines = ['# LSP Document Symbols', '', f'path={self._display_path(indexed.path)}']
        if not indexed.symbols:
            lines.extend(['', 'No document symbols found.'])
            return '\n'.join(lines)
        lines.append(f'symbol_count={len(indexed.symbols)}')
        lines.append('')
        for symbol in indexed.symbols:
            detail = f'{symbol.kind} {symbol.name} @ {self._display_path(Path(symbol.path))}:{symbol.line}:{symbol.character}'
            if symbol.container_name:
                detail += f' ; container={symbol.container_name}'
            lines.append(f'- {detail}')
        return '\n'.join(lines)

    def render_workspace_symbols(
        self,
        query: str,
        *,
        max_results: int = 50,
    ) -> str:
        results = self.workspace_symbols(query, max_results=max_results)
        lines = ['# LSP Workspace Symbols', '', f'query={query}', f'result_count={len(results)}', '']
        if not results:
            lines.append('No workspace symbols found.')
            return '\n'.join(lines)
        for symbol in results:
            lines.append(
                f'- {symbol.kind} {symbol.name} @ {self._display_path(Path(symbol.path))}:{symbol.line}:{symbol.character}'
            )
        return '\n'.join(lines)

    def render_definition(
        self,
        file_path: str,
        line: int,
        character: int,
        *,
        max_results: int = 20,
    ) -> str:
        indexed = self._indexed_from_user_path(file_path)
        symbol_name = self._symbol_name_at_position(indexed, line, character)
        definitions = self.go_to_definition(file_path, line, character, max_results=max_results)
        lines = ['# LSP Definition', '']
        if symbol_name:
            lines.append(f'symbol={symbol_name}')
        lines.append(f'result_count={len(definitions)}')
        lines.append('')
        if not definitions:
            lines.append('No definitions found.')
            return '\n'.join(lines)
        for symbol in definitions:
            lines.append(
                f'- {symbol.kind} {symbol.name} @ {self._display_path(Path(symbol.path))}:{symbol.line}:{symbol.character}'
            )
        return '\n'.join(lines)

    def render_references(
        self,
        file_path: str,
        line: int,
        character: int,
        *,
        max_results: int = 50,
    ) -> str:
        indexed = self._indexed_from_user_path(file_path)
        symbol_name = self._symbol_name_at_position(indexed, line, character)
        references = self.find_references(file_path, line, character, max_results=max_results)
        lines = ['# LSP References', '']
        if symbol_name:
            lines.append(f'symbol={symbol_name}')
        lines.append(f'result_count={len(references)}')
        lines.append(f'file_count={len({reference.path for reference in references})}')
        lines.append('')
        if not references:
            lines.append('No references found.')
            return '\n'.join(lines)
        for reference in references:
            lines.append(
                f'- {self._display_path(Path(reference.path))}:{reference.line}:{reference.character} :: {reference.line_text.strip()}'
            )
        return '\n'.join(lines)

    def render_hover(self, file_path: str, line: int, character: int) -> str:
        hover = self.hover(file_path, line, character)
        lines = ['# LSP Hover', '']
        if hover is None:
            lines.append('No hover information found.')
            return '\n'.join(lines)
        lines.append(f'symbol={hover.name}')
        lines.append(f'kind={hover.kind}')
        lines.append(
            f'location={self._display_path(Path(hover.path))}:{hover.line}:{hover.character}'
        )
        if hover.signature:
            lines.append(f'signature={hover.signature}')
        if hover.documentation:
            lines.extend(['', hover.documentation])
        return '\n'.join(lines)

    def render_prepare_call_hierarchy(self, file_path: str, line: int, character: int) -> str:
        symbol = self.prepare_call_hierarchy(file_path, line, character)
        lines = ['# LSP Call Hierarchy', '']
        if symbol is None:
            lines.append('No callable symbol found at that position.')
            return '\n'.join(lines)
        incoming = self.incoming_calls(file_path, line, character, max_results=100)
        outgoing = self.outgoing_calls(file_path, line, character, max_results=100)
        lines.append(f'symbol={symbol.name}')
        lines.append(f'kind={symbol.kind}')
        lines.append(
            f'location={self._display_path(Path(symbol.path))}:{symbol.line}:{symbol.character}'
        )
        lines.append(f'incoming_calls={len(incoming)}')
        lines.append(f'outgoing_calls={len(outgoing)}')
        return '\n'.join(lines)

    def render_incoming_calls(
        self,
        file_path: str,
        line: int,
        character: int,
        *,
        max_results: int = 50,
    ) -> str:
        symbol = self.prepare_call_hierarchy(file_path, line, character)
        calls = self.incoming_calls(file_path, line, character, max_results=max_results)
        lines = ['# LSP Incoming Calls', '']
        if symbol is not None:
            lines.append(f'symbol={symbol.name}')
        lines.append(f'result_count={len(calls)}')
        lines.append('')
        if not calls:
            lines.append('No incoming calls found.')
            return '\n'.join(lines)
        for call in calls:
            lines.append(
                f'- {call.name} @ {self._display_path(Path(call.path))}:{call.line}:{call.character}'
            )
        return '\n'.join(lines)

    def render_outgoing_calls(
        self,
        file_path: str,
        line: int,
        character: int,
        *,
        max_results: int = 50,
    ) -> str:
        symbol = self.prepare_call_hierarchy(file_path, line, character)
        calls = self.outgoing_calls(file_path, line, character, max_results=max_results)
        lines = ['# LSP Outgoing Calls', '']
        if symbol is not None:
            lines.append(f'symbol={symbol.name}')
        lines.append(f'result_count={len(calls)}')
        lines.append('')
        if not calls:
            lines.append('No outgoing calls found.')
            return '\n'.join(lines)
        for call in calls:
            lines.append(
                f'- {call.name} @ {self._display_path(Path(call.path))}:{call.line}:{call.character}'
            )
        return '\n'.join(lines)

    def render_diagnostics(self, file_path: str | None = None) -> str:
        diagnostics = self.diagnostics(file_path=file_path)
        lines = ['# LSP Diagnostics', '']
        if file_path is not None:
            lines.append(f'path={self._display_path(self.resolve_path(file_path))}')
        lines.append(f'diagnostic_count={len(diagnostics)}')
        lines.append('')
        if not diagnostics:
            lines.append('No diagnostics found.')
            return '\n'.join(lines)
        for diagnostic in diagnostics:
            code = f' [{diagnostic.code}]' if diagnostic.code else ''
            source = f' ({diagnostic.source})' if diagnostic.source else ''
            lines.append(
                f'- {diagnostic.severity.upper()} {self._display_path(Path(diagnostic.path))}:{diagnostic.line}:{diagnostic.character} {diagnostic.message}{code}{source}'
            )
        return '\n'.join(lines)

    def query(
        self,
        operation: str,
        *,
        file_path: str,
        line: int,
        character: int,
        query: str | None = None,
        max_results: int = 50,
    ) -> LSPQueryResult:
        if operation == 'documentSymbol':
            indexed = self._indexed_from_user_path(file_path)
            content = self.render_document_symbols(file_path)
            return LSPQueryResult(
                operation=operation,
                content=content,
                result_count=len(indexed.symbols),
                file_count=1 if indexed.symbols else 0,
            )
        if operation == 'workspaceSymbol':
            indexed = self._indexed_from_user_path(file_path)
            symbol_name = query or self._symbol_name_at_position(indexed, line, character)
            if not symbol_name:
                raise KeyError('No symbol name available for workspaceSymbol query')
            results = self.workspace_symbols(symbol_name, max_results=max_results)
            return LSPQueryResult(
                operation=operation,
                content=self.render_workspace_symbols(symbol_name, max_results=max_results),
                result_count=len(results),
                file_count=len({result.path for result in results}),
                symbol_name=symbol_name,
            )
        if operation == 'goToDefinition':
            definitions = self.go_to_definition(file_path, line, character, max_results=max_results)
            return LSPQueryResult(
                operation=operation,
                content=self.render_definition(file_path, line, character, max_results=max_results),
                result_count=len(definitions),
                file_count=len({definition.path for definition in definitions}),
                symbol_name=self._symbol_name_at_position(self._indexed_from_user_path(file_path), line, character),
            )
        if operation == 'findReferences':
            references = self.find_references(file_path, line, character, max_results=max_results)
            return LSPQueryResult(
                operation=operation,
                content=self.render_references(file_path, line, character, max_results=max_results),
                result_count=len(references),
                file_count=len({reference.path for reference in references}),
                symbol_name=self._symbol_name_at_position(self._indexed_from_user_path(file_path), line, character),
            )
        if operation == 'hover':
            hover = self.hover(file_path, line, character)
            return LSPQueryResult(
                operation=operation,
                content=self.render_hover(file_path, line, character),
                result_count=1 if hover is not None else 0,
                file_count=1 if hover is not None else 0,
                symbol_name=hover.name if hover is not None else None,
            )
        if operation == 'goToImplementation':
            definitions = self.go_to_definition(file_path, line, character, max_results=max_results)
            content = self.render_definition(file_path, line, character, max_results=max_results).replace(
                '# LSP Definition',
                '# LSP Implementation',
            )
            return LSPQueryResult(
                operation=operation,
                content=content,
                result_count=len(definitions),
                file_count=len({definition.path for definition in definitions}),
                symbol_name=self._symbol_name_at_position(self._indexed_from_user_path(file_path), line, character),
            )
        if operation == 'prepareCallHierarchy':
            symbol = self.prepare_call_hierarchy(file_path, line, character)
            return LSPQueryResult(
                operation=operation,
                content=self.render_prepare_call_hierarchy(file_path, line, character),
                result_count=1 if symbol is not None else 0,
                file_count=1 if symbol is not None else 0,
                symbol_name=symbol.name if symbol is not None else None,
            )
        if operation == 'incomingCalls':
            calls = self.incoming_calls(file_path, line, character, max_results=max_results)
            return LSPQueryResult(
                operation=operation,
                content=self.render_incoming_calls(file_path, line, character, max_results=max_results),
                result_count=len(calls),
                file_count=len({call.path for call in calls}),
                symbol_name=self._symbol_name_at_position(self._indexed_from_user_path(file_path), line, character),
            )
        if operation == 'outgoingCalls':
            calls = self.outgoing_calls(file_path, line, character, max_results=max_results)
            return LSPQueryResult(
                operation=operation,
                content=self.render_outgoing_calls(file_path, line, character, max_results=max_results),
                result_count=len(calls),
                file_count=len({call.path for call in calls}),
                symbol_name=self._symbol_name_at_position(self._indexed_from_user_path(file_path), line, character),
            )
        raise KeyError(operation)

    def workspace_symbols(self, query: str, *, max_results: int = 50) -> tuple[LSPSymbol, ...]:
        needle = query.strip().lower()
        if not needle:
            return ()
        results: list[LSPSymbol] = []
        for indexed in self._workspace_indexes():
            for symbol in indexed.symbols:
                if needle in symbol.name.lower():
                    results.append(symbol)
        results.sort(key=lambda item: (item.name.lower(), item.path, item.line, item.character))
        return tuple(results[:max_results])

    def go_to_definition(
        self,
        file_path: str,
        line: int,
        character: int,
        *,
        max_results: int = 20,
    ) -> tuple[LSPSymbol, ...]:
        indexed = self._indexed_from_user_path(file_path)
        symbol_name = self._symbol_name_at_position(indexed, line, character)
        if not symbol_name:
            return ()
        results: list[LSPSymbol] = []
        for candidate in self._workspace_indexes():
            for symbol in candidate.symbols:
                if symbol.name == symbol_name:
                    results.append(symbol)
        results.sort(
            key=lambda item: (
                0 if Path(item.path) == indexed.path else 1,
                abs(item.line - line),
                item.path,
                item.character,
            )
        )
        deduped: list[LSPSymbol] = []
        seen: set[str] = set()
        for symbol in results:
            if symbol.symbol_id in seen:
                continue
            seen.add(symbol.symbol_id)
            deduped.append(symbol)
        return tuple(deduped[:max_results])

    def find_references(
        self,
        file_path: str,
        line: int,
        character: int,
        *,
        max_results: int = 50,
    ) -> tuple[LSPReference, ...]:
        indexed = self._indexed_from_user_path(file_path)
        symbol_name = self._symbol_name_at_position(indexed, line, character)
        if not symbol_name:
            return ()
        references: list[LSPReference] = []
        pattern = re.compile(rf'\b{re.escape(symbol_name)}\b')
        for candidate in self._workspace_indexes():
            for line_number, line_text in enumerate(candidate.text.splitlines(), start=1):
                for match in pattern.finditer(line_text):
                    references.append(
                        LSPReference(
                            name=symbol_name,
                            path=str(candidate.path),
                            line=line_number,
                            character=match.start() + 1,
                            line_text=line_text,
                        )
                    )
                    if len(references) >= max_results:
                        return tuple(references)
        return tuple(references)

    def hover(self, file_path: str, line: int, character: int) -> LSPSymbol | None:
        indexed = self._indexed_from_user_path(file_path)
        for symbol in indexed.symbols:
            if symbol.contains(line, character):
                return symbol
        definitions = self.go_to_definition(file_path, line, character, max_results=1)
        return definitions[0] if definitions else None

    def prepare_call_hierarchy(
        self,
        file_path: str,
        line: int,
        character: int,
    ) -> LSPSymbol | None:
        indexed = self._indexed_from_user_path(file_path)
        callable_symbols = [
            symbol
            for symbol in indexed.symbols
            if symbol.kind in {'function', 'async_function', 'method'}
        ]
        containing = [
            symbol
            for symbol in callable_symbols
            if symbol.contains(line, character)
        ]
        if containing:
            containing.sort(key=lambda item: (item.end_line - item.line, item.end_character - item.character))
            return containing[0]
        definitions = self.go_to_definition(file_path, line, character, max_results=1)
        if definitions and definitions[0].kind in {'function', 'async_function', 'method'}:
            return definitions[0]
        return None

    def incoming_calls(
        self,
        file_path: str,
        line: int,
        character: int,
        *,
        max_results: int = 50,
    ) -> tuple[LSPSymbol, ...]:
        target = self.prepare_call_hierarchy(file_path, line, character)
        if target is None:
            return ()
        workspace_indexes = self._workspace_indexes()
        by_symbol_id = {
            symbol.symbol_id: symbol
            for indexed in workspace_indexes
            for symbol in indexed.symbols
        }
        results: list[LSPSymbol] = []
        seen: set[str] = set()
        for indexed in workspace_indexes:
            for edge in indexed.call_edges:
                if edge.callee_name != target.name:
                    continue
                caller = by_symbol_id.get(edge.caller_symbol_id)
                if caller is None or caller.symbol_id in seen:
                    continue
                seen.add(caller.symbol_id)
                results.append(caller)
                if len(results) >= max_results:
                    return tuple(results)
        return tuple(results)

    def outgoing_calls(
        self,
        file_path: str,
        line: int,
        character: int,
        *,
        max_results: int = 50,
    ) -> tuple[LSPSymbol, ...]:
        target = self.prepare_call_hierarchy(file_path, line, character)
        if target is None:
            return ()
        definitions_by_name: dict[str, list[LSPSymbol]] = {}
        for indexed in self._workspace_indexes():
            for symbol in indexed.symbols:
                definitions_by_name.setdefault(symbol.name, []).append(symbol)
        matches: list[LSPSymbol] = []
        seen: set[str] = set()
        for indexed in self._workspace_indexes():
            for edge in indexed.call_edges:
                if edge.caller_symbol_id != target.symbol_id:
                    continue
                for symbol in definitions_by_name.get(edge.callee_name, []):
                    if symbol.symbol_id in seen:
                        continue
                    seen.add(symbol.symbol_id)
                    matches.append(symbol)
                    if len(matches) >= max_results:
                        return tuple(matches)
        return tuple(matches)

    def diagnostics(self, *, file_path: str | None = None) -> tuple[LSPDiagnostic, ...]:
        if file_path is not None:
            indexed = self._indexed_from_user_path(file_path)
            return indexed.diagnostics
        diagnostics: list[LSPDiagnostic] = []
        for indexed in self._workspace_indexes():
            diagnostics.extend(indexed.diagnostics)
        diagnostics.sort(key=lambda item: (item.path, item.line, item.character))
        return tuple(diagnostics)

    def resolve_path(self, raw_path: str) -> Path:
        expanded = Path(raw_path).expanduser()
        candidate = expanded if expanded.is_absolute() else self.cwd / expanded
        resolved = candidate.resolve(strict=True)
        if not self._is_under_roots(resolved):
            raise ValueError(f'Path {raw_path!r} escapes the configured LSP roots')
        if not resolved.is_file():
            raise FileNotFoundError(raw_path)
        return resolved

    def _indexed_from_user_path(self, raw_path: str) -> IndexedFile:
        try:
            path = self.resolve_path(raw_path)
        except FileNotFoundError as exc:
            raise KeyError(f'Unknown file: {raw_path}') from exc
        except ValueError as exc:
            raise KeyError(str(exc)) from exc
        return self._index_file(path)

    def _display_path(self, path: Path) -> str:
        resolved = path.resolve()
        for root in self._roots():
            try:
                return str(resolved.relative_to(root))
            except ValueError:
                continue
        return str(resolved)

    def _roots(self) -> tuple[Path, ...]:
        roots = [self.cwd, *self.additional_working_directories]
        seen: set[Path] = set()
        normalized: list[Path] = []
        for root in roots:
            resolved = root.resolve()
            if resolved in seen or not resolved.exists():
                continue
            seen.add(resolved)
            normalized.append(resolved)
        return tuple(normalized)

    def _is_under_roots(self, path: Path) -> bool:
        for root in self._roots():
            try:
                path.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def _workspace_files(self, *, limit: int | None = None) -> tuple[Path, ...]:
        max_items = self.max_indexed_files if limit is None else min(limit, self.max_indexed_files)
        found: list[Path] = []
        seen: set[Path] = set()
        ignored = set(self.ignored_directories)
        supported = set(self.supported_extensions)
        for root in self._roots():
            for current_root, dir_names, file_names in os.walk(root):
                dir_names[:] = [
                    name
                    for name in dir_names
                    if name not in ignored and not name.startswith('.pytest_cache')
                ]
                current_path = Path(current_root)
                for name in sorted(file_names):
                    candidate = (current_path / name).resolve()
                    if candidate in seen or candidate.suffix not in supported:
                        continue
                    try:
                        size = candidate.stat().st_size
                    except OSError:
                        continue
                    if size > self.max_file_bytes:
                        continue
                    seen.add(candidate)
                    found.append(candidate)
                    if len(found) >= max_items:
                        return tuple(found)
        return tuple(found)

    def _workspace_indexes(self) -> tuple[IndexedFile, ...]:
        return tuple(self._index_file(path) for path in self._workspace_files())

    def _index_file(self, path: Path) -> IndexedFile:
        stat = path.stat()
        cache_key = str(path)
        cached = self._cache.get(cache_key)
        if cached is not None:
            cached_mtime, cached_size, indexed = cached
            if cached_mtime == stat.st_mtime_ns and cached_size == stat.st_size:
                return indexed
        text = path.read_text(encoding='utf-8', errors='replace')
        suffix = path.suffix.lower()
        if suffix in {'.py', '.pyi'}:
            indexed = _index_python_file(path, text)
        elif suffix == '.json':
            indexed = _index_json_file(path, text)
        else:
            indexed = _index_generic_code_file(path, text)
        self._cache[cache_key] = (stat.st_mtime_ns, stat.st_size, indexed)
        return indexed

    def _symbol_name_at_position(self, indexed: IndexedFile, line: int, character: int) -> str | None:
        word = _word_at(indexed.text, line, character)
        if word:
            return word
        for symbol in indexed.symbols:
            if symbol.contains(line, character):
                return symbol.name
        return None


def _discover_manifest_paths(cwd: Path, additional_dirs: tuple[Path, ...]) -> tuple[Path, ...]:
    directories = [cwd, *additional_dirs]
    seen: set[Path] = set()
    found: list[Path] = []
    for directory in directories:
        for filename in LSP_MANIFEST_FILES:
            candidate = (directory / filename).resolve()
            if candidate in seen or not candidate.exists():
                continue
            seen.add(candidate)
            found.append(candidate)
    return tuple(found)


def _load_manifest_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _index_python_file(path: Path, text: str) -> IndexedFile:
    diagnostics: list[LSPDiagnostic] = []
    symbols: list[LSPSymbol] = []
    call_edges: list[LSPCallEdge] = []
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        diagnostics.append(
            LSPDiagnostic(
                path=str(path),
                severity='error',
                message=exc.msg,
                line=exc.lineno or 1,
                character=(exc.offset or 1),
                code='syntax-error',
                source='python',
            )
        )
        fallback = _index_generic_code_file(path, text)
        return IndexedFile(
            path=path,
            language='python',
            text=text,
            symbols=fallback.symbols,
            diagnostics=tuple(diagnostics),
            call_edges=(),
        )

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.container_stack: list[LSPSymbol] = []
            self.callable_stack: list[LSPSymbol] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> Any:
            symbol = LSPSymbol(
                name=node.name,
                kind='class',
                path=str(path),
                line=node.lineno,
                character=node.col_offset + 1,
                end_line=getattr(node, 'end_lineno', node.lineno),
                end_character=getattr(node, 'end_col_offset', node.col_offset) + 1,
                container_name=self.container_stack[-1].name if self.container_stack else None,
                documentation=_first_doc_line(ast.get_docstring(node)),
            )
            symbols.append(symbol)
            self.container_stack.append(symbol)
            self.generic_visit(node)
            self.container_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
            kind = 'method' if self.container_stack and self.container_stack[-1].kind == 'class' else 'function'
            symbol = LSPSymbol(
                name=node.name,
                kind=kind,
                path=str(path),
                line=node.lineno,
                character=node.col_offset + 1,
                end_line=getattr(node, 'end_lineno', node.lineno),
                end_character=getattr(node, 'end_col_offset', node.col_offset) + 1,
                container_name=self.container_stack[-1].name if self.container_stack else None,
                signature=_python_signature(node),
                documentation=_first_doc_line(ast.get_docstring(node)),
            )
            symbols.append(symbol)
            self.container_stack.append(symbol)
            self.callable_stack.append(symbol)
            self.generic_visit(node)
            self.callable_stack.pop()
            self.container_stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
            kind = 'method' if self.container_stack and self.container_stack[-1].kind == 'class' else 'async_function'
            symbol = LSPSymbol(
                name=node.name,
                kind=kind,
                path=str(path),
                line=node.lineno,
                character=node.col_offset + 1,
                end_line=getattr(node, 'end_lineno', node.lineno),
                end_character=getattr(node, 'end_col_offset', node.col_offset) + 1,
                container_name=self.container_stack[-1].name if self.container_stack else None,
                signature='async ' + _python_signature(node),
                documentation=_first_doc_line(ast.get_docstring(node)),
            )
            symbols.append(symbol)
            self.container_stack.append(symbol)
            self.callable_stack.append(symbol)
            self.generic_visit(node)
            self.callable_stack.pop()
            self.container_stack.pop()

        def visit_Assign(self, node: ast.Assign) -> Any:
            if self.callable_stack:
                self.generic_visit(node)
                return
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.append(
                        LSPSymbol(
                            name=target.id,
                            kind='variable',
                            path=str(path),
                            line=target.lineno,
                            character=target.col_offset + 1,
                            end_line=getattr(target, 'end_lineno', target.lineno),
                            end_character=getattr(target, 'end_col_offset', target.col_offset) + 1,
                            container_name=self.container_stack[-1].name if self.container_stack else None,
                        )
                    )
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
            if self.callable_stack:
                self.generic_visit(node)
                return
            target = node.target
            if isinstance(target, ast.Name):
                symbols.append(
                    LSPSymbol(
                        name=target.id,
                        kind='variable',
                        path=str(path),
                        line=target.lineno,
                        character=target.col_offset + 1,
                        end_line=getattr(target, 'end_lineno', target.lineno),
                        end_character=getattr(target, 'end_col_offset', target.col_offset) + 1,
                        container_name=self.container_stack[-1].name if self.container_stack else None,
                    )
                )
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> Any:
            if self.callable_stack:
                callee_name = _python_called_name(node.func)
                if callee_name:
                    caller = self.callable_stack[-1]
                    call_edges.append(
                        LSPCallEdge(
                            caller_symbol_id=caller.symbol_id,
                            caller_name=caller.name,
                            callee_name=callee_name,
                            path=str(path),
                            line=getattr(node, 'lineno', caller.line),
                            character=getattr(node, 'col_offset', 0) + 1,
                        )
                    )
            self.generic_visit(node)

    Visitor().visit(tree)
    return IndexedFile(
        path=path,
        language='python',
        text=text,
        symbols=tuple(symbols),
        diagnostics=tuple(diagnostics),
        call_edges=tuple(call_edges),
    )


def _index_json_file(path: Path, text: str) -> IndexedFile:
    diagnostics: list[LSPDiagnostic] = []
    symbols: list[LSPSymbol] = []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        diagnostics.append(
            LSPDiagnostic(
                path=str(path),
                severity='error',
                message=exc.msg,
                line=exc.lineno,
                character=exc.colno,
                code='json-error',
                source='json',
            )
        )
        return IndexedFile(
            path=path,
            language='json',
            text=text,
            symbols=(),
            diagnostics=tuple(diagnostics),
            call_edges=(),
        )
    if isinstance(payload, dict):
        for key in payload.keys():
            line_number, character = _find_string_literal(text, key)
            if line_number is None or character is None:
                line_number, character = 1, 1
            symbols.append(
                LSPSymbol(
                    name=str(key),
                    kind='property',
                    path=str(path),
                    line=line_number,
                    character=character,
                    end_line=line_number,
                    end_character=character + len(str(key)),
                )
            )
    return IndexedFile(
        path=path,
        language='json',
        text=text,
        symbols=tuple(symbols),
        diagnostics=tuple(diagnostics),
        call_edges=(),
    )


def _index_generic_code_file(path: Path, text: str) -> IndexedFile:
    symbols: list[LSPSymbol] = []
    patterns = (
        ('class', re.compile(r'^\s*(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)')),
        ('function', re.compile(r'^\s*(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)')),
        ('function', re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_][A-Za-z0-9_]*)\s*=>')),
        ('variable', re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\b')),
        ('function', re.compile(r'^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\b')),
        ('class', re.compile(r'^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b')),
        ('interface', re.compile(r'^\s*(?:export\s+)?interface\s+([A-Za-z_][A-Za-z0-9_]*)')),
        ('type', re.compile(r'^\s*(?:export\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)')),
    )
    for line_number, line_text in enumerate(text.splitlines(), start=1):
        for kind, pattern in patterns:
            match = pattern.search(line_text)
            if match is None:
                continue
            name = match.group(1)
            symbols.append(
                LSPSymbol(
                    name=name,
                    kind=kind,
                    path=str(path),
                    line=line_number,
                    character=match.start(1) + 1,
                    end_line=line_number,
                    end_character=match.end(1) + 1,
                )
            )
            break
    return IndexedFile(
        path=path,
        language=_language_for_extension(path.suffix),
        text=text,
        symbols=tuple(symbols),
        diagnostics=(),
        call_edges=(),
    )


def _python_signature(node: ast.AST) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ''
    argument_names = [arg.arg for arg in node.args.args]
    if node.args.vararg is not None:
        argument_names.append('*' + node.args.vararg.arg)
    if node.args.kwarg is not None:
        argument_names.append('**' + node.args.kwarg.arg)
    return f'{node.name}({", ".join(argument_names)})'


def _python_called_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _word_at(text: str, line: int, character: int) -> str | None:
    lines = text.splitlines()
    if line < 1 or line > len(lines):
        return None
    line_text = lines[line - 1]
    if not line_text:
        return None
    position = max(0, min(len(line_text) - 1, character - 1))
    for match in WORD_PATTERN.finditer(line_text):
        if match.start() <= position < match.end():
            return match.group(0)
    if position > 0:
        for match in WORD_PATTERN.finditer(line_text):
            if match.start() < position <= match.end():
                return match.group(0)
    return None


def _find_string_literal(text: str, value: str) -> tuple[int | None, int | None]:
    quoted = json.dumps(value)
    needle = quoted[1:-1]
    for line_number, line_text in enumerate(text.splitlines(), start=1):
        column = line_text.find(f'"{needle}"')
        if column >= 0:
            return line_number, column + 2
    return None, None


def _first_doc_line(text: str | None) -> str | None:
    if not text:
        return None
    first = text.strip().splitlines()[0].strip()
    return first or None


def _language_for_extension(extension: str) -> str:
    lowered = extension.lower()
    if lowered in {'.py', '.pyi'}:
        return 'python'
    if lowered in {'.js', '.jsx'}:
        return 'javascript'
    if lowered in {'.ts', '.tsx'}:
        return 'typescript'
    if lowered == '.json':
        return 'json'
    return lowered.lstrip('.') or 'text'
