import { render } from "solid-js/web";
import App from "./App.js";
import { SessionStoreProvider } from "./stores/session-store.js";
import "./styles.css";

render(
  () => (
    <SessionStoreProvider>
      <App />
    </SessionStoreProvider>
  ),
  document.getElementById("root") as HTMLElement
);
