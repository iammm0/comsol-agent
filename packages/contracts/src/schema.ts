import { z } from "zod";

export const PROTOCOL_VERSION = "v1" as const;

export const commandKeySchema = z.enum([
  "run",
  "plan",
  "exec",
  "demo",
  "doctor",
  "context_show",
  "context_get_summary",
  "context_set_summary",
  "context_history",
  "context_stats",
  "context_clear",
  "config_save",
  "ollama_ping",
  "models_list",
  "list_apis",
  "model_preview",
  "conversation_delete",
  "abort"
]);

export type CommandKey = z.infer<typeof commandKeySchema>;

export const bridgeErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
  details: z.unknown().optional()
});

export type BridgeError = z.infer<typeof bridgeErrorSchema>;

export const comsolActionSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("geometry.create"),
    feature: z.enum(["block", "cylinder", "sphere", "cone", "torus", "workplane"]),
    params: z.record(z.string(), z.union([z.string(), z.number(), z.boolean()]))
  }),
  z.object({
    type: z.literal("physics.add"),
    feature: z.enum(["heat_transfer", "solid_mechanics", "laminar_flow", "electromagnetic_waves"]),
    domainSelection: z.array(z.number().int().nonnegative()),
    params: z.record(z.string(), z.unknown()).optional()
  }),
  z.object({
    type: z.literal("mesh.generate"),
    feature: z.enum(["free_tetrahedral", "swept", "free_triangular"]),
    size: z.enum(["coarse", "normal", "fine", "custom"]),
    params: z.record(z.string(), z.unknown()).optional()
  }),
  z.object({
    type: z.literal("study.setup"),
    feature: z.enum(["stationary", "time_dependent", "frequency_domain", "eigenvalue"]),
    params: z.record(z.string(), z.unknown()).optional()
  }),
  z.object({
    type: z.literal("solve.run"),
    solver: z.enum(["default", "segregated", "fully_coupled"]),
    params: z.record(z.string(), z.unknown()).optional()
  }),
  z.object({
    type: z.literal("postprocess.export"),
    artifact: z.enum(["png", "csv", "txt", "report"]),
    params: z.record(z.string(), z.unknown()).optional()
  })
]);

export type ComsolAction = z.infer<typeof comsolActionSchema>;

export const commandPayloadSchema = z.object({
  input: z.string().optional(),
  output: z.string().optional(),
  output_path: z.string().optional(),
  path: z.string().optional(),
  verbose: z.boolean().optional(),
  backend: z.string().optional(),
  api_key: z.string().optional(),
  base_url: z.string().optional(),
  ollama_url: z.string().optional(),
  model: z.string().optional(),
  use_react: z.boolean().optional(),
  no_context: z.boolean().optional(),
  skip_check: z.boolean().optional(),
  limit: z.number().int().positive().optional(),
  offset: z.number().int().nonnegative().optional(),
  query: z.string().optional(),
  text: z.string().optional(),
  config: z.record(z.string(), z.string()).optional(),
  conversation_id: z.string().optional(),
  clarifying_answers: z.array(z.record(z.string(), z.unknown())).optional(),
  width: z.number().int().positive().optional(),
  height: z.number().int().positive().optional()
}).passthrough();

export type CommandPayload = z.infer<typeof commandPayloadSchema>;

export const bridgeRequestSchema = z.object({
  version: z.literal(PROTOCOL_VERSION),
  id: z.string().min(1),
  cmd: commandKeySchema,
  payload: commandPayloadSchema.default({}),
  conversationId: z.string().optional(),
  ts: z.string()
});

export type BridgeRequest<TPayload extends CommandPayload = CommandPayload> = Omit<
  z.infer<typeof bridgeRequestSchema>,
  "payload"
> & {
  payload: TPayload;
};

export const runFailureSchema = z.object({
  code: z.string(),
  message: z.string(),
  retriable: z.boolean().default(false)
});

export type RunFailure = z.infer<typeof runFailureSchema>;

export const runArtifactSchema = z.object({
  id: z.string(),
  runId: z.string(),
  kind: z.enum(["mph", "mesh_png", "result_csv", "report_md", "log"]),
  path: z.string(),
  mime: z.string(),
  createdAt: z.string()
});

export type RunArtifact = z.infer<typeof runArtifactSchema>;

export const runPhaseSchema = z.enum([
  "idle",
  "planning",
  "acting",
  "observing",
  "repairing",
  "completed",
  "failed",
  "cancelled"
]);

export type RunPhase = z.infer<typeof runPhaseSchema>;

export const agentRunStateSchema = z.object({
  runId: z.string(),
  phase: runPhaseSchema,
  progress: z.number().min(0).max(100),
  currentStep: z.string().optional(),
  modelPath: z.string().optional(),
  startedAt: z.string(),
  endedAt: z.string().optional(),
  failure: runFailureSchema.optional()
});

export type AgentRunState = z.infer<typeof agentRunStateSchema>;

export const eventTypeSchema = z.enum([
  "run_started",
  "run_progress",
  "thought",
  "action",
  "observation",
  "artifact",
  "plan_end",
  "run_completed",
  "run_failed",
  "log"
]);

export type EventType = z.infer<typeof eventTypeSchema>;

export const bridgeEventSchema = z.object({
  version: z.literal(PROTOCOL_VERSION),
  _event: z.literal(true),
  runId: z.string(),
  type: eventTypeSchema,
  ts: z.string(),
  iteration: z.number().int().nonnegative().optional(),
  data: z.record(z.string(), z.unknown()).default({})
});

export type BridgeEvent<TType extends EventType = EventType> = Omit<
  z.infer<typeof bridgeEventSchema>,
  "type"
> & {
  type: TType;
};

export const bridgeResponseSchema = z.object({
  version: z.literal(PROTOCOL_VERSION),
  id: z.string().min(1),
  ok: z.boolean(),
  message: z.string(),
  data: z.unknown().optional(),
  error: bridgeErrorSchema.optional(),
  ts: z.string()
});

export type BridgeResponse<TData = unknown> = Omit<z.infer<typeof bridgeResponseSchema>, "data"> & {
  data?: TData;
};

export function createRequest<TPayload extends CommandPayload>(
  input: Omit<BridgeRequest<TPayload>, "version" | "ts">
): BridgeRequest<TPayload> {
  return {
    ...input,
    version: PROTOCOL_VERSION,
    ts: new Date().toISOString()
  };
}

export function createResponse<TData>(
  input: Omit<BridgeResponse<TData>, "version" | "ts">
): BridgeResponse<TData> {
  return {
    ...input,
    version: PROTOCOL_VERSION,
    ts: new Date().toISOString()
  };
}
