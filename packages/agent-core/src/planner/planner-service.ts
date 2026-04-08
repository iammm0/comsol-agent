import { createHash } from "node:crypto";
import type { PlannerOutput } from "../types/runtime.js";
import type { ComsolAction } from "@mph-agent/contracts";

function hashId(input: string): string {
  return createHash("sha1").update(input).digest("hex").slice(0, 10);
}

function inferDimension(input: string): 2 | 3 {
  return /\b3d\b|三维|3维|三\s*维/i.test(input) ? 3 : 2;
}

function baseGeometryAction(dimension: 2 | 3): ComsolAction {
  return {
    type: "geometry.create",
    feature: dimension === 3 ? "block" : "workplane",
    params:
      dimension === 3
        ? { width: 0.2, height: 0.1, depth: 0.05 }
        : { width: 1.0, height: 0.5 }
  };
}

export class PlannerService {
  public plan(input: string): PlannerOutput {
    const trimmed = input.trim();
    const modelName = `model_${hashId(trimmed || "empty")}`;
    const dimension = inferDimension(trimmed);
    const steps: PlannerOutput["steps"] = [];

    steps.push({
      stepId: "step_geometry",
      label: "Create geometry",
      action: baseGeometryAction(dimension)
    });

    if (/材料|material|铝|钢|铜/i.test(trimmed)) {
      steps.push({
        stepId: "step_physics_material",
        label: "Add physics",
        action: {
          type: "physics.add",
          feature: "heat_transfer",
          domainSelection: [1],
          params: { material_hint: "from_prompt" }
        }
      });
    }

    if (/网格|mesh/i.test(trimmed)) {
      steps.push({
        stepId: "step_mesh",
        label: "Generate mesh",
        action: {
          type: "mesh.generate",
          feature: dimension === 3 ? "free_tetrahedral" : "free_triangular",
          size: "normal"
        }
      });
    }

    steps.push({
      stepId: "step_study",
      label: "Configure study",
      action: {
        type: "study.setup",
        feature: /瞬态|time/i.test(trimmed) ? "time_dependent" : "stationary",
        params: { auto: true }
      }
    });

    steps.push({
      stepId: "step_solve",
      label: "Run solve",
      action: {
        type: "solve.run",
        solver: "default",
        params: {}
      }
    });

    const clarifyingQuestions = this.buildClarifyingQuestions(trimmed);

    return {
      modelName,
      steps,
      ...(clarifyingQuestions ? { clarifyingQuestions } : {})
    };
  }

  private buildClarifyingQuestions(input: string): PlannerOutput["clarifyingQuestions"] {
    const hasBoundary = /边界|boundary|温度|压力|载荷/i.test(input);
    if (hasBoundary) {
      return [];
    }

    return [
      {
        id: "q_boundary",
        text: "Boundary conditions are missing. Which default should be used?",
        type: "single",
        options: [
          {
            id: "opt_recommended",
            label: "Use engineering defaults",
            value: "recommended",
            recommended: true
          },
          {
            id: "opt_custom",
            label: "I will provide details",
            value: "custom"
          }
        ]
      }
    ];
  }
}
