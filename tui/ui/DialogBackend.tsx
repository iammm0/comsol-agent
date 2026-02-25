import { useTheme } from "../context/theme";
import { useTuiState } from "../context/state";
import { useDialog } from "../context/dialog";

export function DialogBackend() {
  const { theme } = useTheme();
  const state = useTuiState();
  const dialog = useDialog();

  return (
    <box flexDirection="column" paddingBottom={1}>
      <box paddingLeft={2} paddingRight={2} paddingBottom={1}>
        <text fg={theme.text}>LLM 后端</text>
      </box>
      <select
        width="100%"
        height={6}
        focused={true}
        options={[
          { name: "DeepSeek", description: "DeepSeek API" },
          { name: "Kimi", description: "Moonshot Kimi" },
          { name: "Ollama", description: "本地 Ollama" },
          { name: "OpenAI 兼容中转", description: "自定义 OpenAI 兼容 API" },
        ]}
        onSelect={(_index: number, option: { name: string; description: string } | null) => {
          if (!option) return;
          const id =
            option.name === "DeepSeek"
              ? "deepseek"
              : option.name === "Kimi"
                ? "kimi"
                : option.name === "Ollama"
                  ? "ollama"
                  : "openai-compatible";
          state.setBackend(id);
          dialog.clear();
          state.addMessage("system", "已选择后端: " + id);
        }}
      />
    </box>
  );
}
