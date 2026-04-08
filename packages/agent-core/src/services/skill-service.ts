import { mkdir, readFile, readdir, stat } from "node:fs/promises";
import { basename, join } from "node:path";
import type { SkillDocument } from "../types/runtime.js";

interface FrontMatterMap {
  name?: string;
  description?: string;
  tags?: string[];
  triggers?: string[];
}

function parseFrontMatter(raw: string): { frontMatter: FrontMatterMap; body: string } {
  if (!raw.startsWith("---\n")) {
    return { frontMatter: {}, body: raw.trim() };
  }

  const end = raw.indexOf("\n---\n", 4);
  if (end < 0) {
    return { frontMatter: {}, body: raw.trim() };
  }

  const frontMatterRaw = raw.slice(4, end);
  const body = raw.slice(end + 5).trim();
  const frontMatter: FrontMatterMap = {};

  for (const line of frontMatterRaw.split("\n")) {
    const idx = line.indexOf(":");
    if (idx < 0) {
      continue;
    }
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    if (key === "name") frontMatter.name = value;
    if (key === "description") frontMatter.description = value;
    if (key === "tags") {
      frontMatter.tags = value
        .replace(/[\[\]"]/g, "")
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean);
    }
    if (key === "triggers") {
      frontMatter.triggers = value
        .replace(/[\[\]"]/g, "")
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean);
    }
  }

  return { frontMatter, body };
}

export class SkillService {
  private readonly skillsRoot: string;
  private skillCache: SkillDocument[] = [];

  public constructor(skillsRoot: string) {
    this.skillsRoot = skillsRoot;
  }

  public async reload(): Promise<void> {
    this.skillCache = [];
    const entries = await readdir(this.skillsRoot, { withFileTypes: true });

    for (const entry of entries) {
      if (!entry.isDirectory()) {
        continue;
      }
      const skillMdPath = join(this.skillsRoot, entry.name, "SKILL.md");
      try {
        const info = await stat(skillMdPath);
        if (!info.isFile()) {
          continue;
        }
        const content = await readFile(skillMdPath, "utf8");
        const parsed = parseFrontMatter(content);
        this.skillCache.push({
          id: entry.name,
          name: parsed.frontMatter.name ?? entry.name,
          description: parsed.frontMatter.description ?? "",
          tags: parsed.frontMatter.tags ?? [],
          triggers: parsed.frontMatter.triggers ?? [],
          body: parsed.body,
          filePath: skillMdPath
        });
      } catch {
        continue;
      }
    }
  }

  public getAll(): SkillDocument[] {
    return [...this.skillCache];
  }

  public findRelevant(query: string, topK: number): SkillDocument[] {
    const normalized = query.toLowerCase();
    const scored = this.skillCache.map((skill) => {
      let score = 0;
      if (skill.name.toLowerCase().includes(normalized)) {
        score += 10;
      }
      for (const tag of skill.tags) {
        if (normalized.includes(tag.toLowerCase())) {
          score += 3;
        }
      }
      for (const trigger of skill.triggers) {
        if (normalized.includes(trigger.toLowerCase())) {
          score += 5;
        }
      }
      if (skill.body.toLowerCase().includes(normalized)) {
        score += 1;
      }
      return { skill, score };
    });

    return scored
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, topK)
      .map((item) => item.skill);
  }

  public async ensureInitialized(): Promise<void> {
    await mkdir(this.skillsRoot, { recursive: true });
    if (this.skillCache.length === 0) {
      await this.reload();
    }
  }

  public toSummary(skills: SkillDocument[]): string {
    if (skills.length === 0) {
      return "";
    }

    const lines: string[] = [];
    lines.push("Relevant skills:");
    for (const skill of skills) {
      lines.push(`- ${basename(skill.filePath)} (${skill.name}): ${skill.description}`);
    }
    return lines.join("\n");
  }
}
