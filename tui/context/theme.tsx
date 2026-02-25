import { createContext, useContext, type ParentProps } from "solid-js";

export type Theme = {
  background: string;
  backgroundPanel: string;
  backgroundElement: string;
  backgroundMenu: string;
  text: string;
  textMuted: string;
  primary: string;
  secondary: string;
  accent: string;
  error: string;
  success: string;
  warning: string;
  border: string;
  borderActive: string;
  diffAdded: string;
  diffRemoved: string;
  diffAddedBg: string;
  diffRemovedBg: string;
  diffContextBg: string;
  diffHighlightAdded: string;
  diffHighlightRemoved: string;
  diffLineNumber: string;
  diffAddedLineNumberBg: string;
  diffRemovedLineNumberBg: string;
};

const DARK_THEME: Theme = {
  background: "#1a1b26",
  backgroundPanel: "#24283b",
  backgroundElement: "#414868",
  backgroundMenu: "#1f2335",
  text: "#c0caf5",
  textMuted: "#6c7086",
  primary: "#7aa2f7",
  secondary: "#bb9af7",
  accent: "#7dcfff",
  error: "#f7768e",
  success: "#9ece6a",
  warning: "#e0af68",
  border: "#414868",
  borderActive: "#7aa2f7",
  diffAdded: "#9ece6a",
  diffRemoved: "#f7768e",
  diffAddedBg: "#1a2b1a",
  diffRemovedBg: "#2b1a1a",
  diffContextBg: "#1a1b26",
  diffHighlightAdded: "#9ece6a",
  diffHighlightRemoved: "#f7768e",
  diffLineNumber: "#6c7086",
  diffAddedLineNumberBg: "#1a2b1a",
  diffRemovedLineNumberBg: "#2b1a1a",
};

const ThemeContext = createContext<{ theme: Theme } | undefined>(undefined);

export function ThemeProvider(props: ParentProps) {
  const value = { theme: DARK_THEME };
  return (
    <ThemeContext.Provider value={value}>
      {props.children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
