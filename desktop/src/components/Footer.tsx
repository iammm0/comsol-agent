import { useAppState } from "../context/AppStateContext";

export function Footer() {
  const { state } = useAppState();

  const modeLabel = state.mode === "plan" ? "计划模式" : "默认模式";
  const backendLabel = state.backend ?? "default";

  return (
    <div className="footer">
      <span>COMSOL Agent</span>
      <div className="footer-right">
        <span className="footer-mode">
          <span className="dot">●</span> {modeLabel}
        </span>
        <span>{backendLabel}</span>
      </div>
    </div>
  );
}
