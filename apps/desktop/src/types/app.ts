import type { BridgeEvent } from "@mph-agent/contracts";

export type MessageRole = "user" | "assistant" | "system";
export type LocaleMode = "zh" | "en";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  success?: boolean;
  events?: BridgeEvent[];
  time: number;
  modelPath?: string | null;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
}

export type AppMode = "run" | "plan";

export type DialogType =
  | null
  | "help"
  | "backend"
  | "context"
  | "exec"
  | "output"
  | "settings"
  | "ops"
  | "api"
  | "planQuestions";

export interface ClarifyingOption {
  id: string;
  label: string;
  value: string;
  recommended?: boolean;
}

export interface ClarifyingQuestion {
  id: string;
  text: string;
  type: "single" | "multi";
  options: ClarifyingOption[];
}

export interface SlashCommandItem {
  name: string;
  display: string;
  description: string;
}

export const SLASH_COMMANDS: SlashCommandItem[] = [
  { name: "help", display: "/help", description: "Show help" },
  { name: "ops", display: "/ops", description: "Show COMSOL operation hints" },
  { name: "api", display: "/api", description: "List integrated COMSOL API wrappers" },
  { name: "run", display: "/run", description: "Switch to Build mode" },
  { name: "plan", display: "/plan", description: "Switch to Plan mode" },
  { name: "exec", display: "/exec", description: "Execute from JSON plan path" },
  { name: "backend", display: "/backend", description: "Choose LLM backend" },
  { name: "context", display: "/context", description: "Show or clear conversation context" },
  { name: "output", display: "/output", description: "Set default output filename" },
  { name: "settings", display: "/settings", description: "Open settings dialog" },
  { name: "demo", display: "/demo", description: "Run demo diagnostics" },
  { name: "doctor", display: "/doctor", description: "Run environment doctor" },
  { name: "exit", display: "/exit", description: "Exit app" }
];
