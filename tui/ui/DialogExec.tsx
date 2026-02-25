import { createSignal } from "solid-js";
import { useTheme } from "../context/theme";
import { useTuiState } from "../context/state";
import { useDialog } from "../context/dialog";

export function DialogExec() {
  const { theme } = useTheme();
  const state = useTuiState();
  const dialog = useDialog();
  const [step, setStep] = createSignal<"type" | "path">("type");
  const [codeOnly, setCodeOnly] = createSignal(false);

  return (
    <box flexDirection="column" paddingBottom={1}>
      <box paddingLeft={2} paddingRight={2} paddingBottom={1}>
        <text fg={theme.text}>
          {step() === "type" ? "执行方式" : "JSON 计划文件"}
        </text>
      </box>
      {step() === "type" && (
        <select
          width="100%"
          height={4}
          focused={true}
          options={[
            { name: "根据 JSON 文件创建模型", description: "完整执行" },
            { name: "仅生成 Java 代码", description: "只生成代码不执行" },
          ]}
          onSelect={(_index: number, option: { name: string; description: string } | null) => {
            if (!option) return;
            setCodeOnly(option.name.includes("仅生成"));
            setStep("path");
          }}
        />
      )}
      {step() === "path" && (
        <box paddingLeft={2} paddingRight={2}>
          <input
            placeholder=" 例如 plan.json"
            width="100%"
            focused={true}
            onSubmit={(v: unknown) => {
              const path = (typeof v === "string" ? v : "").trim();
              dialog.clear();
              if (path)
                state.handleBridge("exec", {
                  path,
                  code_only: codeOnly(),
                  output: state.outputDefault() ?? undefined,
                });
            }}
          />
        </box>
      )}
    </box>
  );
}
