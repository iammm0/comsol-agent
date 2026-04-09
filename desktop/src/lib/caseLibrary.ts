import { invoke } from "@tauri-apps/api/core";

export interface CaseLibraryItem {
  id: string;
  title: string;
  category: string;
  summary: string;
  officialUrl: string;
  downloadUrl: string;
  tags: string[];
}

interface CaseLibraryBridgeResponse {
  ok: boolean;
  message: string;
  items?: Array<Record<string, unknown>>;
}

const FALLBACK_CASES: CaseLibraryItem[] = [
  {
    id: "heat-sink-3d",
    title: "3D Heat Sink Cooling",
    category: "传热",
    summary: "典型散热片稳态传热分析，展示温度分布与散热能力评估。",
    officialUrl: "https://www.comsol.com/model/heat-sink-3d-473",
    downloadUrl: "https://www.comsol.com/model/download/473",
    tags: ["热传导", "散热", "3D"],
  },
  {
    id: "micromixer",
    title: "Micromixer",
    category: "流体",
    summary: "微流控混合器模型，关注层流与组分传输耦合效果。",
    officialUrl: "https://www.comsol.com/model/micromixer-14611",
    downloadUrl: "https://www.comsol.com/model/download/14611",
    tags: ["层流", "传质", "微流控"],
  },
  {
    id: "induction-heating",
    title: "Induction Heating",
    category: "电磁-热",
    summary: "电磁场与固体传热耦合，分析感应加热过程中的温升。",
    officialUrl: "https://www.comsol.com/model/induction-heating-14595",
    downloadUrl: "https://www.comsol.com/model/download/14595",
    tags: ["感应加热", "电磁", "多物理场"],
  },
];

function normalizeItem(raw: Record<string, unknown>): CaseLibraryItem | null {
  const id = typeof raw.id === "string" ? raw.id : "";
  const title = typeof raw.title === "string" ? raw.title : "";
  const category = typeof raw.category === "string" ? raw.category : "未分类";
  const summary = typeof raw.summary === "string" ? raw.summary : "";
  const officialUrl = typeof raw.official_url === "string" ? raw.official_url : "";
  const downloadUrl = typeof raw.download_url === "string" ? raw.download_url : "";
  const tagsRaw = Array.isArray(raw.tags) ? raw.tags : [];
  const tags = tagsRaw.filter((t): t is string => typeof t === "string");
  if (!id || !title || !officialUrl || !downloadUrl) return null;
  return { id, title, category, summary, officialUrl, downloadUrl, tags };
}

export async function fetchCaseLibrary(): Promise<CaseLibraryItem[]> {
  try {
    const res = await invoke<CaseLibraryBridgeResponse>("bridge_send", {
      cmd: "case_library_list",
      payload: { limit: 200 },
    });
    if (!res.ok || !Array.isArray(res.items)) {
      return FALLBACK_CASES;
    }
    const normalized = res.items
      .map((row) => normalizeItem(row))
      .filter((item): item is CaseLibraryItem => item != null);
    return normalized.length > 0 ? normalized : FALLBACK_CASES;
  } catch {
    return FALLBACK_CASES;
  }
}
