import { createSignal, onCleanup, onMount, Show, type JSX } from "solid-js";
import { ChatTimeline } from "./components/ChatTimeline.js";
import { DialogHost } from "./components/Dialogs.js";
import { PromptInput } from "./components/PromptInput.js";
import { Sidebar } from "./components/Sidebar.js";
import { getBridgeInitStatus } from "./services/bridge.js";
import { useSessionStore } from "./stores/session-store.js";

export default function App(): JSX.Element {
  const store = useSessionStore();
  const isZh = (): boolean => store.state.locale === "zh";
  const [bridgeStatus, setBridgeStatus] = createSignal<{ ready: boolean; error: string | null }>({
    ready: true,
    error: null
  });

  onMount(() => {
    getBridgeInitStatus()
      .then((status) => setBridgeStatus(status))
      .catch((error) =>
        setBridgeStatus({
          ready: false,
          error: error instanceof Error ? error.message : String(error)
        })
      );

    const handler = (event: KeyboardEvent): void => {
      if (event.key === "Escape" && store.state.activeDialog) {
        store.setDialog(null);
      }
    };
    window.addEventListener("keydown", handler);
    onCleanup(() => {
      window.removeEventListener("keydown", handler);
    });
  });

  return (
    <div class="app-root">
      <header class="titlebar">
        <h1>mph-agent rewrite-ts</h1>
        <span>{store.sessionTitle()}</span>
      </header>

      <Show when={!bridgeStatus().ready && bridgeStatus().error}>
        <div class="bridge-error">
          {isZh() ? "Bridge 未就绪：" : "Bridge not ready: "}
          {bridgeStatus().error}
        </div>
      </Show>

      <div class="app-body">
        <Sidebar />
        <main class="main-panel">
          <div class="main-content">
            <ChatTimeline />
          </div>
          <PromptInput />
        </main>
      </div>

      <DialogHost />
    </div>
  );
}
