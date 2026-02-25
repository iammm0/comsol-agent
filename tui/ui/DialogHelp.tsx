import { useTheme } from "../context/theme";

export function DialogHelp() {
  const { theme } = useTheme();

  return (
    <box flexDirection="column" paddingBottom={1} gap={1}>
      <box paddingLeft={2} paddingRight={2}>
        <text fg={theme.text}>帮助</text>
      </box>
      <box paddingLeft={2} paddingRight={2} flexDirection="column" gap={1}>
        <text fg={theme.textMuted}>快捷键</text>
        <box paddingLeft={2} flexDirection="column">
          <text fg={theme.text}>ctrl+k    <text fg={theme.textMuted}>打开命令面板</text></text>
          <text fg={theme.text}>ctrl+c    <text fg={theme.textMuted}>退出 / 关闭对话框</text></text>
          <text fg={theme.text}>esc       <text fg={theme.textMuted}>关闭对话框 / 中断</text></text>
          <text fg={theme.text}>q         <text fg={theme.textMuted}>退出应用</text></text>
        </box>
        <text fg={theme.textMuted}>斜杠命令</text>
        <box paddingLeft={2} flexDirection="column">
          <text fg={theme.text}>/help     <text fg={theme.textMuted}>显示帮助</text></text>
          <text fg={theme.text}>/run      <text fg={theme.textMuted}>默认模式（自然语言 → 模型）</text></text>
          <text fg={theme.text}>/plan     <text fg={theme.textMuted}>计划模式（自然语言 → JSON）</text></text>
          <text fg={theme.text}>/exec     <text fg={theme.textMuted}>根据 JSON 创建模型</text></text>
          <text fg={theme.text}>/backend  <text fg={theme.textMuted}>选择 LLM 后端</text></text>
          <text fg={theme.text}>/context  <text fg={theme.textMuted}>查看或清除对话历史</text></text>
          <text fg={theme.text}>/output   <text fg={theme.textMuted}>设置默认输出文件名</text></text>
          <text fg={theme.text}>/demo     <text fg={theme.textMuted}>演示示例</text></text>
          <text fg={theme.text}>/doctor   <text fg={theme.textMuted}>环境诊断</text></text>
          <text fg={theme.text}>/exit     <text fg={theme.textMuted}>退出</text></text>
        </box>
      </box>
    </box>
  );
}
