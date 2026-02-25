import { useTheme } from "../context/theme";

export function Logo() {
  const { theme } = useTheme();
  return (
    <box flexShrink={0}>
      <text fg={theme.primary}>
        {" "}
        COMSOL Agent{" "}
      </text>
    </box>
  );
}
