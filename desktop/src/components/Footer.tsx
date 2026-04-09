import { useAppState } from "../context/AppStateContext";

export function Footer() {
  const { state } = useAppState();

  const modeLabel =
    state.mode === "discuss" ? "Discuss" : state.mode === "plan" ? "Plan" : "Run";
  const backendLabel = state.backend ?? "default";

  return (
    <div className="footer">
      <span className="footer-left">
        多物理场建模智能体
        <span
          className="footer-workflow-hint"
          title="推荐顺序：探讨 → 规划 → 执行。也可随时用 /discuss、/plan、/run 切换，或直接建模。"
        >
          探讨→规划→执行（可任选入口）
        </span>
      </span>
      <div className="footer-right">
        <span className="footer-mode">
          <span className="dot">●</span> {modeLabel}
        </span>
        <span>{backendLabel}</span>
      </div>
    </div>
  );
}
