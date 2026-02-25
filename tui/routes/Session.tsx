import { For, Switch, Match, Show, createSignal, createMemo } from "solid-js";
import { useTheme } from "../context/theme";
import { useTuiState, type ChatMessage } from "../context/state";
import { useCommand } from "../context/command";
import { Prompt } from "../component/Prompt";
import { SplitBorder, EmptyBorder } from "../component/Border";
import { Spinner } from "../component/Spinner";
import { Header } from "./session/Header";
import { Footer } from "./session/Footer";

export function Session() {
  const { theme } = useTheme();
  const state = useTuiState();
  const command = useCommand();

  function handleSubmit(raw: string) {
    const line = raw.trim();
    if (!line) return;
    if (line.startsWith("/")) {
      const cmd = line.toLowerCase().split(/\s/)[0];
      const found = command.slashes().find((s) => s.display.toLowerCase() === cmd);
      if (found) {
        found.onSelect();
        return;
      }
    }
    state.handleSubmit(raw);
  }

  return (
    <box flexGrow={1} paddingBottom={1} paddingTop={1} paddingLeft={2} paddingRight={2} gap={1}>
      <Header />
      <scrollbox
        flexGrow={1}
        stickyScroll={true}
        stickyStart="bottom"
      >
        <For each={state.messages()}>
          {(message, index) => (
            <Switch>
              <Match when={message.role === "user"}>
                <UserMessage message={message} index={index()} />
              </Match>
              <Match when={message.role === "assistant"}>
                <AssistantMessage message={message} />
              </Match>
              <Match when={message.role === "system"}>
                <SystemMessage message={message} />
              </Match>
            </Switch>
          )}
        </For>
        <Show when={state.busy()}>
          <box marginTop={1}>
            <Spinner>处理中...</Spinner>
          </box>
        </Show>
      </scrollbox>
      <box flexShrink={0}>
        <Prompt
          multiline={true}
          onSubmit={handleSubmit}
          hint={
            <box gap={2} flexDirection="row">
              <box flexDirection="row" gap={1}>
                <text fg={theme.text}>ctrl+k </text>
                <text fg={theme.textMuted}>commands</text>
              </box>
            </box>
          }
          slashes={() => command.slashes()}
        />
      </box>
      <Footer />
    </box>
  );
}

function UserMessage(props: { message: ChatMessage; index: number }) {
  const { theme } = useTheme();
  const [hover, setHover] = createSignal(false);

  return (
    <box
      id={props.message.id}
      border={["left"]}
      borderColor={theme.primary}
      customBorderChars={SplitBorder.customBorderChars}
      marginTop={props.index === 0 ? 0 : 1}
    >
      <box
        onMouseOver={() => setHover(true)}
        onMouseOut={() => setHover(false)}
        paddingTop={1}
        paddingBottom={1}
        paddingLeft={2}
        backgroundColor={hover() ? theme.backgroundElement : theme.backgroundPanel}
        flexShrink={0}
      >
        <text fg={theme.text}>{props.message.text}</text>
      </box>
    </box>
  );
}

function AssistantMessage(props: { message: ChatMessage }) {
  const { theme } = useTheme();

  const isError = createMemo(() => props.message.success === false);
  const hasEvents = createMemo(() => (props.message.events?.length ?? 0) > 0);

  return (
    <box marginTop={1} flexDirection="column" gap={1}>
      <Show when={hasEvents()}>
        <box flexDirection="column" gap={1}>
          <For each={props.message.events ?? []}>
            {(evt) => <RunEventBlock event={evt} theme={theme} />}
          </For>
        </box>
      </Show>
      <Show when={isError()}>
        <box
          border={["left"]}
          paddingTop={1}
          paddingBottom={1}
          paddingLeft={2}
          backgroundColor={theme.backgroundPanel}
          customBorderChars={SplitBorder.customBorderChars}
          borderColor={theme.error}
        >
          <text fg={theme.error}>{props.message.text}</text>
        </box>
      </Show>
      <Show when={!isError() && (props.message.text || !hasEvents())}>
        <box paddingLeft={3} flexDirection="column" gap={0}>
          <box flexDirection="row" gap={1}>
            <text fg={theme.text}>{props.message.text || "处理中..."}</text>
          </box>
          <box flexDirection="row" gap={1} marginTop={1}>
            <text fg={theme.primary}>▣ </text>
            <text fg={theme.textMuted}>{formatTime(props.message.time)}</text>
          </box>
        </box>
      </Show>
    </box>
  );
}

