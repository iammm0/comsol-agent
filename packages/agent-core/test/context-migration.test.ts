import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { ContextService } from "../src/services/context-service.js";

const cleanupTargets: string[] = [];

async function createWorkspace(): Promise<{
  root: string;
  legacyRoot: string;
  targetRoot: string;
}> {
  const root = await mkdtemp(join(tmpdir(), "mph-agent-context-migration-"));
  cleanupTargets.push(root);
  const legacyRoot = join(root, ".context");
  const targetRoot = join(root, ".context-ts");
  await mkdir(legacyRoot, { recursive: true });
  return { root, legacyRoot, targetRoot };
}

afterEach(async () => {
  while (cleanupTargets.length > 0) {
    const target = cleanupTargets.pop();
    if (!target) {
      continue;
    }
    await rm(target, { recursive: true, force: true });
  }
});

describe("ContextService migration", () => {
  it("imports legacy .context conversation data into .context-ts", async () => {
    const { legacyRoot, targetRoot } = await createWorkspace();
    const conversationId = "conv_legacy_a";
    const legacyConvDir = join(legacyRoot, conversationId);
    await mkdir(legacyConvDir, { recursive: true });

    const legacyHistory = [
      {
        id: "legacy-1",
        ts: "2026-01-01T00:00:00.000Z",
        input: "legacy prompt one",
        ok: true,
        model_path: "models/legacy-1.mph",
        plan: { steps: [{ label: "Create geometry" }] }
      },
      {
        timestamp: "2026-01-01T00:05:00.000Z",
        prompt: "legacy prompt two",
        success: false,
        error: "legacy solve failed"
      }
    ];
    await writeFile(join(legacyConvDir, "history.json"), JSON.stringify(legacyHistory, null, 2), "utf8");
    await writeFile(
      join(legacyConvDir, "summary.json"),
      JSON.stringify(
        {
          summary: "legacy summary text",
          lastUpdated: "2026-01-01T00:06:00.000Z",
          totalConversations: 2,
          recentActions: ["Create geometry"],
          preferences: { backend: "ollama" }
        },
        null,
        2
      ),
      "utf8"
    );
    await writeFile(join(legacyConvDir, "latest_model.txt"), "models/legacy-1.mph", "utf8");
    await writeFile(join(legacyConvDir, "operations.md"), "# Operations\n\nlegacy op\n", "utf8");

    const service = new ContextService(targetRoot);
    await service.init();

    const history = await service.readHistory(conversationId);
    expect(history.length).toBe(2);
    expect(history[0]?.id).toBe("legacy-1");
    expect(history[0]?.userInput).toBe("legacy prompt one");
    expect(history[0]?.modelPath).toBe("models/legacy-1.mph");
    expect(history[1]?.userInput).toBe("legacy prompt two");
    expect(history[1]?.success).toBe(false);
    expect(history[1]?.error).toBe("legacy solve failed");

    const latestModel = await service.getLatestModelPath(conversationId);
    expect(latestModel).toBe("models/legacy-1.mph");

    const summary = await service.getSummary(conversationId);
    expect(summary?.summary).toBe("legacy summary text");

    const operations = await readFile(join(targetRoot, conversationId, "operations.md"), "utf8");
    expect(operations.includes("legacy op")).toBe(true);

    const markerPath = join(targetRoot, ".migration-v1.json");
    const marker = JSON.parse(await readFile(markerPath, "utf8")) as {
      importedConversations: number;
      skippedConversations: number;
      errors: string[];
    };
    expect(marker.importedConversations).toBe(1);
    expect(marker.errors.length).toBe(0);
  });

  it("does not duplicate data after migration marker exists", async () => {
    const { legacyRoot, targetRoot } = await createWorkspace();
    const conversationId = "conv_legacy_b";
    const legacyConvDir = join(legacyRoot, conversationId);
    await mkdir(legacyConvDir, { recursive: true });
    await writeFile(
      join(legacyConvDir, "history.json"),
      JSON.stringify([{ input: "single entry", ok: true }], null, 2),
      "utf8"
    );

    const service = new ContextService(targetRoot);
    await service.init();
    await service.init();

    const history = await service.readHistory(conversationId);
    expect(history.length).toBe(1);
    expect(history[0]?.userInput).toBe("single entry");
  });
});

