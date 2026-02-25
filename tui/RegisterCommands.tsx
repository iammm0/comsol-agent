import { onMount } from "solid-js";
import { useCommand } from "./context/command";
import { useDialog } from "./context/dialog";
import { useTuiState } from "./context/state";
import { DialogContext } from "./ui/DialogContext";
import { DialogBackend } from "./ui/DialogBackend";
import { DialogExec } from "./ui/DialogExec";
import { DialogOutput } from "./ui/DialogOutput";
import { DialogHelp } from "./ui/DialogHelp";

export function RegisterCommands() {
  const command = useCommand();
  const dialog = useDialog();
  const state = useTuiState();

  onMount(() => {
    command.register(() => [
    {
      title: "退出",
      value: "app.exit",
      category: "System",
      slash: { name: "exit", aliases: ["quit", "q"] },
      onSelect: () => process.exit(0),
    },
    {
      title: "默认模式",
      value: "mode.run",
      category: "Mode",
      slash: { name: "run" },
      onSelect: () => {
        state.setMode("run");
        state.addMessage("system", "已切换为默认模式（run）");
        dialog.clear();
      },
    },
    {
      title: "计划模式",
      value: "mode.plan",
      category: "Mode",
      slash: { name: "plan" },
      onSelect: () => {
        state.setMode("plan");
        state.addMessage("system", "已切换为计划模式（plan）");
        dialog.clear();
      },
    },
    {
      title: "帮助",
      value: "help",
      category: "System",
      slash: { name: "help" },
      onSelect: () => {
        dialog.replace(() => <DialogHelp />);
      },
    },
    {
      title: "演示",
      value: "demo",
      category: "Run",
      slash: { name: "demo" },
      onSelect: () => {
        state.handleBridge("demo");
        dialog.clear();
      },
    },
    {
      title: "环境诊断",
      value: "doctor",
      category: "Run",
      slash: { name: "doctor" },
      onSelect: () => {
        state.handleBridge("doctor");
        dialog.clear();
      },
    },
    {
      title: "上下文",
      value: "context",
      category: "Session",
      slash: { name: "context" },
      onSelect: () => dialog.replace(() => <DialogContext />),
    },
    {
      title: "LLM 后端",
      value: "backend",
      category: "Session",
      slash: { name: "backend" },
      onSelect: () => dialog.replace(() => <DialogBackend />),
    },
    {
      title: "执行 JSON 计划",
      value: "exec",
      category: "Run",
      slash: { name: "exec" },
      onSelect: () => dialog.replace(() => <DialogExec />),
    },
    {
      title: "默认输出文件名",
      value: "output",
      category: "Session",
      slash: { name: "output" },
      onSelect: () => dialog.replace(() => <DialogOutput />),
    },
  ]);
  });

  return <box height={0} flexShrink={0} />;
}
