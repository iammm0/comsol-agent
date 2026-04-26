"""GUI entry point: ``python -m src.gui [--port N] [--cwd PATH] ...``."""

from __future__ import annotations

import argparse
import json
import os
import webbrowser
from pathlib import Path

import uvicorn

from ..session_store import DEFAULT_AGENT_SESSION_DIR
from .server import AgentState, create_app


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='claw-code-gui',
        description='Launch the local web GUI for the claw-code agent.',
    )
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument(
        '--cwd',
        default='.',
        help='Working directory that the agent operates in (default: current dir).',
    )
    parser.add_argument(
        '--model',
        default=os.environ.get('OPENAI_MODEL', 'Qwen/Qwen3-Coder-30B-A3B-Instruct'),
    )
    parser.add_argument(
        '--base-url',
        default=os.environ.get('OPENAI_BASE_URL', 'http://127.0.0.1:8000/v1'),
    )
    parser.add_argument(
        '--api-key',
        default=os.environ.get('OPENAI_API_KEY', 'local-token'),
    )
    parser.add_argument(
        '--session-dir',
        default=str(DEFAULT_AGENT_SESSION_DIR),
        help='Directory where agent sessions are saved (default: .port_sessions/agent).',
    )
    parser.add_argument('--allow-shell', action='store_true')
    parser.add_argument('--allow-write', action='store_true')
    parser.add_argument('--temperature', type=float, default=0.0)
    parser.add_argument('--timeout-seconds', type=float, default=120.0)
    parser.add_argument('--stream', action='store_true', dest='stream_model_responses')
    parser.add_argument('--max-turns', type=int, default=12)
    parser.add_argument('--max-total-tokens', type=int, default=None)
    parser.add_argument('--max-input-tokens', type=int, default=None)
    parser.add_argument('--max-output-tokens', type=int, default=None)
    parser.add_argument('--max-reasoning-tokens', type=int, default=None)
    parser.add_argument('--max-budget-usd', type=float, default=None, dest='max_total_cost_usd')
    parser.add_argument('--max-tool-calls', type=int, default=None)
    parser.add_argument('--max-delegated-tasks', type=int, default=None)
    parser.add_argument('--max-model-calls', type=int, default=None)
    parser.add_argument('--max-session-turns', type=int, default=None)
    parser.add_argument('--system-prompt', default=None, dest='custom_system_prompt')
    parser.add_argument('--append-system-prompt', default=None)
    parser.add_argument('--override-system-prompt', default=None)
    parser.add_argument(
        '--response-schema-file',
        default=None,
        help='Path to a JSON file describing the structured-output schema.',
    )
    parser.add_argument('--response-schema-name', default='response')
    parser.add_argument('--response-schema-strict', action='store_true')
    parser.add_argument('--auto-snip-threshold', type=int, default=None, dest='auto_snip_threshold_tokens')
    parser.add_argument('--auto-compact-threshold', type=int, default=None, dest='auto_compact_threshold_tokens')
    parser.add_argument('--compact-preserve-messages', type=int, default=4)
    parser.add_argument('--disable-claude-md', action='store_true', dest='disable_claude_md_discovery')
    parser.add_argument(
        '--add-dir',
        action='append',
        default=[],
        dest='additional_working_directories',
        help='Additional working directory the agent may operate in (repeatable).',
    )
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not auto-open a browser tab on launch.',
    )

    args = parser.parse_args()

    response_schema = None
    if args.response_schema_file:
        with open(args.response_schema_file, encoding='utf-8') as fh:
            response_schema = json.load(fh)

    state = AgentState(
        cwd=Path(args.cwd),
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        allow_shell=args.allow_shell,
        allow_write=args.allow_write,
        session_directory=Path(args.session_dir),
        temperature=args.temperature,
        timeout_seconds=args.timeout_seconds,
        stream_model_responses=args.stream_model_responses,
        max_turns=args.max_turns,
        max_total_tokens=args.max_total_tokens,
        max_input_tokens=args.max_input_tokens,
        max_output_tokens=args.max_output_tokens,
        max_reasoning_tokens=args.max_reasoning_tokens,
        max_total_cost_usd=args.max_total_cost_usd,
        max_tool_calls=args.max_tool_calls,
        max_delegated_tasks=args.max_delegated_tasks,
        max_model_calls=args.max_model_calls,
        max_session_turns=args.max_session_turns,
        custom_system_prompt=args.custom_system_prompt,
        append_system_prompt=args.append_system_prompt,
        override_system_prompt=args.override_system_prompt,
        response_schema=response_schema,
        response_schema_name=args.response_schema_name,
        response_schema_strict=args.response_schema_strict,
        auto_snip_threshold_tokens=args.auto_snip_threshold_tokens,
        auto_compact_threshold_tokens=args.auto_compact_threshold_tokens,
        compact_preserve_messages=args.compact_preserve_messages,
        disable_claude_md_discovery=args.disable_claude_md_discovery,
        additional_working_directories=tuple(
            Path(p).expanduser().resolve() for p in args.additional_working_directories
        ),
    )
    app = create_app(state)

    url = f'http://{args.host}:{args.port}'
    print(f'Claw Code GUI listening on {url}')
    print(f'  cwd       : {state.cwd}')
    print(f'  model     : {state.model}')
    print(f'  base-url  : {state.base_url}')
    print(f'  sessions  : {state.session_directory}')
    print(f'  shell     : {"on" if state.allow_shell else "off"}')
    print(f'  write     : {"on" if state.allow_write else "off"}')

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run(app, host=args.host, port=args.port, log_level='info')


if __name__ == '__main__':
    main()
