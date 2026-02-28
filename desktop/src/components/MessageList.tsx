import { useEffect, useRef } from "react";
import { useAppState } from "../context/AppStateContext";
import { useBridge } from "../hooks/useBridge";
import { UserMessage } from "./UserMessage";
import { AssistantMessage } from "./AssistantMessage";
import { SystemMessage } from "./SystemMessage";
import { QUICK_PROMPT_GROUPS, type QuickPromptGroup, type QuickPromptItem } from "../lib/types";

export function MessageList() {
  const { state, messages, dispatch } = useAppState();
  const { handleSubmit } = useBridge();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="message-list">
        <div className="message-list-empty">
          <p className="message-list-empty-hint">输入建模需求开始推理，或输入 /help 查看命令</p>
          <div className="quick-prompts">
            <p className="quick-prompts-title">常用场景 · 点击测试各链路与中断点</p>
            {QUICK_PROMPT_GROUPS.map((group: QuickPromptGroup) => (
              <div key={group.title} className="quick-prompts-section">
                <p className="quick-prompts-section-title" title={group.hint}>
                  {group.title}
                  {group.hint ? <span className="quick-prompts-section-hint"> · {group.hint}</span> : null}
                </p>
                <div className="quick-prompts-grid">
                  {group.prompts.map((item: QuickPromptItem) => (
                    <button
                      key={`${group.title}-${item.label}`}
                      type="button"
                      className="quick-prompt-chip"
                      onClick={() => handleSubmit(item.text)}
                      title={item.text}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list">
      {messages.map((msg, index) => {
        switch (msg.role) {
          case "user":
            return (
              <UserMessage
                key={msg.id}
                message={msg}
                onEditResend={(text) => {
                  if (state.currentConversationId == null) return;
                  dispatch({
                    type: "REMOVE_MESSAGES_FROM_INDEX",
                    conversationId: state.currentConversationId,
                    fromIndex: index,
                  });
                  dispatch({ type: "SET_EDITING_DRAFT", text });
                }}
              />
            );
          case "assistant":
            return <AssistantMessage key={msg.id} message={msg} />;
          case "system":
            return <SystemMessage key={msg.id} message={msg} />;
        }
      })}
      <div ref={bottomRef} />
    </div>
  );
}
