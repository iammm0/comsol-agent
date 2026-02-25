import { createSignal, onCleanup, onMount } from "solid-js";
import { useTheme } from "../context/theme";

const FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

export function Spinner(props: { color?: string; children?: any }) {
  const { theme } = useTheme();
  const [frame, setFrame] = createSignal(0);

  onMount(() => {
    const timer = setInterval(() => {
      setFrame((f) => (f + 1) % FRAMES.length);
    }, 80);
    onCleanup(() => clearInterval(timer));
  });

  const color = () => props.color ?? theme.primary;

  return (
    <box flexDirection="row" gap={1} paddingLeft={3}>
      <text fg={color()}>{FRAMES[frame()]}</text>
      <text fg={theme.textMuted}>{props.children}</text>
    </box>
  );
}
