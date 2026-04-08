import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import {
  bridgeEventSchema,
  bridgeResponseSchema,
  createRequest,
  type BridgeEvent,
  type BridgeRequest,
  type BridgeResponse,
  type CommandKey,
  type CommandPayload
} from "@mph-agent/contracts";

const BRIDGE_EVENT_NAME = "bridge-event";

export async function bridgeSend(
  request: BridgeRequest<CommandPayload>
): Promise<BridgeResponse<Record<string, unknown>>> {
  const response = await invoke<unknown>("bridge_send", { request });
  return bridgeResponseSchema.parse(response) as BridgeResponse<Record<string, unknown>>;
}

export async function bridgeSendStream(
  request: BridgeRequest<CommandPayload>
): Promise<BridgeResponse<Record<string, unknown>>> {
  const response = await invoke<unknown>("bridge_send_stream", { request });
  return bridgeResponseSchema.parse(response) as BridgeResponse<Record<string, unknown>>;
}

export async function sendCommand(
  cmd: CommandKey,
  payload: CommandPayload,
  conversationId?: string
): Promise<BridgeResponse<Record<string, unknown>>> {
  const request = createRequest({
    id: crypto.randomUUID(),
    cmd,
    payload,
    conversationId
  });
  return bridgeSend(request);
}

export async function sendStreamCommand(
  cmd: CommandKey,
  payload: CommandPayload,
  conversationId?: string
): Promise<BridgeResponse<Record<string, unknown>>> {
  const request = createRequest({
    id: crypto.randomUUID(),
    cmd,
    payload,
    conversationId
  });
  return bridgeSendStream(request);
}

export async function listenBridgeEvents(
  onEvent: (event: BridgeEvent) => void
): Promise<UnlistenFn> {
  return listen<unknown>(BRIDGE_EVENT_NAME, (event) => {
    const parsed = bridgeEventSchema.safeParse(event.payload);
    if (!parsed.success) {
      return;
    }
    onEvent(parsed.data);
  });
}

export async function abortBridgeRun(): Promise<void> {
  await invoke("bridge_abort");
}

export async function openPath(path: string): Promise<void> {
  await invoke("open_path", { path });
}

export async function openInFolder(path: string): Promise<void> {
  await invoke("open_in_folder", { path });
}

export async function getBridgeInitStatus(): Promise<{ ready: boolean; error: string | null }> {
  const status = await invoke<{ ready: boolean; error: string | null }>("bridge_init_status");
  return {
    ready: Boolean(status.ready),
    error: status.error ?? null
  };
}
