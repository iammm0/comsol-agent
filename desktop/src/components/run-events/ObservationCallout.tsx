import type { RunEvent } from "../../lib/types";

export function ObservationCallout({ event }: { event: RunEvent }) {
  const d = event.data ?? {};
  const message = String(d.observation ?? d.message ?? "").trim();
  const status = (d.status as string) ?? "success";
  const isWarning = status === "warning";
  const isError = status === "error";

  if (!message) return null;

  return (
    <div
      className={`run-event-callout run-event-callout--observation ${
        isError ? "run-event-callout--error" : isWarning ? "run-event-callout--warning" : "run-event-callout--info"
      }`}
    >
      <span className="run-event-callout__icon" aria-hidden>
        {isError ? "!" : isWarning ? "⚠" : "ℹ"}
      </span>
      <p className="run-event-callout__text">{message}</p>
    </div>
  );
}
