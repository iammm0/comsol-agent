import { useCallback } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { useAppState } from "../context/AppStateContext";

const WIN_CONTROL_CLASS = "titlebar-win-control";

export function TitleBar() {
  const { dispatch, sessionTitle, messages, state } = useAppState();

  const handleMinimize = useCallback(() => {
    getCurrentWindow().minimize();
  }, []);

  const handleToggleMaximize = useCallback(() => {
    getCurrentWindow().toggleMaximize();
  }, []);

  const handleClose = useCallback(() => {
    getCurrentWindow().close();
  }, []);

  return (
    <div className="titlebar">
      <div className="titlebar-left" data-tauri-drag-region>
        <span className="titlebar-icon" aria-hidden>◇</span>
        <span className="titlebar-title">多物理场建模智能体</span>
        <span className="titlebar-session" title={sessionTitle}>
          #{sessionTitle}
        </span>
      </div>
      <div className="titlebar-right">
        <button
          type="button"
          className={`titlebar-entry-btn ${state.view === "case-library" ? "active" : ""}`}
          onClick={() =>
            dispatch({
              type: "SET_VIEW",
              view: state.view === "case-library" ? "session" : "case-library",
            })
          }
          title="打开案例库技能系统"
          aria-label="打开案例库技能系统"
        >
          <span aria-hidden>📚</span>
          <span>案例库技能系统</span>
        </button>
        <span className="titlebar-badge" title="当前会话消息数">
          {messages.length} 条消息
        </span>
        <span className="titlebar-badge mode" title="当前模式">
          {state.mode === "discuss" ? "探讨" : state.mode === "plan" ? "规划" : "执行"}
        </span>
        <span className="titlebar-badge backend" title="当前 LLM 后端">
          {state.backend ?? "default"}
        </span>
        <button
          type="button"
          className="titlebar-action-btn"
          onClick={() => dispatch({ type: "SET_DIALOG", dialog: "settings" })}
          title="设置"
          aria-label="设置"
        >
          ⚙
        </button>
        <button
          type="button"
          className={WIN_CONTROL_CLASS}
          onClick={handleMinimize}
          title="最小化"
          aria-label="最小化"
        >
          <span className="titlebar-btn-icon">−</span>
        </button>
        <button
          type="button"
          className={WIN_CONTROL_CLASS}
          onClick={handleToggleMaximize}
          title="最大化 / 还原"
          aria-label="最大化"
        >
          <span className="titlebar-btn-icon">□</span>
        </button>
        <button
          type="button"
          className={`${WIN_CONTROL_CLASS} titlebar-close`}
          onClick={handleClose}
          title="关闭"
          aria-label="关闭"
        >
          <span className="titlebar-btn-icon">×</span>
        </button>
      </div>
    </div>
  );
}
