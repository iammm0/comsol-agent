import React from "react";
import ReactDOM from "react-dom/client";
import { AppStateProvider } from "./context/AppStateContext";
import { ThemeProvider, initTheme } from "./context/ThemeContext";
import App from "./App";
import "./App.css";

initTheme();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppStateProvider>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </AppStateProvider>
  </React.StrictMode>
);
