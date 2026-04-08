import { randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  bridgeRequestSchema,
  createResponse,
  type BridgeRequest,
  type BridgeResponse,
  type CommandPayload
} from "@mph-agent/contracts";
import { PlannerService } from "../planner/planner-service.js";
import { ReActAgent } from "../react/react-agent.js";
import { ComsolService } from "../services/comsol-service.js";
import { ContextService } from "../services/context-service.js";
import { SkillService } from "../services/skill-service.js";
import type {
  ComsolExecutor,
  RuntimeCommandContext,
  RuntimeCommandHandler,
  RuntimeConfig,
  RuntimePaths
} from "../types/runtime.js";

interface RuntimeDeps {
  config: RuntimeConfig;
  comsolExecutor: ComsolExecutor;
}

export class AgentRuntime {
  private readonly config: RuntimeConfig;
  private readonly contextService: ContextService;
  private readonly plannerService: PlannerService;
  private readonly skillService: SkillService;
  private readonly comsolService: ComsolService;
  private readonly reactAgent: ReActAgent;

  public constructor(deps: RuntimeDeps) {
    this.config = deps.config;
    this.contextService = new ContextService(this.config.paths.contextRoot);
    this.plannerService = new PlannerService();
    this.skillService = new SkillService(this.config.paths.skillsRoot);
    this.comsolService = new ComsolService(deps.comsolExecutor);
    this.reactAgent = new ReActAgent(this.plannerService, this.comsolService);
  }

  public static defaultPaths(workspaceRoot: string): RuntimePaths {
    return {
      workspaceRoot,
      contextRoot: join(workspaceRoot, ".context-ts"),
      skillsRoot: join(workspaceRoot, "skills"),
      promptsRoot: join(workspaceRoot, "prompts"),
      modelsRoot: join(workspaceRoot, "models")
    };
  }

  public async init(): Promise<void> {
    await mkdir(this.config.paths.modelsRoot, { recursive: true });
    await this.contextService.init();
    await this.skillService.ensureInitialized();
  }

  public async handle(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const req = bridgeRequestSchema.parse(context.request);
    const handlers = this.handlers();
    const handler = handlers[req.cmd];

    if (!handler) {
      return createResponse({
        id: req.id,
        ok: false,
        message: `Unknown command: ${req.cmd}`,
        error: {
          code: "UNKNOWN_COMMAND",
          message: `Unknown command: ${req.cmd}`
        }
      });
    }

    return handler({ ...context, request: req as BridgeRequest<CommandPayload> });
  }

  private handlers(): Record<string, RuntimeCommandHandler> {
    return {
      run: async (context) => this.handleRun(context),
      plan: async (context) => this.handlePlan(context),
      exec: async (context) => this.handleExec(context),
      demo: async (context) =>
        this.success(context.request.id, "Demo command executed", { lines: ["demo ok"] }),
      doctor: async (context) => this.handleDoctor(context),
      context_show: async (context) => this.handleContextShow(context),
      context_get_summary: async (context) => this.handleContextGetSummary(context),
      context_set_summary: async (context) => this.handleContextSetSummary(context),
      context_history: async (context) => this.handleContextHistory(context),
      context_stats: async (context) => this.handleContextStats(context),
      context_clear: async (context) => this.handleContextClear(context),
      config_save: async (context) => this.handleConfigSave(context),
      ollama_ping: async (context) => this.success(context.request.id, "Ollama ping simulated", { healthy: true }),
      models_list: async (context) => this.handleModelsList(context),
      list_apis: async (context) => this.handleListApis(context),
      model_preview: async (context) => this.handleModelPreview(context),
      conversation_delete: async (context) => this.handleConversationDelete(context),
      abort: async (context) => this.success(context.request.id, "Abort accepted", {})
    };
  }

