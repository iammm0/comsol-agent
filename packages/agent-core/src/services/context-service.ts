import { randomUUID } from "node:crypto";
import { copyFile, mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import type { ContextSummary, ConversationEntry } from "../types/runtime.js";

interface ConversationContextFiles {
  historyPath: string;
  summaryPath: string;
  latestModelPath: string;
  operationsPath: string;
}

const MIGRATION_MARKER = ".migration-v1.json";

function nowIso(): string {
  return new Date().toISOString();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function optionalString(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function optionalBoolean(value: unknown): boolean | undefined {
  if (typeof value === "boolean") {
    return value;
  }
  return undefined;
}

function optionalNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return undefined;
}

function normalizeSummary(raw: unknown, fallbackTotal: number): ContextSummary | null {
  if (!isRecord(raw)) {
    return null;
  }

  const summary = optionalString(raw.summary);
  if (!summary) {
    return null;
  }

  const lastUpdated = optionalString(raw.lastUpdated ?? raw.updated_at) ?? nowIso();

  const totalFromRaw = optionalNumber(raw.totalConversations ?? raw.total_conversations);
  const totalConversations =
    typeof totalFromRaw === "number" ? Math.max(0, Math.floor(totalFromRaw)) : fallbackTotal;

  const recentActionsRaw = raw.recentActions ?? raw.recent_actions;
  const recentActions = Array.isArray(recentActionsRaw)
    ? recentActionsRaw
        .map((item) => optionalString(item))
        .filter((item): item is string => typeof item === "string")
    : [];

  const preferencesRaw = raw.preferences;
  const preferences: Record<string, string> = {};
  if (isRecord(preferencesRaw)) {
    for (const [key, value] of Object.entries(preferencesRaw)) {
      const normalized = optionalString(value);
      if (normalized) {
        preferences[key] = normalized;
      }
    }
  }

  return {
    summary,
    lastUpdated,
    totalConversations,
    recentActions,
    preferences
  };
}

export class ContextService {
  private readonly root: string;

  public constructor(contextRoot: string) {
    this.root = contextRoot;
  }

  public async init(): Promise<void> {
    await mkdir(this.root, { recursive: true });
    await this.migrateLegacyContextIfNeeded();
  }

  private files(conversationId: string): ConversationContextFiles {
    const dir = join(this.root, conversationId);
    return {
      historyPath: join(dir, "history.json"),
      summaryPath: join(dir, "summary.json"),
      latestModelPath: join(dir, "latest_model.txt"),
      operationsPath: join(dir, "operations.md")
    };
  }

  private async ensureConversationDir(conversationId: string): Promise<string> {
    const dir = join(this.root, conversationId);
    await mkdir(dir, { recursive: true });
    return dir;
  }

  public async addConversationEntry(entry: ConversationEntry): Promise<void> {
    await this.ensureConversationDir(entry.conversationId);
    const files = this.files(entry.conversationId);
    const history = await this.readHistory(entry.conversationId);
    history.push(entry);
    const trimmed = history.slice(-200);
    await writeFile(files.historyPath, JSON.stringify(trimmed, null, 2), "utf8");

    if (entry.modelPath) {
      await writeFile(files.latestModelPath, entry.modelPath, "utf8");
    }

    await this.updateSummary(entry.conversationId);
  }

  public async readHistory(conversationId: string): Promise<ConversationEntry[]> {
    const files = this.files(conversationId);
    try {
      const raw = await readFile(files.historyPath, "utf8");
      const parsed = JSON.parse(raw) as ConversationEntry[];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  public async appendOperation(conversationId: string, line: string): Promise<void> {
    await this.ensureConversationDir(conversationId);
    const files = this.files(conversationId);
    let current = "# Operations\n\n";
    try {
      current = await readFile(files.operationsPath, "utf8");
    } catch {
      // keep default
    }
    const next = `${current}${nowIso()} ${line}\n`;
    await writeFile(files.operationsPath, next, "utf8");
  }

  public async getSummary(conversationId: string): Promise<ContextSummary | null> {
    const files = this.files(conversationId);
    try {
      const raw = await readFile(files.summaryPath, "utf8");
      const parsed = JSON.parse(raw) as ContextSummary;
      if (!parsed.summary) {
        return null;
      }
      return parsed;
    } catch {
      return null;
    }
  }

  public async setSummary(conversationId: string, summary: string): Promise<void> {
    await this.ensureConversationDir(conversationId);
    const files = this.files(conversationId);
    const history = await this.readHistory(conversationId);
    const value: ContextSummary = {
      summary,
      lastUpdated: nowIso(),
      totalConversations: history.length,
      recentActions: [],
      preferences: {}
    };
    await writeFile(files.summaryPath, JSON.stringify(value, null, 2), "utf8");
  }

  public async clearConversation(conversationId: string): Promise<void> {
    const dir = join(this.root, conversationId);
    await rm(dir, { recursive: true, force: true });
  }

  public async getStats(conversationId: string): Promise<Record<string, unknown>> {
    const history = await this.readHistory(conversationId);
    let success = 0;
    let failed = 0;
    for (const item of history) {
      if (item.success) success += 1;
      else failed += 1;
    }
    return {
      total: history.length,
      success,
      failed
    };
  }

  public async getHistoryAsText(conversationId: string, limit: number): Promise<string> {
    const history = await this.readHistory(conversationId);
    const list = history.slice(-limit);
    if (list.length === 0) {
      return "No history";
    }
    return list
      .map((item, index) => `${index + 1}. [${item.success ? "OK" : "ERR"}] ${item.timestamp} ${item.userInput}`)
      .join("\n");
  }

  public async getModels(limit: number): Promise<Array<Record<string, unknown>>> {
    const result: Array<Record<string, unknown>> = [];
    const dirs = await readdir(this.root, { withFileTypes: true });
    for (const dir of dirs) {
      if (!dir.isDirectory()) {
        continue;
      }
      const conversationId = dir.name;
      const history = await this.readHistory(conversationId);
      const latest = await this.getLatestModelPath(conversationId);
      for (const entry of [...history].reverse()) {
        if (!entry.modelPath) {
          continue;
        }
        result.push({
          path: entry.modelPath,
          title: entry.userInput.slice(0, 80),
          timestamp: entry.timestamp,
          is_latest: latest === entry.modelPath
        });
        if (result.length >= limit) {
          return result;
        }
      }
    }
    return result;
  }

  public async getLatestModelPath(conversationId: string): Promise<string | null> {
    const files = this.files(conversationId);
    try {
      const value = (await readFile(files.latestModelPath, "utf8")).trim();
      return value.length > 0 ? value : null;
    } catch {
      return null;
    }
  }

  public async deleteConversationAndModels(conversationId: string): Promise<string[]> {
    const history = await this.readHistory(conversationId);
    const deleted: string[] = [];
    for (const entry of history) {
      if (!entry.modelPath) {
        continue;
      }
      try {
        await rm(entry.modelPath, { force: true });
        deleted.push(entry.modelPath);
      } catch {
        continue;
      }
    }
    await this.clearConversation(conversationId);
    return deleted;
  }

  private async updateSummary(conversationId: string): Promise<void> {
    const files = this.files(conversationId);
    const history = await this.readHistory(conversationId);
    const recentActions: string[] = [];
    for (const item of history.slice(-20)) {
      if (item.plan && Array.isArray(item.plan.steps)) {
        for (const step of item.plan.steps as Array<{ label?: string }>) {
          if (step.label && !recentActions.includes(step.label)) {
            recentActions.push(step.label);
          }
        }
      }
    }

    const summary: ContextSummary = {
      summary: `Conversations: ${history.length}. Last activity: ${history.length > 0 ? history[history.length - 1]?.timestamp : "N/A"}`,
      lastUpdated: nowIso(),
      totalConversations: history.length,
      recentActions,
      preferences: {}
    };
    await writeFile(files.summaryPath, JSON.stringify(summary, null, 2), "utf8");
  }

  private async migrateLegacyContextIfNeeded(): Promise<void> {
    const markerPath = join(this.root, MIGRATION_MARKER);
    if (await this.pathExists(markerPath)) {
      return;
    }

    const legacyRoot = join(dirname(this.root), ".context");
    const report = {
      migratedAt: nowIso(),
      source: legacyRoot,
      importedConversations: 0,
      skippedConversations: 0,
      errors: [] as string[]
    };

    if (!(await this.pathExists(legacyRoot))) {
      await writeFile(markerPath, JSON.stringify(report, null, 2), "utf8");
      return;
    }

    const entries = await readdir(legacyRoot, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) {
        continue;
      }

      const conversationId = entry.name;
      try {
        const imported = await this.importLegacyConversation(legacyRoot, conversationId);
        if (imported) {
          report.importedConversations += 1;
        } else {
          report.skippedConversations += 1;
        }
      } catch (error) {
        report.errors.push(
          `${conversationId}: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    }

    await writeFile(markerPath, JSON.stringify(report, null, 2), "utf8");
  }

  private async importLegacyConversation(
    legacyRoot: string,
    conversationId: string
  ): Promise<boolean> {
    const existingHistory = await this.readHistory(conversationId);
    if (existingHistory.length > 0) {
      return false;
    }

    const sourceDir = join(legacyRoot, conversationId);
    const sourceHistoryPath = join(sourceDir, "history.json");
    const sourceSummaryPath = join(sourceDir, "summary.json");
    const sourceLatestModelPath = join(sourceDir, "latest_model.txt");
    const sourceOperationsPath = join(sourceDir, "operations.md");

    await this.ensureConversationDir(conversationId);
    const targetFiles = this.files(conversationId);

    let importedAny = false;
    let importedSummary = false;
    let normalizedHistory: ConversationEntry[] = [];

    if (await this.pathExists(sourceHistoryPath)) {
      try {
        const historyRaw = await readFile(sourceHistoryPath, "utf8");
        normalizedHistory = this.normalizeLegacyHistory(
          JSON.parse(historyRaw) as unknown,
          conversationId
        );
        if (normalizedHistory.length > 0) {
          await writeFile(
            targetFiles.historyPath,
            JSON.stringify(normalizedHistory.slice(-200), null, 2),
            "utf8"
          );
          importedAny = true;
        }
      } catch {
        // ignore malformed legacy history
      }
    }

    if (await this.pathExists(sourceSummaryPath)) {
      try {
        const summaryRaw = await readFile(sourceSummaryPath, "utf8");
        const normalizedSummary = normalizeSummary(
          JSON.parse(summaryRaw) as unknown,
          normalizedHistory.length
        );
        if (normalizedSummary) {
          await writeFile(targetFiles.summaryPath, JSON.stringify(normalizedSummary, null, 2), "utf8");
          importedAny = true;
          importedSummary = true;
        }
      } catch {
        // ignore malformed summary
      }
    }

    if (await this.pathExists(sourceLatestModelPath)) {
      try {
        const modelPath = optionalString(await readFile(sourceLatestModelPath, "utf8"));
        if (modelPath) {
          await writeFile(targetFiles.latestModelPath, modelPath, "utf8");
          importedAny = true;
        }
      } catch {
        // ignore malformed latest model
      }
    }

    if (await this.pathExists(sourceOperationsPath)) {
      try {
        await copyFile(sourceOperationsPath, targetFiles.operationsPath);
        importedAny = true;
      } catch {
        // ignore operation copy failures
      }
    }

    if (importedAny && !importedSummary) {
      await this.updateSummary(conversationId);
    }

    return importedAny;
  }

  private normalizeLegacyHistory(raw: unknown, conversationId: string): ConversationEntry[] {
    if (!Array.isArray(raw)) {
      return [];
    }

    const output: ConversationEntry[] = [];
    for (let index = 0; index < raw.length; index += 1) {
      const value = raw[index];
      if (!isRecord(value)) {
        continue;
      }

      const userInput =
        optionalString(value.userInput) ??
        optionalString(value.input) ??
        optionalString(value.prompt) ??
        optionalString(value.query) ??
        "(legacy entry)";

      const timestamp =
        optionalString(value.timestamp) ??
        optionalString(value.ts) ??
        optionalString(value.created_at) ??
        nowIso();

      const modelPath =
        optionalString(value.modelPath) ??
        optionalString(value.model_path) ??
        optionalString(value.output_path);

      const explicitSuccess = optionalBoolean(value.success) ?? optionalBoolean(value.ok);
      const errorMessage = optionalString(value.error) ?? optionalString(value.message);
      const success =
        typeof explicitSuccess === "boolean" ? explicitSuccess : errorMessage ? false : true;

      const legacyId = optionalString(value.id);
      const plan = isRecord(value.plan) ? value.plan : undefined;

      const entry: ConversationEntry = {
        id: legacyId ?? `legacy_${conversationId}_${index + 1}_${randomUUID()}`,
        conversationId,
        timestamp,
        userInput,
        ...(plan ? { plan } : {}),
        ...(modelPath ? { modelPath } : {}),
        success,
        ...(!success && errorMessage ? { error: errorMessage } : {})
      };

      output.push(entry);
    }

    return output;
  }

  private async pathExists(path: string): Promise<boolean> {
    try {
      await stat(path);
      return true;
    } catch {
      return false;
    }
  }
}
