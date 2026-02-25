import { useTheme } from "../context/theme";
import { useTuiState } from "../context/state";
import { useDialog } from "../context/dialog";

export function DialogOutput() {
  const { theme } = useTheme();
  const state = useTuiState();
  const dialog = useDialog();

  return (
    <box flexDirection="column" paddingBottom={1}>
      <box paddingLeft={2} paddingRight={2} paddingBottom={1}>
        <text fg={theme.text}>默认输出文件名</text>
      </box>
      <box paddingLeft={2} paddingRight={2}>
        <input
          placeholder=" 例如 model.mph"
          width="100%"
          focused={true}
          onSubmit={(v: unknown) => {
            const name = (typeof v === "string" ? v : "").trim() || null;
            state.setOutputDefault(name);
            dialog.clear();
            state.addMessage("system", "默认输出已设为: " + (name ?? "（未设置）"));
          }}
        />
      </box>
    </box>
  );
}
