import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type KeyboardEvent,
} from "react";
import { useAppState } from "../context/AppStateContext";
import { useBridge } from "../hooks/useBridge";
import { SLASH_COMMANDS } from "../lib/types";

export function Prompt() {
  const { state } = useAppState();
  const { handleSubmit } = useBridge();
  const [value, setValue] = useState("");
  const [showSlash, setShowSlash] = useState(false);
  const [slashIndex, setSlashIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const filteredSlash = value.startsWith("/")
    ? SLASH_COMMANDS.filter((c) =>
        c.display.startsWith(value.toLowerCase().split(/\s/)[0])
      )
    : [];

  useEffect(() => {
    setShowSlash(value.startsWith("/") && filteredSlash.length > 0);
    setSlashIndex(0);
  }, [value, filteredSlash.length]);

  const submit = useCallback(() => {
    const text = value.trim();
    if (!text || state.busy) return;
    handleSubmit(text);
    setValue("");
    setShowSlash(false);
  }, [value, state.busy, handleSubmit]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (showSlash && filteredSlash.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setSlashIndex((i) => Math.min(i + 1, filteredSlash.length - 1));
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          setSlashIndex((i) => Math.max(i - 1, 0));
          return;
        }
        if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey)) {
          e.preventDefault();
          const cmd = filteredSlash[slashIndex];
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
    [showSlash, filteredSlash, slashIndex, submit, handleSubmit]
  );

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 200) + "px";
    }
  }, []);

  return (
    <div className="prompt-area">
      <div className="prompt-wrapper" style={{ position: "relative" }}>
        {showSlash && (
          <div className="slash-dropdown">
            {filteredSlash.map((cmd, i) => (
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
        <div className="prompt-tags">
          <span
            className={`prompt-tag ${state.mode === "plan" ? "plan" : "run"}`}
          >
            {state.mode === "plan" ? "Plan" : "Build"}
          </span>
        </div>
        <textarea
          ref={textareaRef}
          className="prompt-input"
          rows={1}
          placeholder="输入建模需求或 / 命令..."
          value={value}
          disabled={state.busy}
          onChange={(e) => {
            setValue(e.target.value);
            autoResize();
          }}
          onKeyDown={handleKeyDown}
        />
        <button
          className="prompt-send"
          disabled={state.busy || !value.trim()}
          onClick={submit}
          title="发送 (Enter)"
        >
          ↑
        </button>
      </div>
    </div>
  );
}
