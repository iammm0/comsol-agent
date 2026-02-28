import type { RunEvent } from "../../lib/types";

/** 思维流（LLM 流式 / think_chunk）：气泡样式 */
export function ThinkBubble({ event }: { event: RunEvent }) {
  const d = event.data ?? {};
  const type = event.type;

  if (type === "llm_stream_chunk") {
    const chunk = String(d.chunk ?? d.text ?? "").trim();
    const phase = (d.phase as string) ?? "";
    if (!chunk) return null;
    return (
      <div className="run-event-bubble run-event-bubble--think">
        {phase && <span className="run-event-bubble__phase">{phase}</span>}
        <div className="run-event-bubble__content run-event-bubble__content--stream">
          {chunk}
        </div>
      </div>
    );
  }

  const thought = d.thought as Record<string, unknown> | undefined;
  if (!thought) return null;
  const action = thought.action as string | undefined;
  const reasoning = thought.reasoning as string | undefined;

  return (
    <div className="run-event-bubble run-event-bubble--think">
      {action && <div className="run-event-bubble__action">{action}</div>}
      {reasoning && <div className="run-event-bubble__content">{reasoning}</div>}
      {!action && !reasoning && (
        <div className="run-event-bubble__content">{JSON.stringify(thought).slice(0, 200)}</div>
      )}
    </div>
  );
}
