import { createMemo } from "solid-js";
import { useTheme } from "../../context/theme";
import { useTuiState } from "../../context/state";
import { SplitBorder } from "../../component/Border";

export function Header() {
  const { theme } = useTheme();
  const state = useTuiState();

  const title = createMemo(() => state.sessionTitle());
  const messageCount = createMemo(() => state.messages().length);

  return (
    <box flexShrink={0}>
      <box
        paddingTop={1}
        paddingBottom={1}
        paddingLeft={2}
        paddingRight={1}
        border={["left"]}
        borderColor={theme.border}
        customBorderChars={SplitBorder.customBorderChars}
        flexShrink={0}
        backgroundColor={theme.backgroundPanel}
      >
        <box flexDirection="row" justifyContent="space-between" gap={1}>
          <text fg={theme.text}>
            <text fg={theme.text}># </text>
            <text fg={theme.text}>{title()}</text>
          </text>
          <text fg={theme.textMuted} wrapMode="none" flexShrink={0}>
            {messageCount()} 条消息
          </text>
        </box>
      </box>
    </box>
  );
}
