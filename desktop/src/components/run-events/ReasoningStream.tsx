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

type TokenBudgetPayload = {
  phase?: string;
  model?: string;
  prompt_tokens?: unknown;
  soft_input_limit_tokens?: unknown;
  hard_input_limit_tokens?: unknown;
  exceeds_soft_limit?: unknown;
  exceeds_hard_limit?: unknown;
  tokenizer_backend?: unknown;
  tokenizer_accurate?: unknown;
  report?: unknown;
};

type PlanRuntimeSyncPayload = {
  phase?: string;
  after_count?: unknown;
  synced_tasks?: unknown;
  store_path?: unknown;
  sha256?: unknown;
  error?: unknown;
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

function lastEventOfType(events: RunEvent[], type: string): RunEvent | null {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i]?.type === type) return events[i];
  }
  return null;
}

function formatNumber(value: unknown): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "";
  return n.toLocaleString();
}

function BudgetBadge({ event }: { event: RunEvent }) {
  const d = (event.data ?? {}) as TokenBudgetPayload;
  const exceedsHard = Boolean(d.exceeds_hard_limit);
  const exceedsSoft = Boolean(d.exceeds_soft_limit);
  const severity = exceedsHard ? "hard" : exceedsSoft ? "soft" : "ok";
  const promptTokens = formatNumber(d.prompt_tokens);
  const soft = formatNumber(d.soft_input_limit_tokens);
  const model = String(d.model ?? "").trim();
  const report = String(d.report ?? "").trim();

  return (
    <details className={`reasoning-badge reasoning-badge--budget reasoning-badge--${severity}`}>
      <summary className="reasoning-badge__summary" title="Token 预算（点击展开）">
        <span className="reasoning-badge__label">tokens</span>
        <span className="reasoning-badge__value">
          {promptTokens || "-"}
          {soft ? ` / ${soft}` : ""}
        </span>
        {model ? <span className="reasoning-badge__meta">{model}</span> : null}
      </summary>
      {report ? <pre className="reasoning-badge__detail">{report}</pre> : null}
    </details>
  );
}

function PlanSyncBadge({ event }: { event: RunEvent }) {
  const d = (event.data ?? {}) as PlanRuntimeSyncPayload;
  const error = String(d.error ?? "").trim();
  const severity = error ? "fail" : "ok";
  const steps = formatNumber(d.after_count);
  const tasks = formatNumber(d.synced_tasks);
  const storePath = String(d.store_path ?? "").trim();
  const sha = String(d.sha256 ?? "").trim();

  return (
    <details className={`reasoning-badge reasoning-badge--plan reasoning-badge--${severity}`}>
      <summary className="reasoning-badge__summary" title="计划镜像状态（点击展开）">
        <span className="reasoning-badge__label">plan</span>
        <span className="reasoning-badge__value">
          {steps ? `steps=${steps}` : "steps=-"}
          {tasks ? ` · tasks=${tasks}` : ""}
        </span>
      </summary>
      <pre className="reasoning-badge__detail">
        {JSON.stringify(
          {
            store_path: storePath || undefined,
            sha256: sha || undefined,
            error: error || undefined,
          },
          null,
          2
        )}
      </pre>
    </details>
  );
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
            <div className="reasoning-stream__phase-badges">
              {(() => {
                const budget = lastEventOfType(block.events, "token_budget");
                return budget ? <BudgetBadge event={budget} /> : null;
              })()}
              {(() => {
                const sync = lastEventOfType(block.events, "plan_runtime_sync");
                return sync ? <PlanSyncBadge event={sync} /> : null;
              })()}
            </div>
          </div>
          <div className="reasoning-stream__phase-events">
            {block.events
              .filter((evt) => evt.type !== "token_budget" && evt.type !== "plan_runtime_sync")
              .map((evt, j) => (
                <RunEventBlock key={j} event={evt} />
              ))}
          </div>
        </section>
      ))}
    </div>
  );
}
