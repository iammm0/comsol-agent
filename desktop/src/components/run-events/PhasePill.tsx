import type { RunEvent } from "../../lib/types";

const PHASE_LABELS: Record<string, string> = {
  discussion: "闲聊中",
  planning: "规划中",
  planning_clarify: "规划澄清中",
  plan_confirmed: "计划已确认",
  thinking: "思考中",
  executing: "执行中",
  observing: "观察中",
  iterating: "根据结果调整中",
  qa: "问答",
};

export function PhasePill({ event }: { event: RunEvent }) {
  const phase = (event.data?.phase as string) ?? "";
  const label = PHASE_LABELS[phase] || phase || "处理中";
  return (
    <div className="run-event-pill run-event-pill--phase" data-phase={phase}>
      <span className="run-event-pill__dot" />
      <span className="run-event-pill__text">{label}</span>
    </div>
  );
}
