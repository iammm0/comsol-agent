import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type KeyboardEvent,
} from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useAppState } from "../context/AppStateContext";
import { useBridge } from "../hooks/useBridge";
import {
  PROMPT_PLUS_MENU_COMMANDS,
  PROMPT_MODE_ITEMS,
} from "../lib/types";
import type { PromptExtensionItem, AgentMode } from "../lib/types";

export function Prompt() {
  const { state, dispatch } = useAppState();
  const { handleSubmit, abortRun, triggerExtensionAction } = useBridge();
  const [value, setValue] = useState("");
  const [modeToast, setModeToast] = useState("");
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const plusWrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (state.editingDraft != null) {
      setValue(state.editingDraft);
      dispatch({ type: "SET_EDITING_DRAFT", text: null });
    }
  }, [state.editingDraft, dispatch]);

  useEffect(() => {
    if (!showPlusMenu) return;
    const onDocMouseDown = (e: MouseEvent) => {
      const el = plusWrapRef.current;
      if (el && !el.contains(e.target as Node)) {
        setShowPlusMenu(false);
      }
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [showPlusMenu]);

  useEffect(() => {
    if (!modeToast) return;
    const timer = window.setTimeout(() => setModeToast(""), 1800);
    return () => window.clearTimeout(timer);
  }, [modeToast]);

  const submit = useCallback(() => {
    const text = value.trim();
    if (!text || state.busyConversationId != null) return;
    handleSubmit(text);
    setValue("");
  }, [value, state.busyConversationId, handleSubmit]);

  const applyMode = useCallback(
    (mode: AgentMode) => {
      if (state.mode === mode) return;
      dispatch({ type: "SET_MODE", mode });
      if (mode === "run") {
        setModeToast("已切换为执行模式（Run）");
      } else if (mode === "discuss") {
        setModeToast("已切换为探讨模式（Discuss），可与 LLM 闲聊");
      } else {
        setModeToast("已切换为规划模式（Plan）");
      }
    },
    [state.mode, dispatch]
  );

  const onPlusSelect = useCallback(
    async (cmd: PromptExtensionItem) => {
      setShowPlusMenu(false);
      if (cmd.name === "case") {
        const selected = await open({
          multiple: false,
          title: "选择要读取的 COMSOL 模型文件",
          filters: [{ name: "COMSOL Model", extensions: ["mph"] }],
        });
        if (typeof selected === "string") {
          await triggerExtensionAction("case", { modelPath: selected });
        }
        return;
      }
      await triggerExtensionAction(cmd.name);
    },
    [triggerExtensionAction]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Escape") {
        if (showPlusMenu) {
          e.preventDefault();
          setShowPlusMenu(false);
          return;
        }
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submit();
      }
    },
    [submit, showPlusMenu]
  );

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 200) + "px";
    }
  }, []);

  const busy = state.busyConversationId != null;

  return (
    <div className="prompt-area">
      {state.discussionReadyForPlan && state.mode === "discuss" && (
        <div className="prompt-plan-nudge" role="status">
          <span className="prompt-plan-nudge__text">
            探讨结论已就绪，可进入规划模式编写建模需求；也可点下方「规划」或 + 菜单中的扩展功能。
          </span>
          <button
            type="button"
            className="prompt-plan-nudge__btn"
            onClick={() => dispatch({ type: "SET_MODE", mode: "plan" })}
          >
            进入规划
          </button>
        </div>
      )}
      <div className="prompt-toolbar">
        {modeToast && <div className="prompt-mode-toast">{modeToast}</div>}
        <div
          className="prompt-mode-segment"
          role="group"
          aria-label="工作模式"
        >
          {PROMPT_MODE_ITEMS.map((item) => (
            <button
              key={item.mode}
              type="button"
              className={`prompt-mode-btn ${item.mode} ${state.mode === item.mode ? "active" : ""}`}
              title={item.title}
              onClick={() => applyMode(item.mode)}
              disabled={busy}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className="prompt-wrapper" style={{ position: "relative" }}>
        <div className="prompt-plus-wrap" ref={plusWrapRef}>
          <button
            type="button"
            className="prompt-plus-btn"
            disabled={busy}
            aria-expanded={showPlusMenu}
            aria-haspopup="menu"
            title="扩展功能"
            onClick={() => setShowPlusMenu((v) => !v)}
          >
            +
          </button>
          {showPlusMenu && (
            <div className="prompt-plus-menu" role="menu">
              {PROMPT_PLUS_MENU_COMMANDS.map((cmd) => (
                <button
                  key={cmd.name}
                  type="button"
                  role="menuitem"
                  className="prompt-plus-menu-item"
                  onClick={() => void onPlusSelect(cmd)}
                >
                  <span className="prompt-plus-menu-cmd">{cmd.label}</span>
                  <span className="prompt-plus-menu-desc">{cmd.description}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <textarea
          ref={textareaRef}
          className="prompt-input"
          rows={1}
          placeholder="输入建模需求…（扩展功能请点击 +）"
          value={value}
          disabled={busy}
          onChange={(e) => {
            setValue(e.target.value);
            autoResize();
          }}
          onKeyDown={handleKeyDown}
        />
        <button
          className="prompt-send"
          disabled={busy || !value.trim()}
          onClick={submit}
          title="发送 (Enter)"
        >
          ↑
        </button>
        {busy && (
          <button
            type="button"
            className="prompt-stop"
            onClick={abortRun}
            title="停止建模"
          >
            停止
          </button>
        )}
      </div>
    </div>
  );
}
