import { useAppState } from "../context/AppStateContext";

export function Header() {
  const { state, dispatch, sessionTitle, messages } = useAppState();

  return (
    <div className="header">
      <span className="header-title"># {sessionTitle}</span>
      <div className="header-right">
        <span className="header-badge">{messages.length} 条消息</span>
        <button
          type="button"
          className="header-settings-btn"
          onClick={() => dispatch({ type: "SET_DIALOG", dialog: "settings" })}
          title="设置"
          aria-label="设置"
        >
          ⚙
        </button>
      </div>
    </div>
  );
}
