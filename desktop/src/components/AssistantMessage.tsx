import type { ChatMessage } from "../lib/types";
import { RunEventBlock } from "./RunEventBlock";
import { invoke } from "@tauri-apps/api/core";
import { useAppState } from "../context/AppStateContext";
import type { RunEvent } from "../lib/types";

/** 合并连续的 llm_stream_chunk 为单条，便于展示完整思维过程 */
function mergeStreamChunks(events: RunEvent[]): RunEvent[] {
  const out: RunEvent[] = [];
  let buf = "";
  let phase = "";
  for (const e of events) {
    if (e.type === "llm_stream_chunk") {
      buf += (e.data?.chunk ?? e.data?.text ?? "") as string;
      phase = (e.data?.phase ?? phase) as string;
      continue;
    }
    if (buf) {
      out.push({ _event: true, type: "llm_stream_chunk", data: { phase, chunk: buf, text: buf } });
      buf = "";
    }
    out.push(e);
  }
  if (buf) out.push({ _event: true, type: "llm_stream_chunk", data: { phase, chunk: buf, text: buf } });
  return out;
}

/** 根据事件列表得到当前阶段文案（用于“处理中”时的具体状态） */
function getPhaseLabel(events: RunEvent[] | undefined): string {
  if (!events?.length) return "处理中";
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].type === "task_phase" && events[i].data?.phase) {
      const map: Record<string, string> = {
        planning: "规划中",
        thinking: "思考中",
        executing: "执行中",
        observing: "观察中",
        iterating: "迭代中",
      };
      return map[events[i].data.phase as string] ?? "处理中";
    }
  }
  return "处理中";
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function extractModelPath(text: string): string | null {
  if (!text || !text.includes("模型已生成:")) return null;
  const path = text.replace(/^.*模型已生成:\s*/, "").trim();
  return path || null;
}

function openInFolder(path: string) {
  invoke("open_in_folder", { path }).catch(() => {
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(path);
      alert("已复制路径到剪贴板");
    }
  });
}

function openPreviewMd(modelPath: string) {
  const dir = modelPath.replace(/[/\\][^/\\]*$/, "") || modelPath;
  const mdPath = (dir.endsWith("/") || dir.endsWith("\\") ? dir : dir + "/") + "operations.md";
  invoke("open_path", { path: mdPath }).catch(() => {
    alert("未找到操作记录文件 operations.md，请确认模型所在目录。");
  });
}

export function AssistantMessage({ message }: { message: ChatMessage }) {
  const { state } = useAppState();
  const hasEvents = (message.events?.length ?? 0) > 0;
  const isError = message.success === false;
  const isCurrentBusy = state.busyConversationId === state.currentConversationId;
  const showText = !isError && (message.text || !hasEvents);
  const modelPath = extractModelPath(message.text || "");
  const phaseLabel = getPhaseLabel(message.events);
  const placeholderText = message.text || (isCurrentBusy ? phaseLabel : "") || "—";

  return (
    <div className="assistant-msg">
      {hasEvents && (
        <div className="assistant-msg-reasoning">
          <p className="assistant-msg-reasoning-title">推理与构建流程</p>
          <div className="assistant-msg-events">
            {mergeStreamChunks(message.events!).map((evt, i) => (
              <RunEventBlock key={i} event={evt} />
            ))}
          </div>
        </div>
      )}
      {isError && (
        <div className="assistant-msg-body error">
          <div className="assistant-msg-text">{message.text}</div>
        </div>
      )}
      {showText && (
        <div className="assistant-msg-body success">
          <div className="assistant-msg-text">
            {placeholderText}
          </div>
          <div className="assistant-msg-meta">
            {modelPath && (
              <>
                <button
                  type="button"
                  className="assistant-msg-model-btn"
                  onClick={() => openInFolder(modelPath)}
                  title="打开模型所在目录"
                >
                  在文件管理器中打开
                </button>
                <button
                  type="button"
                  className="assistant-msg-model-btn"
                  onClick={() => openPreviewMd(modelPath)}
                  title="预览操作记录 (operations.md)"
                >
                  预览
                </button>
              </>
            )}
            <span className="dot">▣</span>
            <span>{formatTime(message.time)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
