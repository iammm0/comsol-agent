import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type KeyboardEvent,
} from "react";
import { useAppState } from "../context/AppStateContext";
import { useBridge } from "../hooks/useBridge";
import {
  SLASH_COMMANDS,
  PROMPT_PLUS_MENU_COMMANDS,
  PROMPT_MODE_ITEMS,
} from "../lib/types";
import type { SlashCommandItem, AgentMode } from "../lib/types";

export function Prompt() {
  const { state, dispatch } = useAppState();
  const { handleSubmit, abortRun } = useBridge();
  const [value, setValue] = useState("");
  const [modeToast, setModeToast] = useState("");
  const [showSlash, setShowSlash] = useState(false);
  const [slashIndex, setSlashIndex] = useState(0);
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const plusWrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (state.editingDraft != null) {
      setValue(state.editingDraft);
      dispatch({ type: "SET_EDITING_DRAFT", text: null });
    }
  }, [state.editingDraft, dispatch]);

  const filteredSlash = value.startsWith("/")
    ? SLASH_COMMANDS.filter((c: SlashCommandItem) =>
        c.display.startsWith(value.toLowerCase().split(/\s/)[0])
      )
    : [];

  useEffect(() => {
    setShowSlash(value.startsWith("/") && filteredSlash.length > 0);
    setSlashIndex(0);
  }, [value, filteredSlash.length]);

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
    setShowSlash(false);
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
    (cmd: SlashCommandItem) => {
      setShowPlusMenu(false);
      if (cmd.name === "case") {
        setValue("/case ");
        setShowSlash(false);
        requestAnimationFrame(() => {
          textareaRef.current?.focus();
          const el = textareaRef.current;
          if (el) {
            const len = el.value.length;
            el.setSelectionRange(len, len);
          }
        });
        return;
      }
      handleSubmit(cmd.display);
    },
    [handleSubmit]
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
      if (showSlash && filteredSlash.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setSlashIndex((i: number) => Math.min(i + 1, filteredSlash.length - 1));
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          setSlashIndex((i: number) => Math.max(i - 1, 0));
          return;
        }
        if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey)) {
          e.preventDefault();
          const cmd: SlashCommandItem | undefined = filteredSlash[slashIndex];
          if (cmd) {
            handleSubmit(cmd.display);
            setValue("");
            setShowSlash(false);
          }
          return;
        }
      }

      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submit();
      }
    },
    [showSlash, filteredSlash, slashIndex, submit, handleSubmit, showPlusMenu]
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
            探讨结论已就绪，可进入规划模式编写建模需求；也可点下方「规划」或 + 菜单中的命令。
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
        {showSlash && (
          <div className="slash-dropdown">
            {filteredSlash.map((cmd: SlashCommandItem, i: number) => (
              <div
                key={cmd.name}
                className={`slash-item ${i === slashIndex ? "active" : ""}`}
                onMouseEnter={() => setSlashIndex(i)}
                onClick={() => {
                  handleSubmit(cmd.display);
                  setValue("");
                  setShowSlash(false);
                  textareaRef.current?.focus();
                }}
              >
                <span className="slash-item-name">{cmd.display}</span>
                <span className="slash-item-desc">{cmd.description}</span>
              </div>
            ))}
          </div>
        )}
        <div className="prompt-plus-wrap" ref={plusWrapRef}>
          <button
            type="button"
            className="prompt-plus-btn"
            disabled={busy}
            aria-expanded={showPlusMenu}
            aria-haspopup="menu"
            title="命令与工具"
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
                  onClick={() => onPlusSelect(cmd)}
                >
                  <span className="prompt-plus-menu-cmd">{cmd.display}</span>
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
          placeholder="输入建模需求…（仍可直接输入 / 命令）"
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