  private async handleRun(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const input = String(context.request.payload.input ?? "").trim();
    if (!input) {
      return this.failure(context.request.id, "input is required", "VALIDATION_ERROR");
    }

    const conversationId = this.getConversationId(
      context.request.payload.conversation_id,
      context.request.conversationId
    );
    const runResult = await this.reactAgent.run(input, context.emit);

    await this.contextService.addConversationEntry({
      id: randomUUID(),
      conversationId,
      timestamp: new Date().toISOString(),
      userInput: input,
      plan: { status: runResult.ok ? "completed" : "failed" },
      ...(runResult.modelPath ? { modelPath: runResult.modelPath } : {}),
      success: runResult.ok,
      ...(!runResult.ok ? { error: runResult.message } : {})
    });

    if (runResult.ok) {
      return this.success(context.request.id, runResult.message, {
        model_path: runResult.modelPath,
        artifacts: runResult.artifacts,
        run_state: runResult.runState
      });
    }

    return this.failure(context.request.id, runResult.message, "RUN_FAILED", {
      run_state: runResult.runState,
      artifacts: runResult.artifacts
    });
  }

  private async handlePlan(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const input = String(context.request.payload.input ?? "").trim();
    if (!input) {
      return this.failure(context.request.id, "input is required", "VALIDATION_ERROR");
    }
    const plan = this.plannerService.plan(input);
    return this.success(context.request.id, "Plan generated", {
      plan,
      plan_needs_clarification: Boolean(plan.clarifyingQuestions && plan.clarifyingQuestions.length > 0)
    });
  }

  private async handleExec(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const path = String(context.request.payload.path ?? "").trim();
    if (!path) {
      return this.failure(context.request.id, "path is required", "VALIDATION_ERROR");
    }

    const data = await this.comsolService.performAction(randomUUID(), {
      type: "solve.run",
      solver: "default",
      params: {
        plan_path: path
      }
    });

    if (!data.ok) {
      return this.failure(context.request.id, String(data.message), "EXEC_FAILED", data);
    }

    return this.success(context.request.id, "Execution completed", data);
  }

  private async handleDoctor(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const comsolHealth = await this.comsolService.health();
    return this.success(context.request.id, "Doctor diagnostics", {
      node: process.version,
      platform: process.platform,
      arch: process.arch,
      paths: this.config.paths,
      comsol: comsolHealth
    });
  }

  private async handleContextShow(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const conversationId = this.getConversationId(
      context.request.payload.conversation_id,
      context.request.conversationId
    );
    const summary = await this.contextService.getSummary(conversationId);
    return this.success(context.request.id, summary?.summary ?? "No summary", {
      summary: summary?.summary ?? "",
      detail: summary ?? {}
    });
  }

  private async handleContextGetSummary(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    return this.handleContextShow(context);
  }

  private async handleContextSetSummary(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const conversationId = this.getConversationId(
      context.request.payload.conversation_id,
      context.request.conversationId
    );
    const text = String(context.request.payload.text ?? "");
    await this.contextService.setSummary(conversationId, text);
    return this.success(context.request.id, "Summary updated", {});
  }

  private async handleContextHistory(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const conversationId = this.getConversationId(
      context.request.payload.conversation_id,
      context.request.conversationId
    );
    const limit = Number(context.request.payload.limit ?? 10);
    const historyText = await this.contextService.getHistoryAsText(
      conversationId,
      Number.isFinite(limit) ? limit : 10
    );
    return this.success(context.request.id, historyText, { history: historyText });
  }

  private async handleContextStats(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const conversationId = this.getConversationId(
      context.request.payload.conversation_id,
      context.request.conversationId
    );
    const stats = await this.contextService.getStats(conversationId);
    return this.success(context.request.id, "Context stats", stats);
  }

  private async handleContextClear(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const conversationId = this.getConversationId(
      context.request.payload.conversation_id,
      context.request.conversationId
    );
    await this.contextService.clearConversation(conversationId);
    return this.success(context.request.id, "Context cleared", {});
  }

  private async handleConfigSave(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const config = context.request.payload.config;
    if (!config) {
      return this.failure(context.request.id, "config payload is required", "VALIDATION_ERROR");
    }

    const configPath = join(this.config.paths.workspaceRoot, ".env.ts.json");
    let existing: Record<string, string> = {};
    try {
      const raw = await readFile(configPath, "utf8");
      const parsed = JSON.parse(raw) as unknown;
      if (parsed && typeof parsed === "object") {
        existing = parsed as Record<string, string>;
      }
    } catch {
      existing = {};
    }

    const merged = {
      ...existing,
      ...config
    };

    await writeFile(configPath, JSON.stringify(merged, null, 2), "utf8");
    return this.success(context.request.id, "Config saved", { config_path: configPath });
  }

