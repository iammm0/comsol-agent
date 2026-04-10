import type { RunEvent } from "../../lib/types";
import { RunEventBlock } from "./index";

const PHASE_LABELS: Record<string, string> = {
  planning: "规划",
  thinking: "思考",
  executing: "执行",
  observing: "观察",
  iterating: "根据结果调整",
  qa: "问答",
};

/** 合并连续的 llm_stream_chunk 为单条 */
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

export interface PhaseBlock {
  phase: string;
  label: string;
  events: RunEvent[];
  isCurrent: boolean;
}

/** 按 task_phase 将事件分成多个阶段块，便于按「阶段 + 思考」展示 */
export function groupEventsByPhase(events: RunEvent[]): PhaseBlock[] {
  const merged = mergeStreamChunks(events);
  const blocks: PhaseBlock[] = [];
  let current: RunEvent[] = [];
  let currentPhase = "";
  let currentLabel = "规划";

  for (const e of merged) {
    if (e.type === "task_phase" && e.data?.phase) {
      if (current.length > 0) {
        blocks.push({
          phase: currentPhase,
          label: PHASE_LABELS[currentPhase] ?? (currentPhase || "规划"),
          events: current,
          isCurrent: false,
        });
        current = [];
      }
      currentPhase = e.data.phase as string;
      currentLabel = PHASE_LABELS[currentPhase] ?? currentPhase;
      continue;
    }
    if (e.type === "plan_start") {
      if (current.length > 0) {
        blocks.push({ phase: currentPhase, label: currentLabel, events: current, isCurrent: false });
        current = [];
      }
      currentPhase = "planning";
      currentLabel = "规划";
    }
    current.push(e);
  }

  if (current.length > 0 || currentPhase) {
    blocks.push({
      phase: currentPhase,
      label: currentLabel,
      events: current,
      isCurrent: true,
    });
  } else if (blocks.length > 0) {
    blocks[blocks.length - 1].isCurrent = true;
  }

  return blocks;
}

/** 按阶段渲染流式思考与执行结果，突出每个阶段在做什么 */
export function ReasoningStream({ events }: { events: RunEvent[] }) {
  const blocks = groupEventsByPhase(events);
  if (blocks.length === 0) return null;

  return (
    <div className="reasoning-stream">
      {blocks.map((block, i) => (
        <section
          key={i}
          className={`reasoning-stream__phase ${block.isCurrent ? "reasoning-stream__phase--current" : ""}`}
          data-phase={block.phase}
        >
          <div className="reasoning-stream__phase-header">
            <span className="reasoning-stream__phase-label">{block.label}</span>
          </div>
          <div className="reasoning-stream__phase-events">
            {block.events.map((evt, j) => (
              <RunEventBlock key={j} event={evt} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
