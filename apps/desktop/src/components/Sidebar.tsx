import { For, type JSX } from "solid-js";
import { sendCommand } from "../services/bridge.js";
import { useSessionStore } from "../stores/session-store.js";

export function Sidebar(): JSX.Element {
  const store = useSessionStore();
  const isZh = (): boolean => store.state.locale === "zh";

  const removeConversation = async (id: string): Promise<void> => {
    await sendCommand("conversation_delete", { conversation_id: id }, id).catch(() => {});
    store.deleteConversation(id);
  };

  return (
    <aside class="sidebar">
      <div class="sidebar-head">
        <h2>{isZh() ? "会话" : "Conversations"}</h2>
        <button class="btn" type="button" onClick={store.newConversation}>
          {isZh() ? "新建" : "New"}
        </button>
      </div>
      <div class="conversation-list">
        <For each={store.state.conversations}>
          {(conversation) => (
            <div
              class={`conversation-item ${
                store.state.currentConversationId === conversation.id ? "active" : ""
              }`}
            >
              <button
                type="button"
                class="conversation-title"
                onClick={() => store.switchConversation(conversation.id)}
              >
                {conversation.title}
              </button>
              <button
                type="button"
                class="conversation-delete"
                onClick={() => {
                  void removeConversation(conversation.id);
                }}
              >
                {isZh() ? "删除" : "Delete"}
              </button>
            </div>
          )}
        </For>
      </div>
      <div class="sidebar-footer">
        <button class="btn block" type="button" onClick={() => store.setDialog("settings")}>
          {isZh() ? "设置" : "Settings"}
        </button>
      </div>
    </aside>
  );
}
