import type { ChatMessage } from "../lib/types";

export function UserMessage({
  message,
  onEditResend,
}: {
  message: ChatMessage;
  onEditResend?: (text: string) => void;
}) {
  return (
    <div className="user-msg">
      <div className="user-msg-text">{message.text}</div>
      {onEditResend && (
        <button
          type="button"
          className="user-msg-edit-resend"
          onClick={() => onEditResend(message.text)}
          title="修改后重新发起建模"
        >
          编辑并重新建模
        </button>
      )}
    </div>
  );
}
