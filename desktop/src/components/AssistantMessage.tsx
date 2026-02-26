import type { ChatMessage } from "../lib/types";
import { RunEventBlock } from "./RunEventBlock";

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function AssistantMessage({ message }: { message: ChatMessage }) {
  const hasEvents = (message.events?.length ?? 0) > 0;
  const isError = message.success === false;
  const showText = !isError && (message.text || !hasEvents);

  return (
    <div className="assistant-msg">
      {hasEvents && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {message.events!.map((evt, i) => (
            <RunEventBlock key={i} event={evt} />
          ))}
        </div>
      )}
      {isError && (
        <div className="assistant-msg-body error">
          <div className="assistant-msg-text">{message.text}</div>
        </div>
      )}
      {showText && (
        <div className="assistant-msg-body success">
          <div className="assistant-msg-text">
            {message.text || "处理中..."}
          </div>
          <div className="assistant-msg-meta">
            <span className="dot">▣</span>
            <span>{formatTime(message.time)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
