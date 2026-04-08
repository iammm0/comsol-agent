import { describe, expect, it } from "vitest";
import {
  bridgeEventSchema,
  bridgeRequestSchema,
  bridgeResponseSchema,
  commandKeySchema,
  createRequest,
  createResponse
} from "../src/schema.js";

describe("contracts schema", () => {
  it("validates command enum", () => {
    expect(commandKeySchema.parse("run")).toBe("run");
    expect(() => commandKeySchema.parse("invalid")).toThrow();
  });

  it("round-trips request envelope", () => {
    const req = createRequest({
      id: "req-1",
      cmd: "run",
      payload: { input: "build a bracket" },
      conversationId: "conv-1"
    });
    const parsed = bridgeRequestSchema.parse(req);
    expect(parsed.id).toBe("req-1");
    expect(parsed.cmd).toBe("run");
  });

  it("round-trips response envelope", () => {
    const res = createResponse({
      id: "req-1",
      ok: true,
      message: "done",
      data: { modelPath: "models/a.mph" }
    });
    const parsed = bridgeResponseSchema.parse(res);
    expect(parsed.ok).toBe(true);
  });

  it("validates event envelope", () => {
    const event = {
      version: "v1",
      _event: true,
      runId: "run-1",
      type: "run_progress",
      ts: new Date().toISOString(),
      iteration: 1,
      data: {
        progress: 12,
        step: "planning"
      }
    };
    const parsed = bridgeEventSchema.parse(event);
    expect(parsed.type).toBe("run_progress");
  });
});
