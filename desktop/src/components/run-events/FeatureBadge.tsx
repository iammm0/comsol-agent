import type { RunEvent } from "../../lib/types";

export function FeatureBadge({ event }: { event: RunEvent }) {
  const d = event.data ?? {};
  const type = event.type;

  if (type === "geometry_3d") {
    const msg = String(d.message ?? "").trim() || `3D 几何 (${d.dimension ?? 3}D)`;
    return <span className="run-event-badge run-event-badge--geometry">{msg}</span>;
  }

  if (type === "coupling_added") {
    const msg = String(d.type ?? d.message ?? "多物理场耦合").trim();
    return <span className="run-event-badge run-event-badge--coupling">{msg}</span>;
  }

  return null;
}
