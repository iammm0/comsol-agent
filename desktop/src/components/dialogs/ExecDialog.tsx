import { useState, type KeyboardEvent } from "react";
import { useAppState } from "../../context/AppStateContext";
import { useBridge } from "../../hooks/useBridge";

export function ExecDialog({ onClose }: { onClose: () => void }) {
  const { state } = useAppState();
  const { sendCommand } = useBridge();
  const [step, setStep] = useState<"type" | "path">("type");
  const [codeOnly, setCodeOnly] = useState(false);
  const [path, setPath] = useState("");

  const selectType = (isCodeOnly: boolean) => {
    setCodeOnly(isCodeOnly);
    setStep("path");
  };

  const submitPath = () => {
    const trimmed = path.trim();
    if (!trimmed) return;
    onClose();
    sendCommand("exec", {
      path: trimmed,
      code_only: codeOnly,
      output: state.outputDefault ?? undefined,
    });
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submitPath();
    }
  };

  return (
    <>
      <div className="dialog-header">执行 JSON 计划</div>
      <div className="dialog-body">
        <div className="exec-step-indicator">
          <span className={`exec-step ${step === "type" ? "active" : ""}`}>
            1. 执行方式
          </span>
          <span className={`exec-step ${step === "path" ? "active" : ""}`}>
            2. 文件路径
          </span>
        </div>

        {step === "type" && (
          <>
            <div
              className="dialog-option"
              onClick={() => selectType(false)}
            >
              <span className="dialog-option-name">
                根据 JSON 文件创建模型
              </span>
              <span className="dialog-option-desc">完整执行</span>
            </div>
            <div
              className="dialog-option"
              onClick={() => selectType(true)}
            >
              <span className="dialog-option-name">仅生成 Java 代码</span>
              <span className="dialog-option-desc">只生成代码不执行</span>
            </div>
          </>
        )}

        {step === "path" && (
          <>
            <input
              className="dialog-input"
              autoFocus
              placeholder="例如 plan.json"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <div className="dialog-actions">
              <button
                className="dialog-btn secondary"
                onClick={() => setStep("type")}
              >
                上一步
              </button>
              <button
                className="dialog-btn primary"
                disabled={!path.trim()}
                onClick={submitPath}
              >
                执行
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
