import { createMemo, createSignal, For, Show, type JSX } from "solid-js";
import type { BridgeEvent } from "@mph-agent/contracts";
import { abortBridgeRun, listenBridgeEvents, sendCommand, sendStreamCommand } from "../services/bridge.js";
import { getPayloadFromConfig, loadApiConfig } from "../lib/api-config.js";
import { useSessionStore } from "../stores/session-store.js";
import { SLASH_COMMANDS, type ClarifyingOption, type ClarifyingQuestion } from "../types/app.js";

function normalizeOption(raw: unknown, index: number): ClarifyingOption | null {
  if (typeof raw !== "object" || raw === null) {
    return null;
  }
  const item = raw as Record<string, unknown>;
  const base: ClarifyingOption = {
    id: String(item.id ?? `opt_${index + 1}`),
    label: String(item.label ?? item.value ?? `Option ${index + 1}`),
    value: String(item.value ?? item.id ?? `opt_${index + 1}`)
  };
  if (typeof item.recommended === "boolean") {
    return {
      ...base,
      recommended: item.recommended
    };
  }
  return base;
}

function normalizePlanQuestions(raw: unknown): ClarifyingQuestion[] {
  if (!Array.isArray(raw)) {
    return [];
  }

  return raw
    .map((question, index): ClarifyingQuestion | null => {
      if (typeof question !== "object" || question === null) {
        return null;
      }
      const record = question as Record<string, unknown>;
      const options = Array.isArray(record.options)
        ? record.options
            .map((option, optionIndex) => normalizeOption(option, optionIndex))
            .filter((option): option is ClarifyingOption => option !== null)
        : [];

      return {
        id: String(record.id ?? `q_${index + 1}`),
        text: String(record.text ?? `Question ${index + 1}`),
        type: record.type === "multi" ? "multi" : "single",
        options
      };
    })
    .filter((item): item is ClarifyingQuestion => item !== null);
}

