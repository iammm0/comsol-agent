import { useEffect, useRef } from "react";
import { useAppState } from "../context/AppStateContext";
import { useBridge } from "../hooks/useBridge";
import { UserMessage } from "./UserMessage";
import { AssistantMessage } from "./AssistantMessage";
import { SystemMessage } from "./SystemMessage";
import { QUICK_PROMPTS } from "../lib/types";

export function MessageList() {
  const { state, messages } = useAppState();
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
            <p className="quick-prompts-title">常用场景 · 点击快捷开始</p>
            <div className="quick-prompts-grid">
              {QUICK_PROMPTS.map((item) => (
                <button
                  key={item.label}
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
        </div>
      </div>
    );
  }

  return (
    <div className="message-list">
      {messages.map((msg) => {
        switch (msg.role) {
          case "user":
            return <UserMessage key={msg.id} message={msg} />;
          case "assistant":
            return <AssistantMessage key={msg.id} message={msg} />;
          case "system":
            return <SystemMessage key={msg.id} message={msg} />;
        }
      })}
      {state.busyConversationId === state.currentConversationId && (
        <div className="spinner">
          <span className="spinner-dot" />
          {(() => {
            const last = messages[messages.length - 1];
            const events = last?.role === "assistant" ? last.events : undefined;
            let label = "处理中";
            if (events?.length) {
              for (let i = events.length - 1; i >= 0; i--) {
                if (events[i].type === "task_phase" && events[i].data?.phase) {
                  const map: Record<string, string> = {
                    planning: "规划中",
                    thinking: "思考中",
                    executing: "执行中",
                    observing: "观察中",
                    iterating: "迭代中",
                  };
                  label = map[events[i].data.phase as string] ?? label;
                  break;
                }
              }
            }
            return label;
          })()}
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
