from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import parse, request


DEFAULT_SEARCH_STATE_DIR = Path('.port_sessions')
DEFAULT_SEARCH_STATE_FILE = DEFAULT_SEARCH_STATE_DIR / 'search_runtime.json'
SEARCH_MANIFEST_PATHS = (
    Path('.claw-search.json'),
    Path('.claude/search.json'),
)
DEFAULT_SEARXNG_BASE_URL = 'http://127.0.0.1:8080'
DEFAULT_BRAVE_BASE_URL = 'https://api.search.brave.com/res/v1/web/search'
DEFAULT_TAVILY_BASE_URL = 'https://api.tavily.com/search'


@dataclass(frozen=True)
class SearchProviderProfile:
    name: str
    provider: str
    source_manifest: str
    base_url: str
    api_key_env: str | None = None
    description: str | None = None
    default_max_results: int = 5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    provider_name: str
    rank: int


@dataclass(frozen=True)
class SearchStatusReport:
    configured: bool
    detail: str
    provider_name: str | None = None
    provider_kind: str | None = None
    base_url: str | None = None
    manifest_count: int = 0
    provider_count: int = 0
    api_key_env: str | None = None

    def as_text(self) -> str:
        lines = [
            f'configured={self.configured}',
            f'detail={self.detail}',
            f'manifest_count={self.manifest_count}',
            f'provider_count={self.provider_count}',
        ]
        if self.provider_name:
            lines.append(f'provider={self.provider_name}')
        if self.provider_kind:
            lines.append(f'provider_kind={self.provider_kind}')
        if self.base_url:
            lines.append(f'base_url={self.base_url}')
        if self.api_key_env:
            lines.append(f'api_key_env={self.api_key_env}')
        return '\n'.join(lines)


