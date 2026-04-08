import type { ComsolExecutor } from "@mph-agent/agent-core";
export declare class JavaSidecarClient {
    private child;
    private pending;
    private readonly workspaceRoot;
    private readonly resourceRoot;
    private readonly timeoutMs;
    private readonly mockMode;
    private ready;
    constructor(workspaceRoot: string, timeoutMs?: number);
    init(): Promise<void>;
    createExecutor(): ComsolExecutor;
    dispose(): Promise<void>;
    private findLaunchCommand;
    private resolveJavaBinary;
    private onStdout;
    private sendRpc;
    private tryParseReady;
    private tryParseRpcResponse;
    private waitUntilReady;
    private cleanupPending;
    private mockExecute;
    private ensureMockModelsRoot;
    private sanitizeFileSegment;
}
