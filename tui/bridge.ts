/**
 * 桥接客户端：spawn Python tui-bridge，通过 stdin/stdout JSON 行通信。
 * 优先使用 PATH 中的 comsol-agent，否则从仓库根运行 python cli.py tui-bridge。
 * 子进程 stderr 写入 tui-bridge.log，不直接打到终端，避免与 TUI 界面混在一起；执行进度通过事件在 TUI 内展示。
 */
import { join } from "path";
import { createWriteStream, existsSync } from "fs";

export type BridgeResponse = { ok: boolean; message: string };

export type RunEvent = {
  _event: true;
  type: string;
  data: Record<string, unknown>;
  iteration?: number;
};

function findBridgeCmd(): { cmd: string[]; cwd: string } {
  const root = join(import.meta.dir, "..");
  const cliPath = join(root, "cli.py");

  // 1. 若用户已安装 comsol-agent 到 PATH，优先使用
  try {
    const which = Bun.which("comsol-agent");
    if (which) return { cmd: [which, "tui-bridge"], cwd: root };
  } catch {
    // ignore
  }

  // 2. 优先使用项目 venv 中的 Python（依赖均在其中）
  const isWin = process.platform === "win32";
  const venvPython = isWin
    ? join(root, ".venv", "Scripts", "python.exe")
    : join(root, ".venv", "bin", "python3");
  if (existsSync(venvPython)) {
    return { cmd: [venvPython, cliPath, "tui-bridge"], cwd: root };
  }

  // 3. 尝试 uv run（自动激活 venv）
  try {
    const uvPath = Bun.which("uv");
    if (uvPath) {
      return { cmd: [uvPath, "run", "python", cliPath, "tui-bridge"], cwd: root };
    }
  } catch {
    // ignore
  }

  // 4. 回退到系统 Python
  const python = isWin ? "py" : "python3";
  const pyArgs = isWin ? ["-3", cliPath, "tui-bridge"] : [cliPath, "tui-bridge"];
  return { cmd: [python, ...pyArgs], cwd: root };
}

export function createBridge(): {
  send: (req: Record<string, unknown>) => Promise<BridgeResponse>;
  sendStream: (
    req: Record<string, unknown>,
    onEvent: (evt: RunEvent) => void
  ) => Promise<BridgeResponse>;
  close: () => void;
} {
  const { cmd, cwd } = findBridgeCmd();
  const stderrLogPath = join(import.meta.dir, "tui-bridge.log");
  const stderrStream = createWriteStream(stderrLogPath, { flags: "a" });

  const proc = Bun.spawn({
    cmd,
    cwd,
    stdin: "pipe",
    stdout: "pipe",
    stderr: "pipe",
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  });

  // 消费 stderr，写入日志文件，避免 Python logging 直接渲染到 TUI 终端
  (async () => {
    const decoder = new TextDecoder();
    const reader = proc.stderr.getReader();
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        stderrStream.write(chunk);
      }
    } finally {
      reader.releaseLock();
      stderrStream.end();
    }
  })();

  type Resolver = (v: BridgeResponse) => void;
  let pendingResolve: Resolver | null = null;
  let pendingStreamResolve: Resolver | null = null;
  let onEventCallback: ((evt: RunEvent) => void) | null = null;
  const decoder = new TextDecoder();
  let buf = "";

  const consume = (res: BridgeResponse) => {
    const cb = pendingResolve;
    pendingResolve = null;
    if (cb) cb(res);
  };

  const processLine = (line: string) => {
    try {
      const obj = JSON.parse(line) as Record<string, unknown>;
      if (obj._event === true) {
        if (onEventCallback) onEventCallback(obj as RunEvent);
      } else {
        const res = obj as BridgeResponse;
        if (pendingStreamResolve) {
          const cb = pendingStreamResolve;
          pendingStreamResolve = null;
          onEventCallback = null;
          cb(res);
        } else {
          consume(res);
        }
      }
    } catch {
      const fallback: BridgeResponse = { ok: false, message: `无效响应: ${line.slice(0, 80)}` };
      if (pendingStreamResolve) {
        pendingStreamResolve(fallback);
        pendingStreamResolve = null;
        onEventCallback = null;
      } else {
        consume(fallback);
      }
    }
  };

  (async () => {
    const reader = proc.stdout.getReader();
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split(/\r?\n/);
        buf = lines.pop() ?? "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          processLine(trimmed);
        }
      }
      if (buf.trim()) {
        processLine(buf.trim());
      }
    } finally {
      reader.releaseLock();
    }
  })();

  function send(req: Record<string, unknown>): Promise<BridgeResponse> {
    return new Promise((resolve) => {
      pendingResolve = resolve;
      proc.stdin.write(JSON.stringify(req) + "\n");
    });
  }

  function sendStream(
    req: Record<string, unknown>,
    onEvent: (evt: RunEvent) => void
  ): Promise<BridgeResponse> {
    return new Promise((resolve) => {
      pendingStreamResolve = resolve;
      onEventCallback = onEvent;
      proc.stdin.write(JSON.stringify(req) + "\n");
    });
  }

  function close() {
    try {
      proc.kill();
    } catch {
      // ignore
    }
  }

  return { send, sendStream, close };
}
