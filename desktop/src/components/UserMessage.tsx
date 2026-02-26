import type { ChatMessage } from "../lib/types";

export function UserMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="user-msg">
      <div className="user-msg-text">{message.text}</div>
    </div>
  );
}