@dataclass
class SearchRuntime:
    cwd: Path
    providers: tuple[SearchProviderProfile, ...] = field(default_factory=tuple)
    manifests: tuple[str, ...] = field(default_factory=tuple)
    state_path: Path = field(default_factory=lambda: DEFAULT_SEARCH_STATE_FILE.resolve())
    active_provider_name: str | None = None

    @classmethod
    def from_workspace(
        cls,
        cwd: Path,
        additional_working_directories: tuple[str, ...] = (),
    ) -> 'SearchRuntime':
        manifest_paths = _discover_manifest_paths(cwd, additional_working_directories)
        providers: list[SearchProviderProfile] = []
        for manifest_path in manifest_paths:
            providers.extend(_load_profiles_from_manifest(manifest_path))
        providers.extend(_load_profiles_from_env())
        providers = _dedupe_profiles(providers)
        state_path = (cwd.resolve() / DEFAULT_SEARCH_STATE_FILE).resolve()
        payload = _load_state_payload(state_path)
        active_provider_name = payload.get('active_provider_name')
        if not isinstance(active_provider_name, str):
            active_provider_name = None
        return cls(
            cwd=cwd.resolve(),
            providers=tuple(providers),
            manifests=tuple(str(path) for path in manifest_paths),
            state_path=state_path,
            active_provider_name=active_provider_name,
        )

    def has_search_runtime(self) -> bool:
        return bool(self.providers)

    def list_providers(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
    ) -> tuple[SearchProviderProfile, ...]:
        providers = self.providers
        if query:
            needle = query.lower()
            providers = tuple(
                provider
                for provider in providers
                if needle in provider.name.lower()
                or needle in provider.provider.lower()
                or needle in provider.base_url.lower()
                or needle in (provider.description or '').lower()
            )
        if limit is not None and limit >= 0:
            providers = providers[:limit]
        return providers

    def get_provider(self, name: str) -> SearchProviderProfile | None:
        needle = name.strip().lower()
        if not needle:
            return None
        for provider in self.providers:
            if provider.name.lower() == needle:
                return provider
        return None

    def current_provider(self) -> SearchProviderProfile | None:
        if self.active_provider_name:
            active = self.get_provider(self.active_provider_name)
            if active is not None:
                return active
        env_default = os.environ.get('CLAW_SEARCH_PROVIDER')
        if isinstance(env_default, str) and env_default.strip():
            active = self.get_provider(env_default.strip())
            if active is not None:
                return active
        return self.providers[0] if self.providers else None

    def activate_provider(self, name: str) -> SearchStatusReport:
        provider = self.get_provider(name)
        if provider is None:
            raise KeyError(name)
        self.active_provider_name = provider.name
        self._persist_state()
        return SearchStatusReport(
            configured=True,
            detail=f'Activated search provider {provider.name}',
            provider_name=provider.name,
            provider_kind=provider.provider,
            base_url=provider.base_url,
            manifest_count=len(self.manifests),
            provider_count=len(self.providers),
            api_key_env=provider.api_key_env,
        )

    def render_summary(self) -> str:
        lines = [
            f'Local search manifests: {len(self.manifests)}',
            f'Configured search providers: {len(self.providers)}',
        ]
        current = self.current_provider()
        if current is None:
            lines.append('- Active search provider: none')
            return '\n'.join(lines)
        lines.append(f'- Active search provider: {current.name} ({current.provider})')
        for provider in self.providers[:5]:
            details = [provider.name, provider.provider, provider.base_url]
            if provider.api_key_env:
                details.append(f'api_key_env={provider.api_key_env}')
            lines.append('- Provider: ' + ' ; '.join(details))
        return '\n'.join(lines)

    def render_providers_index(self, *, query: str | None = None) -> str:
        providers = self.list_providers(query=query, limit=100)
        lines = ['# Search Providers', '']
        if not providers:
            lines.append('No local search providers discovered.')
            return '\n'.join(lines)
        for provider in providers:
            details = [provider.name, provider.provider, provider.base_url]
            if provider.api_key_env:
                details.append(f'api_key_env={provider.api_key_env}')
            lines.append('- ' + ' ; '.join(details))
        return '\n'.join(lines)

    def render_provider(self, name: str) -> str:
        provider = self.get_provider(name)
        if provider is None:
            return f'# Search Provider\n\nUnknown search provider: {name}'
        lines = [
            '# Search Provider',
            '',
            f'- Name: {provider.name}',
            f'- Provider: {provider.provider}',
            f'- Base URL: {provider.base_url}',
            f'- Source manifest: {provider.source_manifest}',
        ]
        if provider.api_key_env:
            lines.append(f'- API key env: {provider.api_key_env}')
        if provider.description:
            lines.extend(['', provider.description])
        return '\n'.join(lines)

    def render_search_results(
        self,
        query: str,
        *,
        provider_name: str | None = None,
        max_results: int = 5,
        domains: tuple[str, ...] = (),
        timeout_seconds: float = 20.0,
    ) -> str:
        provider, results = self.search(
            query,
            provider_name=provider_name,
            max_results=max_results,
            domains=domains,
            timeout_seconds=timeout_seconds,
        )
        lines = ['# Web Search', '']
        lines.append(f'- Provider: {provider.name} ({provider.provider})')
        lines.append(f'- Query: {query}')
        lines.append(f'- Results: {len(results)}')
        lines.append('')
        if not results:
            lines.append('No search results.')
            return '\n'.join(lines)
        for result in results:
            lines.append(f'{result.rank}. {result.title}')
            lines.append(f'   {result.url}')
            if result.snippet:
                lines.append(f'   {result.snippet}')
        return '\n'.join(lines)

    def search(
        self,
        query: str,
        *,
        provider_name: str | None = None,
        max_results: int = 5,
        domains: tuple[str, ...] = (),
        timeout_seconds: float = 20.0,
    ) -> tuple[SearchProviderProfile, tuple[SearchResult, ...]]:
        provider = self._resolve_provider(provider_name)
        backend = provider.provider.lower()
        if backend == 'searxng':
            results = _search_searxng(provider, query, max_results=max_results, timeout_seconds=timeout_seconds)
        elif backend == 'brave':
            results = _search_brave(provider, query, max_results=max_results, timeout_seconds=timeout_seconds)
        elif backend == 'tavily':
            results = _search_tavily(provider, query, max_results=max_results, domains=domains, timeout_seconds=timeout_seconds)
        else:
            raise ValueError(f'Unsupported search provider: {provider.provider}')
        if domains:
            results = tuple(result for result in results if _matches_domains(result.url, domains))
        return provider, tuple(results[:max_results])

    def _resolve_provider(self, provider_name: str | None) -> SearchProviderProfile:
        if provider_name:
            provider = self.get_provider(provider_name)
            if provider is None:
                raise KeyError(provider_name)
            return provider
        provider = self.current_provider()
        if provider is None:
            raise LookupError('No local search provider is configured.')
        return provider

    def _persist_state(self) -> None:
        payload = {'active_provider_name': self.active_provider_name}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )


