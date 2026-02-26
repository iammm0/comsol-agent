import { useCallback, useEffect } from "react";
import { useAppState } from "./context/AppStateContext";
import { Sidebar } from "./components/Sidebar";
import { Session } from "./components/Session";
import { DialogOverlay } from "./components/dialogs/DialogOverlay";
import { HelpDialog } from "./components/dialogs/HelpDialog";
import { BackendDialog } from "./components/dialogs/BackendDialog";
import { ContextDialog } from "./components/dialogs/ContextDialog";
import { ExecDialog } from "./components/dialogs/ExecDialog";
import { OutputDialog } from "./components/dialogs/OutputDialog";
import { SettingsDialog } from "./components/dialogs/SettingsDialog";

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
      case "settings":
        return <SettingsDialog onClose={closeDialog} />;
      default:
        return null;
    }
  })();

  return (
    <div className="app">
      <Sidebar />
      <div className="app-main">
        <Session />
      </div>
      {dialogContent && (
        <DialogOverlay onClose={closeDialog}>{dialogContent}</DialogOverlay>
      )}
    </div>
  );
}
