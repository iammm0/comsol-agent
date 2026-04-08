import { randomUUID } from "node:crypto";
import type { AgentRunState, RunPhase } from "@mph-agent/contracts";
import type { ComsolService } from "../services/comsol-service.js";
import type { PlannerService } from "../planner/planner-service.js";
import type { ReActRunResult } from "../types/runtime.js";
import { ReActEventBus } from "./event-bus.js";

function toProgress(index: number, total: number): number {
  if (total <= 0) {
    return 0;
  }
  return Math.min(100, Math.round(((index + 1) / total) * 100));
}

export class ReActAgent {
  private readonly planner: PlannerService;
  private readonly comsol: ComsolService;

  public constructor(planner: PlannerService, comsol: ComsolService) {
    this.planner = planner;
    this.comsol = comsol;
  }

  public async run(
    input: string,
    emit: (event: import("@mph-agent/contracts").BridgeEvent) => void
  ): Promise<ReActRunResult> {
    const runId = randomUUID();
    const bus = new ReActEventBus(runId, emit);
    const plan = this.planner.plan(input);
    const startedAt = new Date().toISOString();

    const state: AgentRunState = {
      runId,
      phase: "planning",
      progress: 0,
      startedAt
    };

    bus.emit("run_started", {
      input,
      modelName: plan.modelName
    });

    bus.emit("plan_end", {
      plan,
      requires_clarification: Boolean(plan.clarifyingQuestions && plan.clarifyingQuestions.length > 0),
      clarifying_questions: plan.clarifyingQuestions ?? []
    });

    const artifacts: ReActRunResult["artifacts"] = [];

    for (const [index, step] of plan.steps.entries()) {
      state.phase = this.mapStepToPhase(step.label);
      state.currentStep = step.label;
      state.progress = toProgress(index, plan.steps.length);

      bus.emit(
        "run_progress",
        {
          progress: state.progress,
          step: step.label,
          phase: state.phase
        },
        index + 1
      );

      bus.emit(
        "action",
        {
          stepId: step.stepId,
          label: step.label,
          action: step.action
        },
        index + 1
      );

      const actionResult = await this.comsol.performAction(runId, step.action);
      if (!actionResult.ok) {
        state.phase = "failed";
        state.failure = {
          code: "COMSOL_ACTION_FAILED",
          message: String(actionResult.message),
          retriable: false
        };
        state.endedAt = new Date().toISOString();

        bus.emit(
          "run_failed",
          {
            code: state.failure.code,
            message: state.failure.message,
            stepId: step.stepId
          },
          index + 1
        );

        return {
          ok: false,
          message: state.failure.message,
          runState: state,
          artifacts
        };
      }

      bus.emit(
        "observation",
        {
          stepId: step.stepId,
          message: actionResult.message,
          data: actionResult
        },
        index + 1
      );

      if (typeof actionResult.artifact_path === "string") {
        const artifactKind = this.parseArtifactKind(actionResult.artifact_kind);
        const artifact = {
          id: randomUUID(),
          runId,
          kind: artifactKind,
          path: actionResult.artifact_path,
          mime: String(actionResult.artifact_mime ?? "application/octet-stream"),
          createdAt: new Date().toISOString()
        };
        artifacts.push(artifact);
        bus.emit("artifact", artifact, index + 1);
      }

      if (typeof actionResult.model_path === "string") {
        state.modelPath = actionResult.model_path;
      }
    }

    state.phase = "completed";
    state.progress = 100;
    state.endedAt = new Date().toISOString();

    bus.emit("run_completed", {
      message: "Run completed",
      model_path: state.modelPath ?? null,
      artifacts
    });

    return {
      ok: true,
      message: state.modelPath ? `Model generated: ${state.modelPath}` : "Run completed",
      ...(state.modelPath ? { modelPath: state.modelPath } : {}),
      runState: state,
      artifacts
    };
  }

  private mapStepToPhase(label: string): RunPhase {
    if (/plan/i.test(label)) {
      return "planning";
    }
    if (/solve/i.test(label)) {
      return "observing";
    }
    return "acting";
  }

  private parseArtifactKind(input: unknown): ReActRunResult["artifacts"][number]["kind"] {
    if (
      input === "mph" ||
      input === "mesh_png" ||
      input === "result_csv" ||
      input === "report_md" ||
      input === "log"
    ) {
      return input;
    }
    return "log";
  }
}
