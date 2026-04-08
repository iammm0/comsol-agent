import type { ComsolExecutor } from "../types/runtime.js";
import type { ComsolAction } from "@mph-agent/contracts";

export class ComsolService {
  private readonly executeRpc: ComsolExecutor;

  public constructor(executeRpc: ComsolExecutor) {
    this.executeRpc = executeRpc;
  }

  public async performAction(runId: string, action: ComsolAction): Promise<Record<string, unknown>> {
    const rpcResult = await this.executeRpc({
      method: "comsol.perform_action",
      params: {
        runId,
        action
      }
    });

    if (!rpcResult.ok) {
      return {
        ok: false,
        message: rpcResult.message
      };
    }

    return {
      ok: true,
      message: rpcResult.message,
      ...(rpcResult.data ?? {})
    };
  }

  public async previewModel(path: string, width: number, height: number): Promise<Record<string, unknown>> {
    const rpcResult = await this.executeRpc({
      method: "comsol.preview_model",
      params: { path, width, height }
    });

    return {
      ok: rpcResult.ok,
      message: rpcResult.message,
      ...(rpcResult.data ?? {})
    };
  }

  public async listApis(query: string | undefined, limit: number, offset: number): Promise<Record<string, unknown>> {
    const rpcResult = await this.executeRpc({
      method: "comsol.list_apis",
      params: {
        query,
        limit,
        offset
      }
    });

    return {
      ok: rpcResult.ok,
      message: rpcResult.message,
      ...(rpcResult.data ?? {})
    };
  }

  public async health(): Promise<Record<string, unknown>> {
    const rpcResult = await this.executeRpc({
      method: "system.ping",
      params: {}
    });

    return {
      ok: rpcResult.ok,
      message: rpcResult.message,
      ...(rpcResult.data ?? {})
    };
  }
}
