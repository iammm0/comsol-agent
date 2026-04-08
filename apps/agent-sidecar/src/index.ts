import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import readline from "node:readline";
import { cwd } from "node:process";
import { join } from "node:path";
import { AgentRuntime, createDefaultConfig } from "@mph-agent/agent-core";
import {
  bridgeRequestSchema,
  createRequest,
  createResponse,
  type BridgeRequest,
  type BridgeResponse,
  type CommandPayload,
  type CommandKey
} from "@mph-agent/contracts";
import { JavaSidecarClient } from "./java-sidecar-client.js";

type LegacyRequestShape = {
  cmd?: string;
  payload?: Record<string, unknown>;
  conversation_id?: string;
};

interface SidecarRuntime {
  runtime: AgentRuntime;
  javaClient: JavaSidecarClient;
}

const CONFIG_KEYS = [
  "LLM_BACKEND",
  "DEEPSEEK_API_KEY",
  "DEEPSEEK_MODEL",
  "KIMI_API_KEY",
  "KIMI_MODEL",
  "OPENAI_COMPATIBLE_API_KEY",
  "OPENAI_COMPATIBLE_BASE_URL",
  "OPENAI_COMPATIBLE_MODEL",
  "OLLAMA_URL",
  "OLLAMA_MODEL",
  "COMSOL_HOME",
  "COMSOL_JAR_DIR",
  "COMSOL_JAR_PATH",
  "JAVA_HOME",
  "MPH_AGENT_ENABLE_COMSOL"
] as const;

type PersistedConfigMap = Partial<Record<(typeof CONFIG_KEYS)[number], string>>;

function writeJsonLine(payload: unknown): void {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

function logError(message: string): void {
  process.stderr.write(`[agent-sidecar] ${message}\n`);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function loadPersistedConfig(workspaceRoot: string): Promise<PersistedConfigMap> {
  const configPath = join(workspaceRoot, ".env.ts.json");
  try {
    const raw = await readFile(configPath, "utf8");
    const parsed = JSON.parse(raw) as unknown;
    if (!isRecord(parsed)) {
      return {};
    }
    const out: PersistedConfigMap = {};
    for (const key of CONFIG_KEYS) {
      const value = parsed[key];
      if (typeof value === "string") {
        out[key] = value;
      }
    }
    return out;
  } catch {
    return {};
  }
}

function applyPersistedConfig(config: PersistedConfigMap): void {
  for (const key of CONFIG_KEYS) {
    const value = config[key];
    if (typeof value === "string") {
      process.env[key] = value;
    }
  }

  // Rewrite-ts Java sidecar consumes COMSOL_JAR_DIR/COMSOL_HOME.
  if (!process.env.COMSOL_JAR_DIR && config.COMSOL_JAR_PATH) {
    process.env.COMSOL_JAR_DIR = config.COMSOL_JAR_PATH;
  }
}

function toBridgeRequest(input: unknown): BridgeRequest<CommandPayload> {
  if (isRecord(input)) {
    const maybeVersioned = bridgeRequestSchema.safeParse(input);
    if (maybeVersioned.success) {
      return maybeVersioned.data;
    }
  }

  const legacy = (isRecord(input) ? input : {}) as LegacyRequestShape;
  const cmd = String(legacy.cmd ?? "").trim();
  if (!cmd) {
    throw new Error("Missing command");
  }

  const request = createRequest({
    id: randomUUID(),
    cmd: cmd as CommandKey,
    payload: isRecord(legacy.payload) ? legacy.payload : {},
    conversationId:
      typeof legacy.conversation_id === "string" ? legacy.conversation_id : undefined
  });
  return request;
}

async function buildRuntime(): Promise<SidecarRuntime> {
  const workspaceRoot = process.env.MPH_AGENT_ROOT ?? cwd();
  const persistedConfig = await loadPersistedConfig(workspaceRoot);
  applyPersistedConfig(persistedConfig);

  const config = createDefaultConfig(workspaceRoot);
  if (
    persistedConfig.LLM_BACKEND === "ollama" ||
    persistedConfig.LLM_BACKEND === "deepseek" ||
    persistedConfig.LLM_BACKEND === "kimi" ||
    persistedConfig.LLM_BACKEND === "openai-compatible"
  ) {
    config.defaultBackend = persistedConfig.LLM_BACKEND;
  }
  if (persistedConfig.OLLAMA_MODEL) {
    config.defaultModel = persistedConfig.OLLAMA_MODEL;
  }
  if (persistedConfig.OLLAMA_URL) {
    config.defaultOllamaUrl = persistedConfig.OLLAMA_URL;
  }

  const resourceRoot = process.env.MPH_AGENT_RESOURCE_ROOT;
  if (resourceRoot) {
    config.paths.skillsRoot = join(resourceRoot, "skills");
    config.paths.promptsRoot = join(resourceRoot, "prompts");
  }

  const javaClient = new JavaSidecarClient(workspaceRoot);
  await javaClient.init();

  const runtime = new AgentRuntime({
    config,
    comsolExecutor: javaClient.createExecutor()
  });
  await runtime.init();
  return { runtime, javaClient };
}

async function reloadComsolClient(runtime: SidecarRuntime): Promise<void> {
  await runtime.javaClient.dispose();
  await runtime.javaClient.init();
}

function extractConfigUpdate(payload: CommandPayload): PersistedConfigMap {
  const rawConfig = payload.config;
  if (!isRecord(rawConfig)) {
    return {};
  }
  const out: PersistedConfigMap = {};
  for (const key of CONFIG_KEYS) {
    const value = rawConfig[key];
    if (typeof value === "string") {
      out[key] = value;
    }
  }
  return out;
}

async function main(): Promise<void> {
  const runtime = await buildRuntime();

  // Keep compatibility with existing Rust bootstrap flow.
  writeJsonLine({ _ready: true, ts: new Date().toISOString() });

  const lineReader = readline.createInterface({
    input: process.stdin,
    crlfDelay: Number.POSITIVE_INFINITY
  });

  for await (const line of lineReader) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }

    let parsedInput: unknown;
    try {
      parsedInput = JSON.parse(trimmed) as unknown;
    } catch (error) {
      const response = createResponse({
        id: randomUUID(),
        ok: false,
        message: "Invalid JSON",
        error: {
          code: "INVALID_JSON",
          message: error instanceof Error ? error.message : String(error)
        }
      });
      writeJsonLine(response);
      continue;
    }

    try {
      const request = toBridgeRequest(parsedInput);
      const response = await runtime.runtime.handle({
        request,
        emit: (event) => {
          writeJsonLine(event);
        }
      });

      if (request.cmd === "config_save" && response.ok) {
        const updates = extractConfigUpdate(request.payload);
        applyPersistedConfig(updates);
        try {
          await reloadComsolClient(runtime);
        } catch (error) {
          logError(
            `reload java sidecar after config save failed: ${
              error instanceof Error ? error.message : String(error)
            }`
          );
        }
      }

      writeJsonLine(response);
    } catch (error) {
      const failure: BridgeResponse<Record<string, unknown>> = createResponse({
        id: randomUUID(),
        ok: false,
        message: error instanceof Error ? error.message : "Unknown sidecar failure",
        error: {
          code: "SIDECAR_RUNTIME_ERROR",
          message: error instanceof Error ? error.message : String(error)
        }
      });
      writeJsonLine(failure);
    }
  }

  await runtime.javaClient.dispose();
}

main().catch((error) => {
  logError(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
