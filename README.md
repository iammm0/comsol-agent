# mph-agent (rewrite-ts)

Pure TypeScript rewrite of mph-agent on branch `rewrite-ts`.

## Stack

- Desktop: Tauri 2 + SolidJS + TypeScript
- Agent runtime: Node.js TypeScript sidecar
- COMSOL bridge: Java JSON-RPC sidecar (Node-orchestrated)
- Contracts: Zod-based shared protocol package

## Workspace Layout

```txt
apps/
  desktop/               # SolidJS + Tauri desktop app
  agent-sidecar/         # stdin/stdout command runtime
  comsol-java-sidecar/   # Java JSON-RPC sidecar
packages/
  contracts/             # versioned request/response/event schemas
  agent-core/            # ReAct/planner/context/skills command handlers
```

## Quick Start

```bash
npm install
npm run build -w @mph-agent/contracts
npm run build -w @mph-agent/agent-core
npm run build -w @mph-agent/agent-sidecar
npm run dev:desktop
```

## Packaging Runtime Assets

Before desktop bundle, prepare sidecar/runtime resources:

```bash
npm run prepare:runtime -w @mph-agent/desktop
```

This copies:
- TS agent sidecar bundle to `apps/desktop/src-tauri/resources/sidecar`
- Skills and prompts to `apps/desktop/src-tauri/resources/{skills,prompts}`
- Java sidecar jar if available to `apps/desktop/src-tauri/resources/sidecar/java`

Java sidecar jar is expected at:
- `apps/comsol-java-sidecar/build/libs/comsol-java-sidecar-all.jar`

Build it with Gradle/Gradle wrapper first when enabling non-mock COMSOL execution.

When local network cannot reach Gradle distribution host, you can skip Java build and keep mock fallback:

```bash
MPH_AGENT_SKIP_JAVA_BUILD=1 npm run prepare:runtime -w @mph-agent/desktop
```

## Runtime Protocol

- Request envelope:
  - `BridgeRequest<TPayload> = { version, id, cmd, payload, conversationId, ts }`
- Response envelope:
  - `BridgeResponse<TData> = { version, id, ok, message, data?, error?, ts }`
- Event envelope:
  - `BridgeEvent<TType, TData> = { version, _event: true, runId, type, ts, iteration?, data }`

## Notes

- Legacy Python runtime code has been removed from this branch; desktop runtime now uses the TypeScript sidecar only.
- COMSOL Java sidecar now includes a reflective runtime bridge for `ModelUtil.create/save` when COMSOL jars are configured (`MPH_AGENT_ENABLE_COMSOL=1` + `COMSOL_HOME`/`COMSOL_JAR_DIR`), with automatic mock fallback on failure.
- On first startup, legacy `.context` conversation data is automatically imported into `.context-ts` (one-time migration marker: `.context-ts/.migration-v1.json`).
- CI matrix checks TypeScript and Tauri Rust build health on Windows/macOS/Linux.
- Release checklist: `docs/rewrite-ts-release-checklist.md`.
