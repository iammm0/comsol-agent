import { mkdir, cp, rm, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const workspaceRoot = resolve(__dirname, "../../..");
const desktopRoot = resolve(__dirname, "..");
const sidecarRoot = resolve(workspaceRoot, "apps/agent-sidecar");
const javaSidecarRoot = resolve(workspaceRoot, "apps/comsol-java-sidecar");
const skillsRoot = resolve(workspaceRoot, "skills");
const promptsRoot = resolve(workspaceRoot, "prompts");
const resourcesRoot = resolve(desktopRoot, "src-tauri/resources");

function run(command, args, cwd) {
  const childEnv = { ...process.env };
  if (typeof childEnv.JAVA_HOME === "string" && childEnv.JAVA_HOME.toLowerCase().endsWith("\\bin")) {
    childEnv.JAVA_HOME = dirname(childEnv.JAVA_HOME);
  }

  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(command, args, {
      cwd,
      stdio: "inherit",
      shell: process.platform === "win32",
      env: childEnv
    });
    child.on("exit", (code) => {
      if (code === 0) {
        resolvePromise();
      } else {
        rejectPromise(new Error(`${command} ${args.join(" ")} failed with exit code ${code}`));
      }
    });
    child.on("error", rejectPromise);
  });
}

async function ensureDir(path) {
  await mkdir(path, { recursive: true });
}

async function canReachGradleDistributionHost() {
  if (process.env.MPH_AGENT_SKIP_JAVA_BUILD === "1") {
    return false;
  }

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);
    const response = await fetch("https://services.gradle.org/", {
      method: "HEAD",
      signal: controller.signal
    });
    clearTimeout(timer);
    return response.ok;
  } catch {
    return false;
  }
}

async function prepareNodeSidecar() {
  await run("npm", ["run", "build", "-w", "@mph-agent/agent-sidecar"], workspaceRoot);
  const source = resolve(sidecarRoot, "dist");
  const dest = resolve(resourcesRoot, "sidecar");
  await rm(dest, { recursive: true, force: true });
  await ensureDir(dest);
  await cp(source, dest, { recursive: true });
}

async function prepareJavaSidecar() {
  const gradlew = process.platform === "win32" ? "gradlew.bat" : "./gradlew";
  const hasGradleWrapper = existsSync(resolve(javaSidecarRoot, gradlew));
  const canReachGradle = await canReachGradleDistributionHost();

  if (hasGradleWrapper && canReachGradle) {
    try {
      await run(gradlew, ["shadowJar"], javaSidecarRoot);
    } catch (error) {
      console.warn(
        `[prepare-runtime] Java sidecar build skipped: ${
          error instanceof Error ? error.message : String(error)
        }`
      );
    }
  } else if (hasGradleWrapper && !canReachGradle) {
    console.warn(
      "[prepare-runtime] Gradle distribution host unreachable (or MPH_AGENT_SKIP_JAVA_BUILD=1); skipping Java sidecar build."
    );
  }

  const sourceJar = resolve(javaSidecarRoot, "build/libs/comsol-java-sidecar-all.jar");
  const jarExists = existsSync(sourceJar);
  const destDir = resolve(resourcesRoot, "sidecar/java");
  await ensureDir(destDir);
  if (jarExists) {
    await cp(sourceJar, resolve(destDir, "comsol-java-sidecar-all.jar"));
  } else {
    console.warn(
      "[prepare-runtime] Missing comsol-java-sidecar-all.jar; desktop will fallback to mock COMSOL mode."
    );
  }
}

async function prepareRuntimeDirs() {
  await ensureDir(resolve(resourcesRoot, "runtime/java"));
  await ensureDir(resolve(resourcesRoot, "runtime/node"));
}

async function syncDirectoryIfExists(source, dest) {
  if (!existsSync(source)) {
    return;
  }
  await rm(dest, { recursive: true, force: true });
  await ensureDir(dest);
  await cp(source, dest, { recursive: true });
}

async function prepareKnowledgeResources() {
  await syncDirectoryIfExists(skillsRoot, resolve(resourcesRoot, "skills"));
  await syncDirectoryIfExists(promptsRoot, resolve(resourcesRoot, "prompts"));
}

async function main() {
  await prepareRuntimeDirs();
  await prepareNodeSidecar();
  await prepareJavaSidecar();
  await prepareKnowledgeResources();

  const sidecarStat = await stat(resolve(resourcesRoot, "sidecar/index.js"));
  if (!sidecarStat.isFile()) {
    throw new Error("Missing sidecar entry after prepare-runtime");
  }
  console.log("runtime prepared");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
