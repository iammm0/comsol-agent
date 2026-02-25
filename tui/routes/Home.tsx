import { createSignal, Show } from "solid-js";
import { useTheme } from "../context/theme";
import { useRoute } from "../context/route";
import { useTuiState } from "../context/state";
import { useCommand } from "../context/command";
import { Logo } from "../component/Logo";
import { Tips } from "../component/Tips";
import { Prompt } from "../component/Prompt";

export function Home() {
  const { theme } = useTheme();
  const route = useRoute();
  const state = useTuiState();
  const command = useCommand();
  const [tipsHidden, setTipsHidden] = createSignal(false);

  function handleSubmit(raw: string) {
    const line = raw.trim();
    if (line.startsWith("/")) {
      const cmd = line.toLowerCase().split(/\s/)[0];
      const found = command.slashes().find((s) => s.display.toLowerCase() === cmd);
      if (found) {
        found.onSelect();
        return;
      }
    }
    if (line) {
      state.handleSubmit(raw);
    }
    route.navigate({ type: "session" });
  }

  return (
    <>
      <box flexGrow={1} alignItems="center" paddingLeft={2} paddingRight={2}>
        <box flexGrow={1} minHeight={0} />
        <box height={4} minHeight={0} flexShrink={1} />
        <box flexShrink={0}>
          <Logo />
        </box>
        <box height={1} minHeight={0} flexShrink={1} />
        <box width="100%" maxWidth={120} zIndex={1000} paddingTop={1} flexShrink={0}>
          <Prompt
            onSubmit={handleSubmit}
            placeholder={' 输入建模需求，如 "创建一个热传导模型" …'}
            slashes={() => command.slashes()}
          />
        </box>
        <box
          height={4}
          minHeight={0}
          width="100%"
          maxWidth={120}
          alignItems="center"
          paddingTop={3}
          flexShrink={1}
        >
          <Show when={!tipsHidden()} fallback={<box />}>
            <Tips />
          </Show>
        </box>
        <box flexGrow={1} minHeight={0} />
      </box>
      <box
        paddingTop={1}
        paddingBottom={1}
        paddingLeft={2}
        paddingRight={2}
        flexDirection="row"
        flexShrink={0}
        gap={2}
      >
        <text fg={theme.textMuted}>{process.cwd()}</text>
        <box flexGrow={1} />
        <text fg={theme.textMuted}>v0.1.0</text>
      </box>
    </>
  );
}
