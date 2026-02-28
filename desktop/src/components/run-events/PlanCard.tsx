import type { RunEvent } from "../../lib/types";

/** 规划开始：展示用户输入 */
export function PlanStartCard({ event }: { event: RunEvent }) {
  const input = String(event.data?.user_input ?? "").trim();
  if (!input) return null;
  return (
    <div className="run-event-card run-event-card--plan-start">
      <span className="run-event-card__icon" aria-hidden>📋</span>
      <div className="run-event-card__main">
        <span className="run-event-card__title">规划开始</span>
        <p className="run-event-card__highlight">{input}</p>
      </div>
    </div>
  );
}

/** 规划完成：展示模型名与步骤链 */
export function PlanEndCard({ event }: { event: RunEvent }) {
  const d = event.data ?? {};
  const steps = d.steps as Array<{ action?: string; step_type?: string }> | undefined;
  const model = String(d.model_name ?? "").trim();
  const desc = d.plan_description as string | undefined;

  return (
    <div className="run-event-card run-event-card--plan-end">
      <span className="run-event-card__icon" aria-hidden>✓</span>
      <div className="run-event-card__main">
        <span className="run-event-card__title">规划完成</span>
        {model && <p className="run-event-card__model">{model}</p>}
        {steps?.length ? (
          <ul className="run-event-card__steps">
            {steps.map((s, i) => (
              <li key={i}>{s.action ?? s.step_type ?? "步骤"}</li>
            ))}
          </ul>
        ) : null}
        {desc && <p className="run-event-card__desc">{desc}</p>}
      </div>
    </div>
  );
}