def _discover_manifest_paths(cwd: Path, additional_working_directories: tuple[str, ...]) -> tuple[Path, ...]:
    candidate_roots = [cwd.resolve()]
    for raw_path in additional_working_directories:
        path = Path(raw_path).resolve()
        if path not in candidate_roots:
            candidate_roots.append(path)
    discovered: list[Path] = []
    seen: set[Path] = set()
    for root in candidate_roots:
        for relative_path in SEARCH_MANIFEST_PATHS:
            path = (root / relative_path).resolve()
            if path in seen or not path.exists() or not path.is_file():
                continue
            seen.add(path)
            discovered.append(path)
    return tuple(discovered)


def _load_profiles_from_manifest(path: Path) -> list[SearchProviderProfile]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict):
        providers_payload = payload.get('providers')
        if isinstance(providers_payload, list):
            return [
                provider
                for item in providers_payload
                for provider in [_provider_from_payload(item, path)]
                if provider is not None
            ]
        single = _provider_from_payload(payload, path)
        return [single] if single is not None else []
    return []


def _provider_from_payload(payload: Any, path: Path) -> SearchProviderProfile | None:
    if not isinstance(payload, dict):
        return None
    name = payload.get('name')
    provider = payload.get('provider')
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(provider, str) or not provider.strip():
        return None
    normalized_provider = provider.strip().lower()
    base_url = _optional_str(payload.get('baseUrl') or payload.get('base_url')) or _default_base_url(normalized_provider)
    if base_url is None:
        return None
    api_key_env = _optional_str(payload.get('apiKeyEnv') or payload.get('api_key_env')) or _default_api_env(normalized_provider)
    description = _optional_str(payload.get('description'))
    default_max_results = payload.get('defaultMaxResults') or payload.get('default_max_results') or 5
    if isinstance(default_max_results, bool) or not isinstance(default_max_results, int):
        default_max_results = 5
    metadata = payload.get('metadata')
    return SearchProviderProfile(
        name=name.strip(),
        provider=normalized_provider,
        source_manifest=str(path),
        base_url=base_url,
        api_key_env=api_key_env,
        description=description,
        default_max_results=max(default_max_results, 1),
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def _load_profiles_from_env() -> list[SearchProviderProfile]:
    providers: list[SearchProviderProfile] = []
    searxng_base = os.environ.get('SEARXNG_BASE_URL')
    if isinstance(searxng_base, str) and searxng_base.strip():
        providers.append(
            SearchProviderProfile(
                name='searxng',
                provider='searxng',
                source_manifest='env:SEARXNG_BASE_URL',
                base_url=searxng_base.strip(),
            )
        )
    brave_key = os.environ.get('BRAVE_SEARCH_API_KEY')
    if isinstance(brave_key, str) and brave_key.strip():
        providers.append(
            SearchProviderProfile(
                name='brave',
                provider='brave',
                source_manifest='env:BRAVE_SEARCH_API_KEY',
                base_url=DEFAULT_BRAVE_BASE_URL,
                api_key_env='BRAVE_SEARCH_API_KEY',
            )
        )
    tavily_key = os.environ.get('TAVILY_API_KEY')
    if isinstance(tavily_key, str) and tavily_key.strip():
        providers.append(
            SearchProviderProfile(
                name='tavily',
                provider='tavily',
                source_manifest='env:TAVILY_API_KEY',
                base_url=DEFAULT_TAVILY_BASE_URL,
                api_key_env='TAVILY_API_KEY',
            )
        )
    return providers


def _dedupe_profiles(providers: list[SearchProviderProfile]) -> list[SearchProviderProfile]:
    seen: set[str] = set()
    deduped: list[SearchProviderProfile] = []
    for provider in providers:
        key = provider.name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(provider)
    return deduped


def _load_state_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _default_base_url(provider: str) -> str | None:
    if provider == 'searxng':
        return DEFAULT_SEARXNG_BASE_URL
    if provider == 'brave':
        return DEFAULT_BRAVE_BASE_URL
    if provider == 'tavily':
        return DEFAULT_TAVILY_BASE_URL
    return None


def _default_api_env(provider: str) -> str | None:
    if provider == 'brave':
        return 'BRAVE_SEARCH_API_KEY'
    if provider == 'tavily':
        return 'TAVILY_API_KEY'
    return None


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _search_searxng(
    provider: SearchProviderProfile,
    query: str,
    *,
    max_results: int,
    timeout_seconds: float,
) -> tuple[SearchResult, ...]:
    endpoint = provider.base_url.rstrip('/')
    if not endpoint.endswith('/search'):
        endpoint += '/search'
    url = endpoint + '?' + parse.urlencode(
        {
            'q': query,
            'format': 'json',
        }
    )
    req = request.Request(url, headers={'User-Agent': 'claw-code-agent/1.0'})
    with request.urlopen(req, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode('utf-8', errors='replace'))
    results = payload.get('results')
    if not isinstance(results, list):
        return ()
    rendered: list[SearchResult] = []
    for index, item in enumerate(results[:max_results], start=1):
        if not isinstance(item, dict):
            continue
        url_value = item.get('url')
        title = item.get('title')
        snippet = item.get('content') or item.get('snippet') or ''
        if not isinstance(url_value, str) or not url_value.strip():
            continue
        if not isinstance(title, str) or not title.strip():
            title = url_value
        rendered.append(
            SearchResult(
                title=title.strip(),
                url=url_value.strip(),
                snippet=str(snippet).strip(),
                provider_name=provider.name,
                rank=index,
            )
        )
    return tuple(rendered)


def _search_brave(
    provider: SearchProviderProfile,
    query: str,
    *,
    max_results: int,
    timeout_seconds: float,
) -> tuple[SearchResult, ...]:
    api_key = _require_api_key(provider)
    url = provider.base_url + '?' + parse.urlencode({'q': query, 'count': max_results})
    req = request.Request(
        url,
        headers={
            'User-Agent': 'claw-code-agent/1.0',
            'X-Subscription-Token': api_key,
            'Accept': 'application/json',
        },
    )
    with request.urlopen(req, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode('utf-8', errors='replace'))
    results = payload.get('web', {}).get('results')
    if not isinstance(results, list):
        return ()
    rendered: list[SearchResult] = []
    for index, item in enumerate(results[:max_results], start=1):
        if not isinstance(item, dict):
            continue
        url_value = item.get('url')
        title = item.get('title')
        snippet = item.get('description') or ''
        if not isinstance(url_value, str) or not url_value.strip():
            continue
        if not isinstance(title, str) or not title.strip():
            title = url_value
        rendered.append(
            SearchResult(
                title=title.strip(),
                url=url_value.strip(),
                snippet=str(snippet).strip(),
                provider_name=provider.name,
                rank=index,
            )
        )
    return tuple(rendered)


def _search_tavily(
    provider: SearchProviderProfile,
    query: str,
    *,
    max_results: int,
    domains: tuple[str, ...],
    timeout_seconds: float,
) -> tuple[SearchResult, ...]:
    api_key = _require_api_key(provider)
    payload = {
        'api_key': api_key,
        'query': query,
        'max_results': max_results,
    }
    if domains:
        payload['include_domains'] = list(domains)
    data = json.dumps(payload, ensure_ascii=True).encode('utf-8')
    req = request.Request(
        provider.base_url,
        data=data,
        headers={
            'User-Agent': 'claw-code-agent/1.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )
    with request.urlopen(req, timeout=timeout_seconds) as response:
        body = json.loads(response.read().decode('utf-8', errors='replace'))
    results = body.get('results')
    if not isinstance(results, list):
        return ()
    rendered: list[SearchResult] = []
    for index, item in enumerate(results[:max_results], start=1):
        if not isinstance(item, dict):
            continue
        url_value = item.get('url')
        title = item.get('title')
        snippet = item.get('content') or ''
        if not isinstance(url_value, str) or not url_value.strip():
            continue
        if not isinstance(title, str) or not title.strip():
            title = url_value
        rendered.append(
            SearchResult(
                title=title.strip(),
                url=url_value.strip(),
                snippet=str(snippet).strip(),
                provider_name=provider.name,
                rank=index,
            )
        )
    return tuple(rendered)


def _require_api_key(provider: SearchProviderProfile) -> str:
    if provider.api_key_env is None:
        raise LookupError(f'Search provider {provider.name} does not define an API key env var.')
    value = os.environ.get(provider.api_key_env)
    if not isinstance(value, str) or not value.strip():
        raise LookupError(
            f'Search provider {provider.name} requires env var {provider.api_key_env}.'
        )
    return value.strip()


def _matches_domains(url: str, domains: tuple[str, ...]) -> bool:
    hostname = parse.urlparse(url).hostname or ''
    hostname = hostname.lower()
    for domain in domains:
        normalized = domain.strip().lower()
        if not normalized:
            continue
        if hostname == normalized or hostname.endswith('.' + normalized):
            return True
    return False
