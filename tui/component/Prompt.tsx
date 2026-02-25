import type { InputRenderable, TextareaRenderable } from "@opentui/core";
import { createSignal, createMemo, Show, For, onMount, onCleanup, type JSX } from "solid-js";
import { useTheme } from "../context/theme";
import { useTuiState } from "../context/state";
import { EmptyBorder } from "./Border";

const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

// "return" = macOS/Linux, "enter" = Windows 终端可能报告
const PROMPT_KEYBINDINGS = [
  { name: "return", action: "submit" as const },
  { name: "enter", action: "submit" as const },
  { name: "return", meta: true, action: "newline" as const },
  { name: "enter", meta: true, action: "newline" as const },
];

export type SlashOption = { display: string; value: string; onSelect: () => void };

export type PromptProps = {
  visible?: boolean;
  disabled?: boolean;
  /** 单行用 input（Enter 默认提交），多行用 textarea */
  multiline?: boolean;
  onSubmit?: (value: string) => void;
  placeholder?: string;
  hint?: JSX.Element;
  slashes?: () => SlashOption[];
};

export function Prompt(props: PromptProps) {
  const { theme } = useTheme();
  const state = useTuiState();
  const [spinFrame, setSpinFrame] = createSignal(0);
  const [inputValue, setInputValue] = createSignal("");
  let inputRef: InputRenderable | TextareaRenderable | undefined;

  onMount(() => {
    const timer = setInterval(() => {
      setSpinFrame((f) => (f + 1) % SPINNER_FRAMES.length);
    }, 80);
    onCleanup(() => clearInterval(timer));
  });

  const highlight = createMemo(() => {
    return state.mode() === "plan" ? theme.warning : theme.primary;
  });

  const modeLabel = createMemo(() => {
    return state.mode() === "plan" ? "Plan" : "Build";
  });

  const backendLabel = createMemo(() => {
    const b = state.backend();
    return b ?? "default";
  });

  function handleSubmit() {
    if (props.disabled) return;
    const raw = inputRef?.plainText ?? "";
    const trimmed = raw.trim();
    props.onSubmit?.(trimmed);
    inputRef?.setText("");
    setInputValue("");
  }

  const slashFilter = createMemo(() => {
    const v = inputValue();
    if (!v.startsWith("/")) return "";
    return v.slice(1).toLowerCase();
  });

  const slashMatches = createMemo(() => {
    const filter = slashFilter();
    const list = props.slashes?.() ?? [];
    if (!filter) return list;
    return list.filter((s) => s.display.toLowerCase().includes(filter));
  });

  const showSlashList = createMemo(() => {
    return inputValue().startsWith("/") && slashMatches().length > 0;
  });

  if (props.visible === false) return null;

  return (
    <>
      <box>
        <box
          border={["left"]}
          borderColor={highlight()}
          customBorderChars={{
            ...EmptyBorder,
            vertical: "┃",
            bottomLeft: "╹",
          }}
        >
          <box
            paddingLeft={2}
            paddingRight={2}
            paddingTop={1}
            flexShrink={0}
            backgroundColor={theme.backgroundElement}
            flexGrow={1}
          >
            <Show
              when={props.multiline}
              fallback={
                <input
                  ref={(r) => {
                    inputRef = r;
                  }}
                  placeholder={props.placeholder ?? " 输入建模需求或 /命令 …"}
                  focused={true}
                  onSubmit={handleSubmit}
                  onInput={(v: string) => setInputValue(v)}
                />
              }
            >
              <textarea
                ref={(r) => {
                  inputRef = r;
                }}
                placeholder={props.placeholder ?? " 输入建模需求或 /命令 …"}
                minHeight={1}
                maxHeight={6}
                focused={true}
                keyBindings={PROMPT_KEYBINDINGS}
                keyAliasMap={{ enter: "return" }}
                onSubmit={handleSubmit}
                onContentChange={() => {
                  const v = inputRef?.plainText ?? "";
                  setInputValue(v);
                }}
              />
            </Show>
            <Show when={showSlashList()} fallback={<box />}>
              <box
                flexDirection="column"
                paddingTop={1}
                paddingBottom={1}
                maxHeight={8}
                flexShrink={0}
              >
                <For each={slashMatches()}>
                  {(opt) => (
                    <box
                      flexDirection="row"
                      paddingLeft={2}
                      paddingRight={2}
                      onMouseUp={() => {
                        opt.onSelect();
                        inputRef?.setText("");
                        setInputValue("");
                      }}
                    >
                      <text fg={theme.primary}>{opt.display}</text>
                      <text fg={theme.textMuted}> — 选择执行</text>
                    </box>
                  )}
                </For>
              </box>
            </Show>
            <box flexDirection="row" flexShrink={0} paddingTop={1} gap={1}>
              <text fg={highlight()}>{modeLabel()} </text>
              <text flexShrink={0} fg={theme.text}>
                {backendLabel()}
              </text>
            </box>
          </box>
        </box>
        <box
          height={1}
          border={["left"]}
          borderColor={highlight()}
          customBorderChars={{
            ...EmptyBorder,
            vertical: "╹",
          }}
        >
          <box
            height={1}
            border={["bottom"]}
            borderColor={theme.backgroundElement}
            customBorderChars={{
              ...EmptyBorder,
              horizontal: "▀",
            }}
          />
        </box>
        <box flexDirection="row" justifyContent="space-between">
          <Show
            when={state.busy()}
            fallback={
              <Show when={props.hint} fallback={<box />}>
                {props.hint}
              </Show>
            }
          >
            <box flexDirection="row" gap={1} flexGrow={1}>
              <box flexShrink={0} flexDirection="row" gap={1}>
                <text fg={theme.primary} marginLeft={1}>
                  [{SPINNER_FRAMES[spinFrame()]}]
                </text>
              </box>
              <box flexGrow={1} />
              <box flexDirection="row" gap={1}>
                <text fg={theme.text}>esc </text>
                <text fg={theme.textMuted}>interrupt</text>
              </box>
            </box>
          </Show>
          <Show when={!state.busy()} fallback={<box />}>
            <box gap={2} flexDirection="row">
              <box flexDirection="row" gap={1}>
                <text fg={theme.text}>ctrl+k </text>
                <text fg={theme.textMuted}>commands</text>
              </box>
            </box>
          </Show>
        </box>
      </box>
    </>
  );
}
