import { invoke } from "@tauri-apps/api/core";
import type { BridgeResponse, OpsCatalogItem } from "./types";

interface OpsCatalogResponse extends BridgeResponse {
  items?: OpsCatalogItem[];
  total?: number;
  limit?: number;
  offset?: number;
  categories?: string[];
}

export interface OpsCatalogResult {
  ok: boolean;
  message: string;
  items: OpsCatalogItem[];
  total: number;
  limit: number;
  offset: number;
  categories: string[];
}

export async function fetchOpsCatalog(options?: {
  query?: string;
  limit?: number;
  offset?: number;
}): Promise<OpsCatalogResult> {
  const { query, limit = 200, offset = 0 } = options ?? {};

  try {
    const res = await invoke<OpsCatalogResponse>("bridge_send", {
      cmd: "ops_catalog",
      payload: {
        query: query?.trim() || undefined,
        limit,
        offset,
      },
    });

    return {
      ok: res.ok,
      message: res.message,
      items: Array.isArray(res.items) ? res.items : [],
      total: typeof res.total === "number" ? res.total : 0,
      limit: typeof res.limit === "number" ? res.limit : limit,
      offset: typeof res.offset === "number" ? res.offset : offset,
      categories: Array.isArray(res.categories) ? res.categories : [],
    };
  } catch (error) {
    return {
      ok: false,
      message: String(error),
      items: [],
      total: 0,
      limit,
      offset,
      categories: [],
    };
  }
}