function RunEventBlock(props: { event: { type: string; data: Record<string, unknown>; iteration?: number }; theme: ReturnType<typeof useTheme>["theme"] }) {
  const { event, theme } = props;
  const borderColor =
    event.type === "plan_start" || event.type === "plan_end"
      ? theme.accent
      : event.type === "think_chunk"
        ? theme.primary
        : event.type.startsWith("action") || event.type === "exec_result"
          ? theme.secondary
          : event.type === "error"
            ? theme.error
            : theme.textMuted;

  const label = () => {
    if (event.type === "plan_start") return "规划开始";
    if (event.type === "plan_end") return "规划完成";
    if (event.type === "task_phase") return `迭代 ${event.data.iteration ?? event.iteration ?? "?"}`;
    if (event.type === "think_chunk") return "思考";
    if (event.type === "action_start") return "执行";
    if (event.type === "action_end") return "完成";
    if (event.type === "exec_result") return "结果";
    if (event.type === "observation") return "观察";
    if (event.type === "content") return "内容";
    if (event.type === "error") return "错误";
    return event.type;
  };

  const content = () => {
    const d = event.data;
    if (event.type === "plan_start") return String(d.user_input ?? "");
    if (event.type === "plan_end") {
      const steps = d.steps as Array<{ action?: string; step_type?: string }> | undefined;
      const model = d.model_name ?? "";
      if (steps?.length) return `${model} · ${steps.length} 步: ${steps.map((s) => s.action ?? s.step_type).join(" → ")}`;
      return String(model);
    }
    if (event.type === "task_phase") return String(d.phase ?? "");
    if (event.type === "think_chunk") {
      const t = d.thought as Record<string, unknown> | undefined;
      if (!t) return "";
      const action = t.action ?? "";
      const reasoning = t.reasoning ?? "";
      return [action, reasoning].filter(Boolean).join(" — ");
    }
    if (event.type === "action_start") {
      const t = d.thought as Record<string, unknown> | undefined;
      return t ? String(t.action ?? JSON.stringify(t)) : "";
    }
    if (event.type === "action_end") return String(d.action ?? "完成");
    if (event.type === "exec_result") {
      const r = d.result as Record<string, unknown> | undefined;
      return r ? String(r.status ?? r.message ?? JSON.stringify(r)) : "";
    }
    if (event.type === "observation") return String(d.observation ?? d.message ?? "");
    if (event.type === "content") return String(d.content ?? "");
    if (event.type === "error") return String(d.message ?? "");
    return JSON.stringify(d).slice(0, 120);
  };

  return (
    <box
      border={["left"]}
      borderColor={borderColor}
      customBorderChars={{ ...EmptyBorder, vertical: "┃" }}
      paddingLeft={2}
      paddingTop={1}
      paddingBottom={1}
      backgroundColor={theme.backgroundPanel}
    >
      <box flexDirection="column" gap={0}>
        <box flexDirection="row" gap={1}>
          <text fg={theme.primary}>{label()}</text>
          <Show when={event.iteration != null}>
            <text fg={theme.textMuted}>#{event.iteration}</text>
          </Show>
        </box>
        <Show when={content()}>
          <box flexDirection="row" gap={1} marginTop={1}>
            <text fg={theme.text} wrapMode="word">{content()}</text>
          </box>
        </Show>
      </box>
    </box>
  );
}

function SystemMessage(props: { message: ChatMessage }) {
  const { theme } = useTheme();
  return (
    <box paddingLeft={3} marginTop={1}>
      <text fg={props.message.success === false ? theme.error : theme.textMuted}>
        {props.message.text}
      </text>
    </box>
  );
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
