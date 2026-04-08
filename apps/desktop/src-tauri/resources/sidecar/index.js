import { randomUUID } from "node:crypto";
import readline from "node:readline";
import { cwd } from "node:process";
import { join } from "node:path";
import { AgentRuntime, createDefaultConfig } from "@mph-agent/agent-core";
import { bridgeRequestSchema, createRequest, createResponse } from "@mph-agent/contracts";
import { JavaSidecarClient } from "./java-sidecar-client.js";
function writeJsonLine(payload) {
    process.stdout.write(`${JSON.stringify(payload)}\n`);
}
function logError(message) {
    process.stderr.write(`[agent-sidecar] ${message}\n`);
}
function isRecord(value) {
    return typeof value === "object" && value !== null;
}
function toBridgeRequest(input) {
    if (isRecord(input)) {
        const maybeVersioned = bridgeRequestSchema.safeParse(input);
        if (maybeVersioned.success) {
            return maybeVersioned.data;
        }
    }
    const legacy = (isRecord(input) ? input : {});
    const cmd = String(legacy.cmd ?? "").trim();
    if (!cmd) {
        throw new Error("Missing command");
    }
    const request = createRequest({
        id: randomUUID(),
        cmd: cmd,
        payload: isRecord(legacy.payload) ? legacy.payload : {},
        conversationId: typeof legacy.conversation_id === "string" ? legacy.conversation_id : undefined
    });
    return request;
}
async function buildRuntime() {
    const workspaceRoot = process.env.MPH_AGENT_ROOT ?? cwd();
    const config = createDefaultConfig(workspaceRoot);
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
async function main() {
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
        let parsedInput;
        try {
            parsedInput = JSON.parse(trimmed);
        }
        catch (error) {
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
            writeJsonLine(response);
        }
        catch (error) {
            const failure = createResponse({
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
//# sourceMappingURL=index.js.map