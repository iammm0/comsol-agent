import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useAppState } from "../context/AppStateContext";

const MEMORY_SIDEBAR_COLLAPSED_KEY = "mph-agent-memory-sidebar-collapsed";

interface MemoryPreviewState {
  memoryText: string;
  promptContextText: string;
  loading: boolean;
  error: string;
  updatedAt: number | null;
}

function splitPreviewLines(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) =>
      line
        .trim()
        .replace(/^[-*]\s*/, "")
        .replace(/^\d+[.)]\s*/, "")
        .trim()
    )
    .filter(Boolean);
}

function formatUpdatedAt(value: number | null): string {
  if (!value) return "尚未刷新";
  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

async function readContextCommand(
  cmd: "context_get_summary" | "context_prompt_context",
  conversationId: string
): Promise<string> {
  const res = await invoke<{ ok: boolean; message: string }>("bridge_send", {
    cmd,
    payload: { conversation_id: conversationId },
  });
  if (!res.ok) {
    throw new Error(res.message || "读取上下文失败");
  }
  return res.message || "";
}

export function ContextMemorySidebar() {
  const { state } = useAppState();
  const cid = state.currentConversationId;
  const requestRef = useRef(0);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(MEMORY_SIDEBAR_COLLAPSED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [preview, setPreview] = useState<MemoryPreviewState>({
    memoryText: "",
    promptContextText: "",
    loading: false,
    error: "",
    updatedAt: null,
  });

  const refresh = useCallback(async () => {
    const conversationId = cid;
    const requestId = ++requestRef.current;
    if (!conversationId) {
      setPreview({
        memoryText: "",
        promptContextText: "",
        loading: false,
        error: "",
        updatedAt: null,
      });
      return;
    }

    setPreview((current) => ({ ...current, loading: true, error: "" }));
    try {
      const [memoryText, promptContextText] = await Promise.all([
        readContextCommand("context_get_summary", conversationId),
        readContextCommand("context_prompt_context", conversationId),
      ]);
      if (requestRef.current !== requestId) return;
      setPreview({
        memoryText,
        promptContextText,
        loading: false,
        error: "",
        updatedAt: Date.now(),
      });
    } catch (error) {
      if (requestRef.current !== requestId) return;
      setPreview((current) => ({
        ...current,
        loading: false,
        error: String(error),
        updatedAt: Date.now(),
      }));
    }
  }, [cid]);

  useEffect(() => {
    if (state.busyConversationId != null) return;
    void refresh();
    const timer = window.setTimeout(() => {
      void refresh();
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [refresh, state.busyConversationId]);

  useEffect(() => {
    try {
      localStorage.setItem(
        MEMORY_SIDEBAR_COLLAPSED_KEY,
        collapsed ? "1" : "0"
      );
    } catch {
      // ignore
    }
  }, [collapsed]);

  const memoryLines = useMemo(
    () => splitPreviewLines(preview.memoryText),
    [preview.memoryText]
  );
  const promptContextLines = useMemo(
    () => splitPreviewLines(preview.promptContextText),
    [preview.promptContextText]
  );

  const hasMemory = memoryLines.length > 0;
  const hasPromptContext = promptContextLines.length > 0;
  const previewCount = Math.max(memoryLines.length, promptContextLines.length);
  const statusTone = preview.error
    ? "error"
    : preview.loading
      ? "loading"
      : hasMemory || hasPromptContext
        ? "ready"
        : "idle";

  return (
    <aside
      className={`context-memory-sidebar ${collapsed ? "collapsed" : ""}`}
      aria-label="当前对话记忆上下文"
    >
      <header className="context-memory-sidebar__header">
        <button
          type="button"
          className="context-memory-sidebar__toggle"
          aria-expanded={!collapsed}
          aria-label={collapsed ? "展开记忆预览" : "收起记忆预览"}
          title={collapsed ? "展开记忆预览" : "收起记忆预览"}
          onClick={() => setCollapsed((value) => !value)}
        >
          {collapsed ? "<" : ">"}
        </button>

        {collapsed ? (
          <div className="context-memory-sidebar__collapsed-body">
            <span className="context-memory-sidebar__eyebrow">Memory</span>
            <span className="context-memory-sidebar__collapsed-title">
              记忆预览
            </span>
            <span
              className={`context-memory-sidebar__collapsed-dot ${statusTone}`}
              aria-hidden="true"
            />
            <span className="context-memory-sidebar__collapsed-count">
              {previewCount}
            </span>
          </div>
        ) : (
          <>
            <div className="context-memory-sidebar__heading">
              <span className="context-memory-sidebar__eyebrow">Memory</span>
              <h2>当前对话记忆</h2>
            </div>
            <button
              type="button"
              className="context-memory-sidebar__refresh"
              onClick={() => void refresh()}
              disabled={preview.loading}
              title="刷新记忆上下文"
            >
              {preview.loading ? "刷新中" : "刷新"}
            </button>
          </>
        )}
      </header>

      {!collapsed && (
        <>
          <div className="context-memory-sidebar__meta">
            <span>最后更新：{formatUpdatedAt(preview.updatedAt)}</span>
            {preview.loading && <span>正在读取 Bridge 上下文</span>}
          </div>

          {preview.error && (
            <div className="context-memory-sidebar__error" role="status">
              {preview.error}
            </div>
          )}

          <section className="context-memory-card">
            <div className="context-memory-card__head">
              <h3>Agent 记住的内容</h3>
              <span>{memoryLines.length} 条</span>
            </div>
            {hasMemory ? (
              <ul className="context-memory-list">
                {memoryLines.map((line, index) => (
                  <li key={`${index}-${line}`}>{line}</li>
                ))}
              </ul>
            ) : (
              <p className="context-memory-empty">
                暂无手动或长期记忆。对话完成后，agent 会把稳定偏好和建模线索整理到这里。
              </p>
            )}
          </section>

          <section className="context-memory-card context-memory-card--context">
            <div className="context-memory-card__head">
              <h3>将注入的上下文</h3>
              <span>{promptContextLines.length} 行</span>
            </div>
            {hasPromptContext ? (
              <div className="context-memory-preview">
                {promptContextLines.map((line, index) => (
                  <p key={`${index}-${line}`}>{line}</p>
                ))}
              </div>
            ) : (
              <p className="context-memory-empty">
                暂无可注入上下文。新一轮对话结束后这里会自动刷新。
              </p>
            )}
          </section>
        </>
      )}
    </aside>
  );
}
