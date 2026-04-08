import { describe, expect, it } from "vitest";
import { createRequest } from "@mph-agent/contracts";
import { isAbsolute, join } from "node:path";
import { tmpdir } from "node:os";
import {
  AgentRuntime,
  createDefaultConfig,
  passthroughComsolExecutor
} from "../src/core/agent-runtime.js";

function testRoot(name: string): string {
  return join(tmpdir(), `mph-agent-test-${name}`);
}

describe("AgentRuntime", () => {
  it("handles plan command", async () => {
    const root = testRoot("plan");
    const runtime = new AgentRuntime({
      config: createDefaultConfig(root),
      comsolExecutor: passthroughComsolExecutor(root)
    });
    await runtime.init();

    const req = createRequest({
      id: "req-plan",
      cmd: "plan",
      payload: { input: "build a 3d bracket" },
      conversationId: "conv-1"
    });

    const res = await runtime.handle({
      request: req,
      emit: () => {}
    });

    expect(res.ok).toBe(true);
    expect(res.data?.plan).toBeTruthy();
  });

  it("emits run events and success response", async () => {
    const events: string[] = [];
    const root = testRoot("run");
    const runtime = new AgentRuntime({
      config: createDefaultConfig(root),
      comsolExecutor: passthroughComsolExecutor(root)
    });
    await runtime.init();

    const req = createRequest({
      id: "req-run",
      cmd: "run",
      payload: { input: "create a model and solve" },
      conversationId: "conv-2"
    });

    const res = await runtime.handle({
      request: req,
      emit: (event) => {
        events.push(event.type);
      }
    });

    expect(res.ok).toBe(true);
    expect(events.includes("run_started")).toBe(true);
    expect(events.includes("run_completed")).toBe(true);
    const modelPath = (res.data?.model_path as string | undefined) ?? "";
    expect(modelPath.length).toBeGreaterThan(0);
    expect(isAbsolute(modelPath)).toBe(true);
  });

  it("returns doctor diagnostics with comsol health", async () => {
    const root = testRoot("doctor");
    const runtime = new AgentRuntime({
      config: createDefaultConfig(root),
      comsolExecutor: passthroughComsolExecutor(root)
    });
    await runtime.init();

    const req = createRequest({
      id: "req-doctor",
      cmd: "doctor",
      payload: {},
      conversationId: "conv-3"
    });

    const res = await runtime.handle({
      request: req,
      emit: () => {}
    });

    expect(res.ok).toBe(true);
    expect(res.data?.comsol).toBeTruthy();
    expect((res.data?.comsol as { ok?: boolean }).ok).toBe(true);
  });
});
