import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
function isRecord(value) {
    return typeof value === "object" && value !== null;
}
const TINY_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn6mSgAAAAASUVORK5CYII=";
export class JavaSidecarClient {
    child = null;
    pending = new Map();
    workspaceRoot;
    resourceRoot;
    timeoutMs;
    mockMode;
    ready = false;
    constructor(workspaceRoot, timeoutMs = 60_000) {
        this.workspaceRoot = workspaceRoot;
        this.resourceRoot = process.env.MPH_AGENT_RESOURCE_ROOT ?? null;
        this.timeoutMs = timeoutMs;
        this.mockMode = process.env.MPH_AGENT_MOCK_COMSOL === "1";
    }
    async init() {
        if (this.mockMode) {
            return;
        }
        const entry = this.findLaunchCommand();
        if (!entry) {
            // Fallback to mock mode when java sidecar artifact is unavailable.
            process.env.MPH_AGENT_MOCK_COMSOL = "1";
            return;
        }
        try {
            const { command, args, cwd } = entry;
            this.ready = false;
            this.child = spawn(command, args, {
                cwd,
                stdio: ["pipe", "pipe", "pipe"]
            });
            this.child.stdout.setEncoding("utf8");
            this.child.stderr.setEncoding("utf8");
            this.child.stdout.on("data", (chunk) => this.onStdout(chunk));
            this.child.stderr.on("data", (chunk) => {
                process.stderr.write(`[java-sidecar] ${chunk}`);
            });
            this.child.on("exit", () => {
                this.cleanupPending(new Error("Java sidecar exited unexpectedly"));
                this.child = null;
                this.ready = false;
            });
            await this.waitUntilReady(10_000);
            const ping = await this.sendRpc("system.ping", {});
            if (!ping.ok) {
                throw new Error(`Java sidecar ping failed: ${ping.message}`);
            }
        }
        catch (error) {
            process.stderr.write(`[java-sidecar] init failed, falling back to mock mode: ${error instanceof Error ? error.message : String(error)}\n`);
            await this.dispose().catch(() => { });
            process.env.MPH_AGENT_MOCK_COMSOL = "1";
        }
    }
    createExecutor() {
        return async (request) => {
            if (process.env.MPH_AGENT_MOCK_COMSOL === "1" ||
                this.mockMode ||
                !this.child ||
                !this.ready) {
                return this.mockExecute(request);
            }
            return this.sendRpc(request.method, request.params);
        };
    }
    async dispose() {
        if (!this.child) {
            return;
        }
        this.ready = false;
        this.child.kill();
        this.child = null;
        this.cleanupPending(new Error("Java sidecar disposed"));
    }
    findLaunchCommand() {
        const jarCandidates = [];
        if (this.resourceRoot) {
            jarCandidates.push(join(this.resourceRoot, "sidecar", "java", "comsol-java-sidecar-all.jar"));
        }
        jarCandidates.push(join(this.workspaceRoot, "apps", "comsol-java-sidecar", "build", "libs", "comsol-java-sidecar-all.jar"));
        const jarPath = jarCandidates.find((item) => existsSync(item));
        if (!jarPath) {
            return null;
        }
        const javaBin = this.resolveJavaBinary();
        return {
            command: javaBin,
            args: ["-jar", jarPath],
            cwd: this.workspaceRoot
        };
    }
    resolveJavaBinary() {
        const configured = process.env.MPH_AGENT_JAVA_BIN;
        if (configured && existsSync(configured)) {
            return configured;
        }
        if (this.resourceRoot) {
            const bundled = join(this.resourceRoot, "runtime", "java", "bin", process.platform === "win32" ? "java.exe" : "java");
            if (existsSync(bundled)) {
                return bundled;
            }
        }
        if (process.env.JAVA_HOME) {
            const javaHomeBin = join(process.env.JAVA_HOME, "bin", process.platform === "win32" ? "java.exe" : "java");
            if (existsSync(javaHomeBin)) {
                return javaHomeBin;
            }
        }
        return process.platform === "win32" ? "java.exe" : "java";
    }
    onStdout(chunk) {
        const lines = chunk
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter(Boolean);
        for (const line of lines) {
            let parsed;
            try {
                parsed = JSON.parse(line);
            }
            catch {
                continue;
            }
            const readyEnvelope = this.tryParseReady(parsed);
            if (readyEnvelope) {
                this.ready = true;
                continue;
            }
            const responseEnvelope = this.tryParseRpcResponse(parsed);
            if (!responseEnvelope) {
                continue;
            }
            const pending = this.pending.get(responseEnvelope.id);
            if (!pending) {
                continue;
            }
            clearTimeout(pending.timer);
            this.pending.delete(responseEnvelope.id);
            pending.resolve({
                ok: responseEnvelope.ok,
                message: responseEnvelope.message,
                ...(responseEnvelope.data ? { data: responseEnvelope.data } : {})
            });
        }
    }
    sendRpc(method, params) {
        if (!this.child) {
            return Promise.resolve({
                ok: false,
                message: "Java sidecar is not running"
            });
        }
        const id = randomUUID();
        const payload = { id, method, params };
        const line = JSON.stringify(payload);
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pending.delete(id);
                reject(new Error(`RPC timeout: ${method}`));
            }, this.timeoutMs);
            this.pending.set(id, { resolve, reject, timer });
            this.child?.stdin.write(`${line}\n`, (error) => {
                if (!error) {
                    return;
                }
                clearTimeout(timer);
                this.pending.delete(id);
                reject(error);
            });
        }).catch((error) => ({
            ok: false,
            message: error instanceof Error ? error.message : String(error)
        }));
    }
    tryParseReady(parsed) {
        if (!isRecord(parsed)) {
            return null;
        }
        if (parsed._ready !== true) {
            return null;
        }
        return {
            _ready: true,
            ...(typeof parsed.ts === "string" ? { ts: parsed.ts } : {}),
            ...(typeof parsed.service === "string" ? { service: parsed.service } : {})
        };
    }
    tryParseRpcResponse(parsed) {
        if (!isRecord(parsed)) {
            return null;
        }
        if (typeof parsed.id !== "string") {
            return null;
        }
        if (typeof parsed.ok !== "boolean") {
            return null;
        }
        if (typeof parsed.message !== "string") {
            return null;
        }
        return {
            id: parsed.id,
            ok: parsed.ok,
            message: parsed.message,
            ...(isRecord(parsed.data) ? { data: parsed.data } : {})
        };
    }
    async waitUntilReady(timeoutMs) {
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            if (this.ready) {
                return;
            }
            if (!this.child) {
                throw new Error("Java sidecar exited before ready");
            }
            await new Promise((resolve) => setTimeout(resolve, 25));
        }
        throw new Error(`Java sidecar handshake timed out after ${timeoutMs}ms`);
    }
    cleanupPending(error) {
        for (const [, pending] of this.pending) {
            clearTimeout(pending.timer);
            pending.reject(error);
        }
        this.pending.clear();
    }
    async mockExecute(request) {
        if (request.method === "system.ping") {
            return {
                ok: true,
                message: "pong",
                data: {
                    service: "comsol-java-sidecar",
                    backend_mode: "mock",
                    version: "1.0.0"
                }
            };
        }
        if (request.method === "comsol.list_apis") {
            return {
                ok: true,
                message: "mock list_apis",
                data: {
                    apis: [
                        {
                            wrapper_name: "api_modelutil_create",
                            owner: "com.comsol.model.util.ModelUtil",
                            method_name: "create"
                        }
                    ],
                    total: 1,
                    limit: request.params.limit ?? 200,
                    offset: request.params.offset ?? 0
                }
            };
        }
        if (request.method === "comsol.perform_action") {
            const runId = typeof request.params.runId === "string" ? request.params.runId : randomUUID();
            const runSegment = this.sanitizeFileSegment(runId);
            const action = isRecord(request.params.action) ? request.params.action : {};
            const actionType = typeof action.type === "string" ? action.type : "unknown";
            const modelsRoot = await this.ensureMockModelsRoot();
            if (actionType === "solve.run") {
                const modelPath = join(modelsRoot, `${runSegment}.mph`);
                const logPath = join(modelsRoot, `${runSegment}.log`);
                await writeFile(modelPath, `# Mock mph artifact generated by agent sidecar\nrunId=${runId}\n`, "utf8");
                await writeFile(logPath, `Mock solve completed at ${new Date().toISOString()}\n`, "utf8");
                return {
                    ok: true,
                    message: "mock solve completed",
                    data: {
                        run_id: runId,
                        action_type: actionType,
                        model_path: modelPath,
                        artifact_path: logPath,
                        artifact_kind: "log",
                        artifact_mime: "text/plain"
                    }
                };
            }
            if (actionType === "postprocess.export") {
                const artifactType = typeof action.artifact === "string" && action.artifact.trim().length > 0
                    ? action.artifact.trim()
                    : "png";
                if (artifactType === "csv") {
                    const csvPath = join(modelsRoot, `${runSegment}_result.csv`);
                    await writeFile(csvPath, "x,y,value\n0,0,1\n", "utf8");
                    return {
                        ok: true,
                        message: "mock postprocess exported",
                        data: {
                            run_id: runId,
                            action_type: actionType,
                            artifact_path: csvPath,
                            artifact_kind: "result_csv",
                            artifact_mime: "text/csv"
                        }
                    };
                }
                const pngPath = join(modelsRoot, `${runSegment}_result.png`);
                await writeFile(pngPath, Buffer.from(TINY_PNG_BASE64, "base64"));
                return {
                    ok: true,
                    message: "mock postprocess exported",
                    data: {
                        run_id: runId,
                        action_type: actionType,
                        artifact_path: pngPath,
                        artifact_kind: "mesh_png",
                        artifact_mime: "image/png"
                    }
                };
            }
            return {
                ok: true,
                message: `mock executed ${actionType}`,
                data: {
                    run_id: runId,
                    action_type: actionType
                }
            };
        }
        if (request.method === "comsol.preview_model") {
            const modelsRoot = await this.ensureMockModelsRoot();
            const previewPath = join(modelsRoot, "preview.png");
            await writeFile(previewPath, Buffer.from(TINY_PNG_BASE64, "base64"));
            return {
                ok: true,
                message: "mock preview",
                data: {
                    image_base64: TINY_PNG_BASE64,
                    artifact_path: previewPath,
                    artifact_kind: "mesh_png",
                    artifact_mime: "image/png"
                }
            };
        }
        const modelPath = join(await this.ensureMockModelsRoot(), "generated_model.mph");
        await writeFile(modelPath, "# Mock model\n", "utf8");
        return {
            ok: true,
            message: `mock executed ${request.method}`,
            data: {
                model_path: modelPath
            }
        };
    }
    async ensureMockModelsRoot() {
        const modelsRoot = join(this.workspaceRoot, "models");
        await mkdir(modelsRoot, { recursive: true });
        return modelsRoot;
    }
    sanitizeFileSegment(value) {
        const sanitized = value
            .replace(/[^a-zA-Z0-9._-]+/g, "_")
            .replace(/_+/g, "_")
            .replace(/^_+/, "")
            .replace(/_+$/, "");
        return sanitized.length > 0 ? sanitized : "item";
    }
}
//# sourceMappingURL=java-sidecar-client.js.map