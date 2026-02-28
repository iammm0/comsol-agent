import type { RunEvent } from "../../lib/types";

export function StepNode({ event }: { event: RunEvent }) {
  const d = event.data ?? {};
  const type = event.type;
  const isEnd = type === "step_end";
  const message = String(d.message ?? d.step_type ?? (isEnd ? "完成" : "执行中...")).trim();

  return (
    <div className={`run-event-step ${isEnd ? "run-event-step--end" : "run-event-step--start"}`}>
      <span className="run-event-step__dot" aria-hidden />
      <span className="run-event-step__label">{message}</span>
    </div>
  );
}
