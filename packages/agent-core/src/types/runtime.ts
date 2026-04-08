import type {
  AgentRunState,
  BridgeEvent,
  BridgeRequest,
  BridgeResponse,
  CommandPayload,
  ComsolAction,
  RunArtifact
} from "@mph-agent/contracts";

export interface RuntimePaths {
  workspaceRoot: string;
  contextRoot: string;
  skillsRoot: string;
  promptsRoot: string;
  modelsRoot: string;
}

export interface RuntimeConfig {
  paths: RuntimePaths;
  defaultBackend: "ollama" | "deepseek" | "kimi" | "openai-compatible";
  defaultModel: string;
  defaultOllamaUrl: string;
}

export interface ConversationEntry {
  id: string;
  conversationId: string;
  timestamp: string;
  userInput: string;
  plan?: Record<string, unknown>;
  modelPath?: string;
  success: boolean;
  error?: string;
}

export interface ContextSummary {
  summary: string;
  lastUpdated: string;
  totalConversations: number;
  recentActions: string[];
  preferences: Record<string, string>;
}

export interface SkillDocument {
  id: string;
  name: string;
  description: string;
  tags: string[];
  triggers: string[];
  body: string;
  filePath: string;
}

export interface PlannerOutput {
  modelName: string;
  steps: Array<{
    stepId: string;
    label: string;
    action: ComsolAction;
  }>;
  clarifyingQuestions?: Array<{
    id: string;
    text: string;
    type: "single" | "multi";
    options: Array<{
      id: string;
      label: string;
      value: string;
      recommended?: boolean;
    }>;
  }>;
}

export interface ReActRunResult {
  ok: boolean;
  message: string;
  modelPath?: string;
  runState: AgentRunState;
  artifacts: RunArtifact[];
}

export type EventSink = (event: BridgeEvent) => void;

export interface ComsolRpcRequest {
  method: string;
  params: Record<string, unknown>;
}

export interface ComsolRpcResponse {
  ok: boolean;
  message: string;
  data?: Record<string, unknown>;
}

export type ComsolExecutor = (request: ComsolRpcRequest) => Promise<ComsolRpcResponse>;

export interface RuntimeCommandContext {
  request: BridgeRequest<CommandPayload>;
  emit: EventSink;
}

export type RuntimeCommandHandler = (
  context: RuntimeCommandContext
) => Promise<BridgeResponse<Record<string, unknown>>>;