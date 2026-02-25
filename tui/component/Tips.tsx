import { createMemo, For } from "solid-js";
import { useTheme } from "../context/theme";

const TIPS = [
  "输入自然语言直接生成 COMSOL 模型",
  "使用 /plan 仅解析为 JSON，不执行",
  "使用 /doctor 检查环境与配置",
  "使用 /context 查看或清除对话历史",
  "使用 /backend 切换 LLM 后端",
  "使用 /help 查看全部命令",
];

function parse(tip: string): { text: string; highlight: boolean }[] {
  const parts: { text: string; highlight: boolean }[] = [];
  const regex = /\{highlight\}(.*?)\{\/highlight\}/g;
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(tip)) !== null) {
    if (m.index > lastIndex) {
      parts.push({ text: tip.slice(lastIndex, m.index), highlight: false });
    }
    parts.push({ text: m[1], highlight: true });
    lastIndex = m.index + m[0].length;
  }
  if (lastIndex < tip.length) {
    parts.push({ text: tip.slice(lastIndex), highlight: false });
  }
  return parts.length ? parts : [{ text: tip, highlight: false }];
}

export function Tips(props: { hidden?: boolean }) {
  const { theme } = useTheme();
  const tip = createMemo(() => TIPS[Math.floor(Math.random() * TIPS.length)]);
  const parts = createMemo(() => parse(tip()));

  if (props.hidden) return null;

  return (
    <box flexDirection="row" maxWidth="100%" gap={0}>
      <text flexShrink={0} fg={theme.warning}>
        {" "}
        ● Tip{" "}
      </text>
      <box flexDirection="row" flexShrink={1} flexWrap="wrap">
        <For each={parts()}>
          {(part) => (
            <text fg={part.highlight ? theme.text : theme.textMuted}>
              {part.text}
            </text>
          )}
        </For>
      </box>
    </box>
  );
}
