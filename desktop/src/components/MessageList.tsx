import { useEffect, useRef, useState } from "react";
import { useAppState } from "../context/AppStateContext";
import { useBridge } from "../hooks/useBridge";
import { UserMessage } from "./UserMessage";
import { AssistantMessage } from "./AssistantMessage";
import { SystemMessage } from "./SystemMessage";
import {
  QUICK_PROMPT_GROUPS,
  USAGE_WORKFLOW_HEADLINE,
  USAGE_WORKFLOW_INTRO,
  USAGE_WORKFLOW_SHORTCUTS,
  USAGE_WORKFLOW_STEPS,
  type QuickPromptGroup,
  type QuickPromptItem,
} from "../lib/types";

export function MessageList() {
  const { messages } = useAppState();
  const { handleSubmit, triggerExtensionAction } = useBridge();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [emptyPanel, setEmptyPanel] = useState<"workflow" | "cases">("workflow");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="message-list">
        <div className="message-list-empty">
          <p className="message-list-empty-hint">输入建模需求开始推理，扩展功能请点击输入框左侧的 +</p>
          <div className="empty-state-panels">
            <div className="empty-state-tabs" role="tablist" aria-label="新会话引导分区">
              <button
                type="button"
                role="tab"
                id="empty-tab-workflow"
                className="empty-state-tab"
                aria-selected={emptyPanel === "workflow"}
                aria-controls="empty-panel-workflow"
                onClick={() => setEmptyPanel("workflow")}
              >
                使用流程
              </button>
              <button
                type="button"
                role="tab"
                id="empty-tab-cases"
                className="empty-state-tab"
                aria-selected={emptyPanel === "cases"}
                aria-controls="empty-panel-cases"
                onClick={() => setEmptyPanel("cases")}
              >
                快速案例
              </button>
            </div>

            {emptyPanel === "workflow" ? (
              <section
                id="empty-panel-workflow"
                role="tabpanel"
                aria-labelledby="empty-tab-workflow"
                className="usage-workflow"
              >
                <h2 id="usage-workflow-title" className="usage-workflow-title">
                  {USAGE_WORKFLOW_HEADLINE}
                </h2>
                <p className="usage-workflow-intro">{USAGE_WORKFLOW_INTRO}</p>
                <ol className="usage-workflow-steps">
                  {USAGE_WORKFLOW_STEPS.map((row) => (
                    <li key={row.step} className="usage-workflow-step">
                      <span className="usage-workflow-step-index">{row.step}</span>
                      <div className="usage-workflow-step-body">
                        <span className="usage-workflow-step-title">{row.title}</span>
                        <span className="usage-workflow-step-text">{row.body}</span>
                      </div>
                    </li>
                  ))}
                </ol>
                <div className="usage-workflow-shortcuts">
                  <span className="usage-workflow-shortcuts-label">快捷命令</span>
                  <div className="usage-workflow-shortcuts-grid">
                    {USAGE_WORKFLOW_SHORTCUTS.map((item: QuickPromptItem) => (
                      <button
                        key={item.label}
                        type="button"
                        className="usage-workflow-chip"
                        onClick={() =>
                          item.extensionName
                            ? void triggerExtensionAction(item.extensionName)
                            : handleSubmit(item.text)
                        }
                        title={item.text || item.label}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>
              </section>
            ) : (
              <div
                id="empty-panel-cases"
                role="tabpanel"
                aria-labelledby="empty-tab-cases"
                className="quick-prompts"
              >
                <p className="quick-prompts-title">常用场景（点开分类后点击按钮发送）</p>
                {QUICK_PROMPT_GROUPS.map((group: QuickPromptGroup) => (
                  <details key={group.title} className="quick-prompts-details">
                    <summary className="quick-prompts-details-summary">
                      <span className="quick-prompts-details-title">{group.title}</span>
                      {group.hint ? (
                        <span className="quick-prompts-details-hint" title={group.hint}>
                          {group.hint}
                        </span>
                      ) : null}
                    </summary>
                    <div className="quick-prompts-details-body">
                      <div className="quick-prompts-grid">
                        {group.prompts.map((item: QuickPromptItem) => (
                          <button
                            key={`${group.title}-${item.label}`}
                            type="button"
                            className="quick-prompt-chip"
                            onClick={() =>
                              item.extensionName
                                ? void triggerExtensionAction(item.extensionName)
                                : handleSubmit(item.text)
                            }
                            title={item.text || item.label}
                          >
                            {item.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </details>
                ))}
              </div>
            )}
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
      <div ref={bottomRef} />
    </div>
  );
}
