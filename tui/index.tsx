/** COMSOL Agent TUI — OpenTUI + Solid.js（复刻 OpenCode 结构） */
import { writeFileSync } from "fs";
import { join } from "path";

const logError = (err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  const stack = err instanceof Error ? err.stack ?? "" : "";
  try {
    writeFileSync(
      join(import.meta.dir, "tui-error.log"),
      `${new Date().toISOString()}\n${msg}\n${stack}`,
      "utf8",
    );
  } catch {
    // ignore
  }
  console.error("[TUI Error]", msg, stack);
};
process.on("uncaughtException", logError);
process.on("unhandledRejection", logError);

import { render, useTerminalDimensions } from "@opentui/solid";
import { Switch, Match } from "solid-js";
import { RouteProvider, useRoute } from "./context/route";
import { ThemeProvider, useTheme } from "./context/theme";
import { TuiStateProvider } from "./context/state";
import { DialogProvider } from "./context/dialog";
import { CommandProvider } from "./context/command";
import { RegisterCommands } from "./RegisterCommands";
import { Home } from "./routes/Home";
import { Session } from "./routes/Session";

function App() {
  const dimensions = useTerminalDimensions();
  const route = useRoute();
  const { theme } = useTheme();

  return (
    <box
      width={dimensions().width}
      height={dimensions().height}
      backgroundColor={theme.background}
    >
      <Switch>
        <Match when={route.data().type === "home"}>
          <Home />
        </Match>
        <Match when={route.data().type === "session"}>
          <Session />
        </Match>
      </Switch>
    </box>
  );
}

render(
  () => (
    <RouteProvider>
      <ThemeProvider>
        <TuiStateProvider>
          <DialogProvider>
            <CommandProvider>
              <RegisterCommands />
              <App />
            </CommandProvider>
          </DialogProvider>
        </TuiStateProvider>
      </ThemeProvider>
    </RouteProvider>
  ),
  {
    exitOnCtrlC: false,
  },
);
