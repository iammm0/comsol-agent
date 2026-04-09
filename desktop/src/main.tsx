import React from "react";
import ReactDOM from "react-dom/client";
import { MathJaxContext } from "better-react-mathjax";
import { AppStateProvider } from "./context/AppStateContext";
import { ThemeProvider, initTheme } from "./context/ThemeContext";
import App from "./App";
import "./App.css";

initTheme();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MathJaxContext
      version={3}
      config={{
        loader: { load: ["[tex]/ams"] },
        tex: {
          inlineMath: [
            ["$", "$"],
            ["\\(", "\\)"],
          ],
          displayMath: [
            ["$$", "$$"],
            ["\\[", "\\]"],
          ],
          packages: { "[+]": ["ams"] },
        },
      }}
    >
      <AppStateProvider>
        <ThemeProvider>
          <App />
        </ThemeProvider>
      </AppStateProvider>
    </MathJaxContext>
  </React.StrictMode>
);
