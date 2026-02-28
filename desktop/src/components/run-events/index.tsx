import type { RunEvent } from "../../lib/types";
import { PlanStartCard, PlanEndCard } from "./PlanCard";
import { PhasePill } from "./PhasePill";
import { ThinkBubble } from "./ThinkBubble";
import { ActionStepCard } from "./ActionStepCard";
import { StepNode } from "./StepNode";
import { MaterialCard } from "./MaterialCard";
import { FeatureBadge } from "./FeatureBadge";
import { ObservationCallout } from "./ObservationCallout";
import { ErrorAlert } from "./ErrorAlert";
import { ContentBlock } from "./ContentBlock";

/** 按事件类型选择对应展示组件，突出不同类型信息的重点 */
export function RunEventBlock({ event }: { event: RunEvent }) {
  const type = event.type ?? "";

  switch (type) {
    case "plan_start":
      return <PlanStartCard event={event} />;
    case "plan_end":
      return <PlanEndCard event={event} />;
    case "task_phase":
      return <PhasePill event={event} />;
    case "think_chunk":
    case "llm_stream_chunk":
      return <ThinkBubble event={event} />;
    case "action_start":
    case "action_end":
    case "exec_result":
      return <ActionStepCard event={event} />;
    case "step_start":
    case "step_end":
      return <StepNode event={event} />;
    case "material_start":
    case "material_end":
      return <MaterialCard event={event} />;
    case "geometry_3d":
    case "coupling_added":
      return <FeatureBadge event={event} />;
    case "observation":
      return <ObservationCallout event={event} />;
    case "error":
      return <ErrorAlert event={event} />;
    case "content":
      return <ContentBlock event={event} />;
    default:
      return <FallbackBlock event={event} />;
  }
}

function FallbackBlock({ event }: { event: RunEvent }) {
  const d = event.data ?? {};
  return (
    <div className="run-event run-event--fallback">
      <span className="run-event__type">{event.type}</span>
      {Object.keys(d).length > 0 && (
        <pre className="run-event__raw">{JSON.stringify(d).slice(0, 200)}</pre>
      )}
    </div>
  );
}
