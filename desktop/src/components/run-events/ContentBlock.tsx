import type { RunEvent } from "../../lib/types";

export function ContentBlock({ event }: { event: RunEvent }) {
  const content = String(event.data?.content ?? "").trim();
  if (!content) return null;
  return <div className="run-event-content-block">{content}</div>;
}
