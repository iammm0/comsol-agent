import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomUUID } from "node:crypto";
import { dirname, isAbsolute, resolve } from "node:path";
import readline from "node:readline";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import {
  createRequest,
  type BridgeEvent,
  type BridgeResponse,
  type CommandKey,
  type CommandPayload
} from "@mph-agent/contracts";

interface ReadyEnvelope {
  _ready: true;
  ts?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isReadyEnvelope(value: unknown): value is ReadyEnvelope {
  return isRecord(value) && value._ready === true;
}

function isBridgeEvent(value: unknown): value is BridgeEvent {
  return isRecord(value) && value._event === true && typeof value.type === "string";
}

function isBridgeResponse(value: unknown): value is BridgeResponse<Record<string, unknown>> {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.ok === "boolean" &&
    typeof value.message === "string"
  );
}

class JsonMessageQueue {
  private readonly items: unknown[] = [];
  private readonly waiters: Array<(value: unknown) => void> = [];

  public push(value: unknown): void {
    const waiter = this.waiters.shift();
    if (waiter) {
      waiter(value);
      return;
    }
    this.items.push(value);
  }

  public async next(timeoutMs: number): Promise<unknown> {
    if (this.items.length > 0) {
      return this.items.shift();
    }

    return new Promise<unknown>((resolve, reject) => {
      const timer = setTimeout(() => {
        const index = this.waiters.indexOf(waiter);
        if (index >= 0) {
          this.waiters.splice(index, 1);
        }
        reject(new Error(`Timed out waiting for sidecar message after ${timeoutMs}ms`));
      }, timeoutMs);

      const waiter = (value: unknown): void => {
        clearTimeout(timer);
        resolve(value);
      };
      this.waiters.push(waiter);
    });
  }
}

class SidecarHarness {
  private readonly child: ChildProcessWithoutNullStreams;
  private readonly queue = new JsonMessageQueue();
  private readonly lineReader: readline.Interface;

  private constructor(child: ChildProcessWithoutNullStreams) {
    this.child = child;
    this.child.stdout.setEncoding("utf8");
    this.child.stderr.setEncoding("utf8");
    this.lineReader = readline.createInterface({
      input: this.child.stdout,
      crlfDelay: Number.POSITIVE_INFINITY
    });
    this.lineReader.on("line", (line) => {
      const trimmed = line.trim();
      if (!trimmed) {
        return;
      }
      try {
        this.queue.push(JSON.parse(trimmed) as unknown);
      } catch {
        // Ignore malformed stdout lines.
      }
    });
  }

  public static async start(): Promise<SidecarHarness> {
    const testDir = dirname(fileURLToPath(import.meta.url));
    const packageRoot = resolve(testDir, "..");
    const workspaceRoot = resolve(packageRoot, "..", "..");

    const child = spawn(process.execPath, ["dist/index.js"], {
      cwd: packageRoot,
      stdio: ["pipe", "pipe", "pipe"],
      env: {
        ...process.env,
        MPH_AGENT_ROOT: workspaceRoot,
        MPH_AGENT_MOCK_COMSOL: "1"
      }
    });

    const harness = new SidecarHarness(child);
    const ready = await harness.queue.next(8_000);
    if (!isReadyEnvelope(ready)) {
      await harness.stop();
      throw new Error("Sidecar did not emit ready envelope");
    }
    return harness;
  }

  public async send(
    cmd: CommandKey,
    payload: CommandPayload
  ): Promise<{
    response: BridgeResponse<Record<string, unknown>>;
    events: BridgeEvent[];
  }> {
    const request = createRequest({
      id: randomUUID(),
      cmd,
      payload
    });

    this.child.stdin.write(`${JSON.stringify(request)}\n`);

    const events: BridgeEvent[] = [];
    const deadline = Date.now() + 20_000;

    while (Date.now() < deadline) {
      const remaining = Math.max(100, deadline - Date.now());
      const message = await this.queue.next(remaining);
      if (isBridgeEvent(message)) {
        events.push(message);
        continue;
      }
      if (isBridgeResponse(message) && message.id === request.id) {
        return {
          response: message,
          events
        };
      }
    }

    throw new Error("Timed out waiting for matching sidecar response");
  }

  public async stop(): Promise<void> {
    this.lineReader.close();
    if (!this.child.killed) {
      this.child.kill();
    }
    await new Promise((resolve) => {
      this.child.once("exit", () => resolve(undefined));
      setTimeout(() => resolve(undefined), 2_000);
    });
  }
}

let harness: SidecarHarness | null = null;

afterEach(async () => {
  if (harness) {
    await harness.stop();
    harness = null;
  }
});

describe("agent-sidecar integration", () => {
  it("returns plan output for plan command", async () => {
    harness = await SidecarHarness.start();
    const { response, events } = await harness.send("plan", {
      input: "Create a 3d heat transfer block with mesh"
    });

    expect(response.ok).toBe(true);
    expect(response.data?.plan).toBeTruthy();
    expect(events.length).toBe(0);
  });

  it("emits stream events for run command and returns final response", async () => {
    harness = await SidecarHarness.start();
    const { response, events } = await harness.send("run", {
      input: "Build model and solve with mesh"
    });

    expect(response.ok).toBe(true);
    expect(events.some((item) => item.type === "run_started")).toBe(true);
    expect(events.some((item) => item.type === "run_completed")).toBe(true);
    const modelPath = (response.data?.model_path as string | undefined) ?? "";
    expect(modelPath.length).toBeGreaterThan(0);
    expect(isAbsolute(modelPath)).toBe(true);
  });

  it("returns absolute preview artifact path", async () => {
    harness = await SidecarHarness.start();
    const { response, events } = await harness.send("model_preview", {
      path: "models/test.mph",
      width: 320,
      height: 240
    });

    expect(response.ok).toBe(true);
    expect(events.length).toBe(0);
    const artifactPath = (response.data?.artifact_path as string | undefined) ?? "";
    expect(artifactPath.length).toBeGreaterThan(0);
    expect(isAbsolute(artifactPath)).toBe(true);
  });
});
