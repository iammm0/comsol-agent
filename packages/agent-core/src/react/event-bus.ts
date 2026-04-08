import type { EventSink } from "../types/runtime.js";
import type { BridgeEvent, EventType } from "@mph-agent/contracts";

export class ReActEventBus {
  private readonly runId: string;
  private readonly sink: EventSink;

  public constructor(runId: string, sink: EventSink) {
    this.runId = runId;
    this.sink = sink;
  }

  public emit(type: EventType, data: Record<string, unknown>, iteration?: number): void {
    const event: BridgeEvent = {
      version: "v1",
      _event: true,
      runId: this.runId,
      type,
      ts: new Date().toISOString(),
      ...(typeof iteration === "number" ? { iteration } : {}),
      data
    };
    this.sink(event);
  }
}
