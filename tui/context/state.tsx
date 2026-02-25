import { createBridge, type RunEvent } from "../bridge";
import {
  createContext,
  useContext,
  createSignal,
  onCleanup,
  type ParentProps,
} from "solid-js";

export type MessageRole = "user" | "assistant" | "system";

export type ChatMessage = {
  id: string;
  role: MessageRole;
  text: string;
  time: number;
  success?: boolean;
  tool?: string;
  events?: RunEvent[];
};

type TuiStateContextValue = {
  messages: () => ChatMessage[];
  addMessage: (role: MessageRole, text: string, opts?: { success?: boolean; tool?: string }) => void;
  mode: () => "run" | "plan";
  setMode: (m: "run" | "plan") => void;
  backend: () => string | null;
  setBackend: (b: string | null) => void;
  outputDefault: () => string | null;
  setOutputDefault: (o: string | null) => void;
  execCodeOnly: () => boolean;
  setExecCodeOnly: (v: boolean) => void;
  busy: () => boolean;
  sessionTitle: () => string;
  handleBridge: (cmd: string, payload?: Record<string, unknown>) => Promise<void>;
  handleSubmit: (raw: string) => void;
};

const TuiStateContext = createContext<TuiStateContextValue | undefined>(undefined);

let messageCounter = 0;
function nextId(): string {
  return `msg_${++messageCounter}_${Date.now()}`;
}

export function TuiStateProvider(props: ParentProps) {
  const [messages, setMessages] = createSignal<ChatMessage[]>([]);
  const [mode, setMode] = createSignal<"run" | "plan">("run");
  const [backend, setBackend] = createSignal<string | null>(null);
  const [outputDefault, setOutputDefault] = createSignal<string | null>(null);
  const [execCodeOnly, setExecCodeOnly] = createSignal(false);
  const [busy, setBusy] = createSignal(false);
  const [sessionTitle, setSessionTitle] = createSignal("新会话");

  let bridge: ReturnType<typeof createBridge> | null = null;

  function addMessage(role: MessageRole, text: string, opts?: { success?: boolean; tool?: string; events?: RunEvent[] }) {
    const msg: ChatMessage = {
      id: nextId(),
      role,
      text,
      time: Date.now(),
      success: opts?.success,
      tool: opts?.tool,
      events: opts?.events,
    };
    setMessages((prev) => [...prev, msg]);
  }

  function appendRunEvent(evt: RunEvent) {
    setMessages((prev) => {
      const last = prev.length - 1;
      if (last < 0) return prev;
      const m = prev[last];
      if (m.role !== "assistant") return prev;
      const events = [...(m.events ?? []), evt];
      return [...prev.slice(0, last), { ...m, events }];
    });
  }

  function finalizeRunMessage(text: string, success: boolean) {
    setMessages((prev) => {
      const last = prev.length - 1;
      if (last < 0) return prev;
      const m = prev[last];
      if (m.role !== "assistant") return prev;
      return [...prev.slice(0, last), { ...m, text, success }];
    });
  }

  // Create bridge synchronously so it's ready before first submit (onMount runs after paint and was too late)
  try {
    bridge = createBridge();
  } catch (e) {
    addMessage("system", "桥接启动失败: " + String(e), { success: false });
  }

  onCleanup(() => {
    bridge?.close();
  });

  async function handleBridge(cmd: string, payload: Record<string, unknown> = {}) {
    if (!bridge) {
      addMessage("system", "桥接未就绪", { success: false });
      return;
    }
    setBusy(true);

    if (cmd === "run") {
      addMessage("assistant", "", { events: [] });
      try {
        const res = await bridge.sendStream({ cmd, ...payload }, (evt) => {
          appendRunEvent(evt);
        });
        finalizeRunMessage(res.message, res.ok);
      } catch (e) {
        finalizeRunMessage("请求失败: " + String(e), false);
      } finally {
        setBusy(false);
      }
      return;
    }

    try {
      const res = await bridge.send({ cmd, ...payload });
      addMessage("assistant", res.message, { success: res.ok });
    } catch (e) {
      addMessage("assistant", "请求失败: " + String(e), { success: false });
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(raw: string) {
    const line = raw.trim();
    if (!line) return;

    if (line.startsWith("/")) {
      const cmd = line.toLowerCase().split(/\s/)[0];
      if (cmd === "/quit" || cmd === "/exit") {
        process.exit(0);
        return;
      }
      if (cmd === "/run") {
        setMode("run");
        addMessage("system", "已切换为默认模式（run）");
        return;
      }
      if (cmd === "/plan") {
        setMode("plan");
        addMessage("system", "已切换为计划模式（plan）");
        return;
      }
      if (cmd === "/help") {
        addMessage("system", HELP_TEXT);
        return;
      }
      if (cmd === "/demo") {
        addMessage("user", line);
        handleBridge("demo");
        return;
      }
      if (cmd === "/doctor") {
        addMessage("user", line);
        handleBridge("doctor");
        return;
      }
      if (cmd === "/context" || cmd === "/backend" || cmd === "/exec" || cmd === "/output") {
        return;
      }
      addMessage("system", "未知斜杠命令: " + cmd + "，输入 /help 查看帮助", { success: false });
      return;
    }

    addMessage("user", line);

    // Set title from first user message
    if (messages().filter((m) => m.role === "user").length <= 1) {
      setSessionTitle(line.length > 50 ? line.slice(0, 47) + "..." : line);
    }

    if (mode() === "plan") {
      handleBridge("plan", { input: line });
    } else {
      handleBridge("run", {
        input: line,
        output: outputDefault() ?? undefined,
        backend: backend() ?? undefined,
        use_react: true,
        no_context: false,
      });
    }
  }

  const value: TuiStateContextValue = {
    messages,
    addMessage,
    mode,
    setMode,
    backend,
    setBackend,
    outputDefault,
    setOutputDefault,
    execCodeOnly,
    setExecCodeOnly,
    busy,
    sessionTitle,
    handleBridge,
    handleSubmit,
  };

  return (
    <TuiStateContext.Provider value={value}>
      {props.children}
    </TuiStateContext.Provider>
  );
}

export function useTuiState() {
  const ctx = useContext(TuiStateContext);
  if (!ctx) throw new Error("useTuiState must be used within TuiStateProvider");
  return ctx;
}

const HELP_TEXT =
  "命令\n" +
  "  /quit, /exit  退出\n" +
  "  /run          默认模式（自然语言 → 模型）\n" +
  "  /plan         计划模式（自然语言 → JSON）\n" +
  "  /exec         根据 JSON 计划创建模型或生成代码\n" +
  "  /demo         演示示例\n" +
  "  /doctor       环境诊断\n" +
  "  /context      查看或清除对话历史\n" +
  "  /backend      选择 LLM 后端\n" +
  "  /output       设置默认输出文件名\n" +
  "  /help         本帮助";
