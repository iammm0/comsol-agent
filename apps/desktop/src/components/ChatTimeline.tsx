import { For, Show, type JSX } from "solid-js";
import type { BridgeEvent } from "@mph-agent/contracts";
import { useSessionStore } from "../stores/session-store.js";

function eventLabel(event: BridgeEvent): string {
  if (event.type === "run_progress") {
    return `${String(event.data.step ?? "progress")} (${String(event.data.progress ?? 0)}%)`;
  }
  if (event.type === "action") {
    return `action: ${String(event.data.label ?? "")}`;
  }
  if (event.type === "observation") {
    return `observation: ${String(event.data.message ?? "")}`;
  }
  if (event.type === "run_failed") {
    return `failed: ${String(event.data.message ?? "")}`;
  }
  if (event.type === "run_completed") {
    return "completed";
  }
  return event.type;
}

export function ChatTimeline(): JSX.Element {
  const store = useSessionStore();

  return (
    <div class="timeline">
      <For each={store.messages()}>
        {(message) => (
          <div class={`message ${message.role}`}>
            <div class="message-head">
              <span>{message.role}</span>
              <Show when={typeof message.success === "boolean"}>
                <span class={message.success ? "status ok" : "status fail"}>
                  {message.success ? "ok" : "fail"}
                </span>
              </Show>
            </div>
            <div class="message-body">{message.text || "..."}</div>
            <Show when={(message.events?.length ?? 0) > 0}>
              <ul class="events">
                <For each={message.events}>{(event) => <li>{eventLabel(event)}</li>}</For>
              </ul>
            </Show>
            <Show when={message.modelPath}>
              <div class="model-path">model: {message.modelPath}</div>
            </Show>
          </div>
        )}
      </For>
    </div>
  );
}