export function PromptInput(): JSX.Element {
  const store = useSessionStore();
  const [value, setValue] = createSignal("");
  const [showSlash, setShowSlash] = createSignal(false);
  const [slashIndex, setSlashIndex] = createSignal(0);
  const isZh = createMemo(() => store.state.locale === "zh");
  let unlisten: (() => void) | null = null;

  const filteredSlash = createMemo(() => {
    const input = value().trim();
    if (!input.startsWith("/")) {
      return [] as typeof SLASH_COMMANDS;
    }
    const first = input.toLowerCase().split(/\s/, 1)[0] ?? "";
    return SLASH_COMMANDS.filter((command) => command.display.startsWith(first));
  });

  const submitLine = async (): Promise<void> => {
    const line = value().trim();
    if (!line || store.state.busyConversationId) {
      return;
    }

    const conversationId = store.state.currentConversationId;
    if (!conversationId) {
      return;
    }

    if (line.startsWith("/")) {
      await handleSlash(line, conversationId);
      setValue("");
      setShowSlash(false);
      return;
    }

    store.addMessage("user", line);
    store.setLastPlanInput(line);
    const userCount = store.messages().filter((message) => message.role === "user").length;
    if (userCount <= 1) {
      store.renameConversation(
        conversationId,
        line.length > 50 ? `${line.slice(0, 47)}...` : line
      );
    }

    if (store.state.mode === "plan") {
      store.setBusyConversation(conversationId);
      const apiPayload = getPayloadFromConfig(store.state.backend, loadApiConfig());
      const response = await sendCommand("plan", { input: line, ...apiPayload }, conversationId);
      store.addMessage("assistant", response.message, { success: response.ok });
      store.setBusyConversation(null);
      return;
    }

    store.setBusyConversation(conversationId);
    store.addMessage("assistant", "", { events: [] });

    unlisten?.();
    unlisten = await listenBridgeEvents((event: BridgeEvent) => {
      store.appendEvent(conversationId, event);
      if (event.type === "plan_end") {
        const requiresClarification = Boolean(event.data.requires_clarification);
        if (requiresClarification) {
          const questions = normalizePlanQuestions(event.data.clarifying_questions);
          if (questions.length > 0) {
            store.setPendingPlanQuestions(questions);
            store.setDialog("planQuestions");
          }
        }
      }
    });

    const backend = store.state.backend;
    const output = store.state.outputDefault;
    const apiPayload = getPayloadFromConfig(backend, loadApiConfig());

    const response = await sendStreamCommand(
      "run",
      {
        input: line,
        use_react: true,
        no_context: false,
        ...(output ? { output } : {}),
        ...(backend ? { backend } : {}),
        ...apiPayload
      },
      conversationId
    );

    store.finalizeLast(conversationId, response.message, response.ok);
    store.setBusyConversation(null);
    setValue("");
    setShowSlash(false);
    unlisten?.();
    unlisten = null;
  };

  const handleSlash = async (line: string, conversationId: string): Promise<void> => {
    const cmd = line.toLowerCase().split(/\s/, 1)[0] ?? "";
    if (cmd === "/quit" || cmd === "/exit") {
      window.close();
      return;
    }
    if (cmd === "/run") {
      store.setMode("run");
      store.addMessage("system", isZh() ? "已切换到构建模式" : "Switched to Build mode");
      return;
    }
    if (cmd === "/plan") {
      store.setMode("plan");
      store.addMessage("system", isZh() ? "已切换到计划模式" : "Switched to Plan mode");
      return;
    }
    if (cmd === "/help") {
      store.setDialog("help");
      return;
    }
    if (cmd === "/ops") {
      store.setDialog("ops");
      return;
    }
    if (cmd === "/api") {
      store.setDialog("api");
      return;
    }
    if (cmd === "/backend") {
      store.setDialog("backend");
      return;
    }
    if (cmd === "/context") {
      store.setDialog("context");
      return;
    }
    if (cmd === "/exec") {
      store.setDialog("exec");
      return;
    }
    if (cmd === "/output") {
      store.setDialog("output");
      return;
    }
    if (cmd === "/settings") {
      store.setDialog("settings");
      return;
    }
    if (cmd === "/demo") {
      store.addMessage("user", line);
      store.setBusyConversation(conversationId);
      const response = await sendCommand("demo", {}, conversationId);
      store.addMessage("assistant", response.message, { success: response.ok });
      store.setBusyConversation(null);
      return;
    }
    if (cmd === "/doctor") {
      store.addMessage("user", line);
      store.setBusyConversation(conversationId);
      const response = await sendCommand("doctor", {}, conversationId);
      store.addMessage("assistant", response.message, { success: response.ok });
      store.setBusyConversation(null);
      return;
    }
    store.addMessage("system", isZh() ? `未知命令: ${cmd}` : `Unknown command: ${cmd}`, {
      success: false
    });
  };

  return (
    <div class="prompt-area">
      <Show when={showSlash() && filteredSlash().length > 0}>
        <div class="slash-dropdown">
          <For each={filteredSlash()}>
            {(command, index) => (
              <button
                type="button"
                class={`slash-item ${index() === slashIndex() ? "active" : ""}`}
                onMouseEnter={() => setSlashIndex(index())}
                onClick={() => {
                  setValue(command.display);
                }}
              >
                <span>{command.display}</span>
                <small>{command.description}</small>
              </button>
            )}
          </For>
        </div>
      </Show>
      <div class="prompt-row">
        <button
          type="button"
          class={`mode-tag ${store.state.mode === "plan" ? "plan" : "run"}`}
          onClick={() => store.setMode(store.state.mode === "plan" ? "run" : "plan")}
        >
          {store.state.mode === "plan" ? (isZh() ? "计划" : "Plan") : isZh() ? "构建" : "Build"}
        </button>
        <textarea
          class="prompt-input"
          value={value()}
          rows={1}
          placeholder={
            isZh()
              ? "输入 COMSOL 建模需求，或使用 / 命令..."
              : "Describe COMSOL modeling requirements or use /commands..."
          }
          disabled={store.state.busyConversationId !== null}
          onInput={(event) => {
            const target = event.currentTarget;
            setValue(target.value);
            setShowSlash(target.value.startsWith("/") && filteredSlash().length > 0);
            target.style.height = "auto";
            target.style.height = `${Math.min(target.scrollHeight, 220)}px`;
          }}
          onKeyDown={(event) => {
            if (showSlash() && filteredSlash().length > 0) {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setSlashIndex((current) => Math.min(current + 1, filteredSlash().length - 1));
                return;
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setSlashIndex((current) => Math.max(current - 1, 0));
                return;
              }
              if (event.key === "Tab") {
                event.preventDefault();
                const selected = filteredSlash()[slashIndex()];
                if (selected) {
                  setValue(selected.display);
                }
                return;
              }
            }
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submitLine();
            }
          }}
        />
        <button
          type="button"
          class="btn send"
          disabled={store.state.busyConversationId !== null || value().trim().length === 0}
          onClick={() => {
            void submitLine();
          }}
        >
          {isZh() ? "发送" : "Send"}
        </button>
        <Show when={store.state.busyConversationId !== null}>
          <button
            type="button"
            class="btn stop"
            onClick={() => {
              void abortBridgeRun();
              const busyId = store.state.busyConversationId;
              if (busyId) {
                store.finalizeLast(busyId, isZh() ? "已中止运行" : "Run aborted", false);
              }
              store.setBusyConversation(null);
            }}
          >
            {isZh() ? "停止" : "Stop"}
          </button>
        </Show>
      </div>
    </div>
  );
}
