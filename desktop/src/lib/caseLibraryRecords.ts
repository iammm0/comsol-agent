import type { CaseLibraryItem } from "./caseLibrary";

const STORAGE_KEY = "mph-agent-case-library-records";

export type CaseLibraryRecordAction = "view" | "download";

export interface CaseLibraryRecord {
  id: string;
  title: string;
  category: string;
  summary: string;
  officialUrl: string;
  downloadUrl: string;
  tags: string[];
  viewCount: number;
  downloadCount: number;
  lastViewedAt: number | null;
  lastDownloadedAt: number | null;
  updatedAt: number;
}

export function loadCaseLibraryRecords(): CaseLibraryRecord[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is CaseLibraryRecord => typeof item === "object" && item !== null)
      .sort((a, b) => b.updatedAt - a.updatedAt);
  } catch {
    return [];
  }
}

function saveCaseLibraryRecords(records: CaseLibraryRecord[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(records.slice(0, 100)));
  } catch {}
}

export function trackCaseLibraryRecord(
  item: CaseLibraryItem,
  action: CaseLibraryRecordAction
): CaseLibraryRecord[] {
  const now = Date.now();
  const current = loadCaseLibraryRecords();
  const next = current.filter((record) => record.id !== item.id);
  const existing = current.find((record) => record.id === item.id);
  const record: CaseLibraryRecord = {
    id: item.id,
    title: item.title,
    category: item.category,
    summary: item.summary,
    officialUrl: item.officialUrl,
    downloadUrl: item.downloadUrl,
    tags: item.tags,
    viewCount: (existing?.viewCount ?? 0) + (action === "view" ? 1 : 0),
    downloadCount: (existing?.downloadCount ?? 0) + (action === "download" ? 1 : 0),
    lastViewedAt: action === "view" ? now : existing?.lastViewedAt ?? null,
    lastDownloadedAt: action === "download" ? now : existing?.lastDownloadedAt ?? null,
    updatedAt: now,
  };
  const merged = [record, ...next].sort((a, b) => b.updatedAt - a.updatedAt);
  saveCaseLibraryRecords(merged);
  return merged;
}

export function removeCaseLibraryRecord(id: string): CaseLibraryRecord[] {
  const next = loadCaseLibraryRecords().filter((record) => record.id !== id);
  saveCaseLibraryRecords(next);
  return next;
}

export function clearCaseLibraryRecords(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
}
