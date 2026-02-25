import { createMemo } from "solid-js";
import { useTheme } from "../../context/theme";
import { useTuiState } from "../../context/state";

export function Footer() {
  const { theme } = useTheme();
  const state = useTuiState();

  const modeLabel = createMemo(() =>
    state.mode() === "plan" ? "计划模式" : "默认模式",
  );
  const backendLabel = createMemo(() => state.backend() ?? "default");

  return (
    <box flexDirection="row" justifyContent="space-between" gap={1} flexShrink={0}>
      <text fg={theme.textMuted}>{process.cwd()}</text>
      <box gap={2} flexDirection="row" flexShrink={0}>
        <text fg={theme.text}>
          <text fg={theme.success}>•</text> {modeLabel()}
        </text>
        <text fg={theme.textMuted}>{backendLabel()}</text>
        <text fg={theme.textMuted}>/status</text>
      </box>
    </box>
  );
}
