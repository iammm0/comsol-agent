import type { RunEvent } from "../lib/types";

function eventCategory(type: string): string {
  if (type === "plan_start" || type === "plan_end") return "plan";
  if (type === "think_chunk") return "think";
  if (type.startsWith("action") || type === "exec_result") return "action";
  if (type === "material_start" || type === "material_end") return "material";
  if (type === "geometry_3d" || type === "coupling_added") return "geometry";
  if (type === "step_start" || type === "step_end") return "step";
  if (type === "error") return "err";
  return "";
}

function eventLabel(type: string): string {
  const map: Record<string, string> = {
    plan_start: "规划开始",
    plan_end: "规划完成",
    task_phase: "迭代",
    think_chunk: "思考",
    action_start: "执行",
    action_end: "完成",
    exec_result: "结果",
    observation: "观察",
    content: "内容",
    error: "错误",
    material_start: "材料设置",
    material_end: "材料完成",
  geometry_3d: "3D 几何",
  coupling_added: "多物理场耦合",
  step_start: "步骤开始",
  step_end: "步骤完成",
  };
  return map[type] ?? type;
}

function eventContent(event: RunEvent): string {
  const d = event.data;
  const type = event.type;

  if (type === "plan_start") return String(d.user_input ?? "");
  if (type === "plan_end") {
    const steps = d.steps as
      | Array<{ action?: string; step_type?: string }>
      | undefined;
    const model = d.model_name ?? "";
    if (steps?.length)
      return `${model} · ${steps.length} 步: ${steps.map((s) => s.action ?? s.step_type).join(" → ")}`;
    return String(model);
  }
  if (type === "task_phase")
    return `${String(d.phase ?? "")} #${event.data.iteration ?? event.iteration ?? "?"}`;
  if (type === "think_chunk") {
    const t = d.thought as Record<string, unknown> | undefined;
    if (!t) return "";
    return [t.action, t.reasoning].filter(Boolean).join(" — ");
  }
  if (type === "action_start") {
    const t = d.thought as Record<string, unknown> | undefined;
    return t ? String(t.action ?? JSON.stringify(t)) : "";
  }
  if (type === "action_end") return String(d.action ?? "完成");
  if (type === "exec_result") {
    const r = d.result as Record<string, unknown> | undefined;
    return r ? String(r.status ?? r.message ?? JSON.stringify(r)) : "";
  }
  if (type === "observation") return String(d.observation ?? d.message ?? "");
  if (type === "content") return String(d.content ?? "");
  if (type === "error") return String(d.message ?? "");
  if (type === "material_start") return String(d.message ?? "添加材料...");
  if (type === "material_end") {
    const mats = d.materials as
      | Array<{ material?: string; label?: string }>
      | undefined;
    return mats?.length
      ? `已添加 ${mats.length} 种材料: ${mats.map((m) => m.label || m.material).join(", ")}`
      : "材料设置完成";
  }
  if (type === "geometry_3d")
    return String(d.message ?? `3D 几何 (${d.dimension ?? 3}D)`);
  if (type === "coupling_added")
    return String(d.type ?? d.message ?? "多物理场耦合已添加");
  if (type === "step_start")
    return String(d.message ?? d.step_type ?? "执行中...");
  if (type === "step_end")
    return String(d.message ?? d.step_type ?? "完成");
  return JSON.stringify(d).slice(0, 120);
}

export function RunEventBlock({ event }: { event: RunEvent }) {
  const cat = eventCategory(event.type);
  const label = eventLabel(event.type);
  const content = eventContent(event);

  return (
    <div className={`run-event ${cat}`}>
      <div className="run-event-header">
        <span className="run-event-label">{label}</span>
        {event.iteration != null && (
          <span className="run-event-iter">#{event.iteration}</span>
        )}
      </div>
      {content && <div className="run-event-content">{content}</div>}
    </div>
  );
}
