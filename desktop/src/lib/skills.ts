import { invoke } from "@tauri-apps/api/core";

export interface LocalSkillLibraryItem {
  id: string;
  name: string;
  slug: string;
  description: string;
  preview: string;
  tags: string[];
  triggers: string[];
  author: string;
  version: string;
  path: string;
  skillFile: string;
  updatedAt: string | null;
}

export interface OnlineSkillLibraryItem {
  id: string;
  name: string;
  description: string;
  tags: string[];
  provider: string;
  sourceUrl: string;
  homepageUrl: string;
  installed: boolean;
}

interface SkillsBridgeResponse {
  ok: boolean;
  message: string;
  items?: Array<Record<string, unknown>>;
  item?: Record<string, unknown> | null;
  total?: number;
}

let skillsBridgeQueue: Promise<unknown> = Promise.resolve();

function queueSkillsBridge<T>(task: () => Promise<T>): Promise<T> {
  const run = skillsBridgeQueue.then(task, task);
  skillsBridgeQueue = run.then(
    () => undefined,
    () => undefined
  );
  return run;
}

function invokeSkillsBridge(cmd: string, payload: Record<string, unknown>): Promise<SkillsBridgeResponse> {
  return queueSkillsBridge(() =>
    invoke<SkillsBridgeResponse>("bridge_send", {
      cmd,
      payload,
    })
  );
}

function normalizeLocalSkill(raw: Record<string, unknown>): LocalSkillLibraryItem | null {
  const id = typeof raw.id === "string" ? raw.id : "";
  const name = typeof raw.name === "string" ? raw.name : "";
  const slug = typeof raw.slug === "string" ? raw.slug : "";
  const path = typeof raw.path === "string" ? raw.path : "";
  const skillFile = typeof raw.skill_file === "string" ? raw.skill_file : "";
  if (!id || !name || !slug || !path || !skillFile) return null;
  return {
    id,
    name,
    slug,
    description: typeof raw.description === "string" ? raw.description : "",
    preview: typeof raw.preview === "string" ? raw.preview : "",
    tags: Array.isArray(raw.tags) ? raw.tags.filter((item): item is string => typeof item === "string") : [],
    triggers: Array.isArray(raw.triggers)
      ? raw.triggers.filter((item): item is string => typeof item === "string")
      : [],
    author: typeof raw.author === "string" ? raw.author : "",
    version: typeof raw.version === "string" ? raw.version : "",
    path,
    skillFile,
    updatedAt: typeof raw.updated_at === "string" ? raw.updated_at : null,
  };
}

function normalizeOnlineSkill(raw: Record<string, unknown>): OnlineSkillLibraryItem | null {
  const id = typeof raw.id === "string" ? raw.id : "";
  const name = typeof raw.name === "string" ? raw.name : "";
  const sourceUrl = typeof raw.source_url === "string" ? raw.source_url : "";
  if (!id || !name || !sourceUrl) return null;
  return {
    id,
    name,
    description: typeof raw.description === "string" ? raw.description : "",
    tags: Array.isArray(raw.tags) ? raw.tags.filter((item): item is string => typeof item === "string") : [],
    provider: typeof raw.provider === "string" ? raw.provider : "Online",
    sourceUrl,
    homepageUrl: typeof raw.homepage_url === "string" ? raw.homepage_url : sourceUrl,
    installed: raw.installed === true,
  };
}

export async function fetchLocalSkillLibraries(): Promise<{
  ok: boolean;
  message: string;
  items: LocalSkillLibraryItem[];
  total: number;
}> {
  try {
    const res = await invokeSkillsBridge("skills_list_local", {});
    const items = Array.isArray(res.items)
      ? res.items
          .map((item) => normalizeLocalSkill(item))
          .filter((item): item is LocalSkillLibraryItem => item != null)
      : [];
    return {
      ok: res.ok,
      message: res.message,
      items,
      total: typeof res.total === "number" ? res.total : items.length,
    };
  } catch (error) {
    return { ok: false, message: String(error), items: [], total: 0 };
  }
}

export async function createLocalSkillLibrary(input: {
  name: string;
  description?: string;
  tags?: string[];
  triggers?: string[];
}): Promise<{ ok: boolean; message: string; item: LocalSkillLibraryItem | null }> {
  try {
    const res = await invokeSkillsBridge("skills_create_local", {
        name: input.name,
        description: input.description,
        tags: input.tags ?? [],
        triggers: input.triggers ?? [],
    });
    return {
      ok: res.ok,
      message: res.message,
      item: res.item ? normalizeLocalSkill(res.item) : null,
    };
  } catch (error) {
    return { ok: false, message: String(error), item: null };
  }
}

export async function importLocalSkillLibrary(sourcePath: string): Promise<{
  ok: boolean;
  message: string;
  item: LocalSkillLibraryItem | null;
}> {
  try {
    const res = await invokeSkillsBridge("skills_import_local", { source_path: sourcePath });
    return {
      ok: res.ok,
      message: res.message,
      item: res.item ? normalizeLocalSkill(res.item) : null,
    };
  } catch (error) {
    return { ok: false, message: String(error), item: null };
  }
}

export async function fetchOnlineSkillLibrary(): Promise<{
  ok: boolean;
  message: string;
  items: OnlineSkillLibraryItem[];
  total: number;
}> {
  try {
    const res = await invokeSkillsBridge("skills_list_online", {});
    const items = Array.isArray(res.items)
      ? res.items
          .map((item) => normalizeOnlineSkill(item))
          .filter((item): item is OnlineSkillLibraryItem => item != null)
      : [];
    return {
      ok: res.ok,
      message: res.message,
      items,
      total: typeof res.total === "number" ? res.total : items.length,
    };
  } catch (error) {
    return { ok: false, message: String(error), items: [], total: 0 };
  }
}
