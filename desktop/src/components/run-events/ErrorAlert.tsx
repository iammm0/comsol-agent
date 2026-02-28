import type { RunEvent } from "../../lib/types";

export function ErrorAlert({ event }: { event: RunEvent }) {
  const message = String(event.data?.message ?? "").trim();
  if (!message) return null;

  return (
    <div className="run-event-alert run-event-alert--error">
      <span className="run-event-alert__icon" aria-hidden>×</span>
      <p className="run-event-alert__text">{message}</p>
    </div>
  );
}
