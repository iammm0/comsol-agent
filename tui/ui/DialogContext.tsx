import { useTheme } from "../context/theme";
import { useTuiState } from "../context/state";
import { useDialog } from "../context/dialog";

export function DialogContext() {
  const { theme } = useTheme();
  const state = useTuiState();
  const dialog = useDialog();

  return (
    <box flexDirection="column" paddingBottom={1}>
      <box paddingLeft={2} paddingRight={2} paddingBottom={1}>
        <text fg={theme.text}>上下文</text>
      </box>
      <select
        width="100%"
        height={6}
        focused={true}
        options={[
          { name: "查看摘要", description: "显示对话上下文摘要" },
          { name: "查看历史", description: "显示最近对话记录" },
          { name: "统计信息", description: "显示会话统计数据" },
          { name: "清除历史", description: "清除当前对话历史" },
        ]}
        onSelect={(_index: number, option: { name: string; description: string } | null) => {
          if (!option) return;
          const id =
            option.name === "查看摘要"
              ? "context_show"
              : option.name === "查看历史"
                ? "context_history"
                : option.name === "统计信息"
                  ? "context_stats"
                  : "context_clear";
          dialog.clear();
          state.handleBridge(id, id === "context_history" ? { limit: 10 } : {});
        }}
      />
    </box>
  );
}
