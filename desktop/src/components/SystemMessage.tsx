import type { ChatMessage } from "../lib/types";

export function SystemMessage({ message }: { message: ChatMessage }) {
  const cls = message.success === false ? "system-msg error" : "system-msg normal";
  return <div className={cls}>{message.text}</div>;
}