  private async handleModelsList(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const limit = Number(context.request.payload.limit ?? 50);
    const models = await this.contextService.getModels(Number.isFinite(limit) ? limit : 50);
    return this.success(context.request.id, "Models listed", { models });
  }

  private async handleListApis(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const query = context.request.payload.query
      ? String(context.request.payload.query)
      : undefined;
    const limit = Number(context.request.payload.limit ?? 200);
    const offset = Number(context.request.payload.offset ?? 0);
    const result = await this.comsolService.listApis(
      query,
      Number.isFinite(limit) ? limit : 200,
      Number.isFinite(offset) ? offset : 0
    );
    if (!result.ok) {
      return this.failure(context.request.id, String(result.message), "LIST_APIS_FAILED", result);
    }
    return this.success(context.request.id, String(result.message), result);
  }

  private async handleModelPreview(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const path = String(
      context.request.payload.path ?? context.request.payload.model_path ?? ""
    ).trim();
    if (!path) {
      return this.failure(context.request.id, "path is required", "VALIDATION_ERROR");
    }

    const width = Number(context.request.payload.width ?? 640);
    const height = Number(context.request.payload.height ?? 480);
    const result = await this.comsolService.previewModel(
      path,
      Number.isFinite(width) ? width : 640,
      Number.isFinite(height) ? height : 480
    );

    if (!result.ok) {
      return this.failure(
        context.request.id,
        String(result.message),
        "MODEL_PREVIEW_FAILED",
        result
      );
    }

    return this.success(context.request.id, String(result.message), result);
  }

  private async handleConversationDelete(
    context: RuntimeCommandContext
  ): Promise<BridgeResponse<Record<string, unknown>>> {
    const conversationId = this.getConversationId(
      context.request.payload.conversation_id,
      context.request.conversationId
    );
    const deletedPaths = await this.contextService.deleteConversationAndModels(conversationId);
    return this.success(context.request.id, "Conversation deleted", {
      deleted_paths: deletedPaths
    });
  }

  private success(
    id: string,
    message: string,
    data: Record<string, unknown>
  ): BridgeResponse<Record<string, unknown>> {
    return createResponse({
      id,
      ok: true,
      message,
      data
    });
  }

  private failure(
    id: string,
    message: string,
    code: string,
    data?: Record<string, unknown>
  ): BridgeResponse<Record<string, unknown>> {
    return createResponse({
      id,
      ok: false,
      message,
      ...(data ? { data } : {}),
      error: {
        code,
        message
      }
    });
  }

  private getConversationId(payloadValue: unknown, envelopeValue: unknown): string {
    if (typeof payloadValue === "string" && payloadValue.trim().length > 0) {
      return payloadValue.trim();
    }
    if (typeof envelopeValue === "string" && envelopeValue.trim().length > 0) {
      return envelopeValue.trim();
    }
    return "default";
  }
}

export function createDefaultConfig(workspaceRoot: string): RuntimeConfig {
  return {
    paths: AgentRuntime.defaultPaths(workspaceRoot),
    defaultBackend: "ollama",
    defaultModel: "llama3",
    defaultOllamaUrl: "http://localhost:11434"
  };
}

export function passthroughComsolExecutor(workspaceRoot = process.cwd()): ComsolExecutor {
  return async (request) => {
    const data: Record<string, unknown> = { method: request.method };

    if (request.method === "comsol.perform_action") {
      data.model_path = join(workspaceRoot, "models", "generated_model.mph");
    }

    if (request.method === "comsol.preview_model") {
      data.artifact_path = join(workspaceRoot, "models", "preview.png");
      data.artifact_kind = "mesh_png";
      data.artifact_mime = "image/png";
    }

    if (request.method === "comsol.list_apis") {
      data.apis = [
        {
          wrapper_name: "api_modelutil_create",
          owner: "com.comsol.model.util.ModelUtil",
          method_name: "create"
        }
      ];
      data.total = 1;
      data.limit = request.params.limit;
      data.offset = request.params.offset;
    }

    return {
      ok: true,
      message: `Mocked ${request.method}`,
      data
    };
  };
}
