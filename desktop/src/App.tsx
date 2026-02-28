import { useCallback, useEffect } from "react";
import { useAppState } from "./context/AppStateContext";
import { Sidebar } from "./components/Sidebar";
import { Session } from "./components/Session";
import { TitleBar } from "./components/TitleBar";
import { DialogOverlay } from "./components/dialogs/DialogOverlay";
import { HelpDialog } from "./components/dialogs/HelpDialog";
import { BackendDialog } from "./components/dialogs/BackendDialog";
import { ContextDialog } from "./components/dialogs/ContextDialog";
import { ExecDialog } from "./components/dialogs/ExecDialog";
import { OutputDialog } from "./components/dialogs/OutputDialog";
import { SettingsDialog } from "./components/dialogs/SettingsDialog";
import { ComsolOpsDialog } from "./components/dialogs/ComsolOpsDialog";

export default function App() {
  const { state, dispatch } = useAppState();

  const closeDialog = useCallback(() => {
    dispatch({ type: "SET_DIALOG", dialog: null });
  }, [dispatch]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && state.activeDialog) {
        closeDialog();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [state.activeDialog, closeDialog]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    void import("@tauri-apps/api/core")
      .then((m) => m.invoke("apply_window_icon"))
      .catch(() => {});
  }, []);

  const dialogContent = (() => {
    switch (state.activeDialog) {
      case "help":
        return <HelpDialog />;
      case "backend":
        return <BackendDialog onClose={closeDialog} />;
      case "context":
        return <ContextDialog onClose={closeDialog} />;
      case "exec":
        return <ExecDialog onClose={closeDialog} />;
      case "output":
        return <OutputDialog onClose={closeDialog} />;
      case "ops":
        return <ComsolOpsDialog onClose={closeDialog} />;
      case "settings":
        return <SettingsDialog onClose={closeDialog} />;
      default:
        return null;
    }
  })();

  return (
    <div className="app">
      <TitleBar />
      <div className="app-body">
        <Sidebar />
        <div className="app-main">
          <Session />
        </div>
      </div>
      {dialogContent && (
        <DialogOverlay onClose={closeDialog}>{dialogContent}</DialogOverlay>
      )}
    </div>
  );
}
