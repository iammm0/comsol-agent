import { useState, type KeyboardEvent } from "react";
import { useAppState } from "../../context/AppStateContext";

export function OutputDialog({ onClose }: { onClose: () => void }) {
  const { dispatch, addMessage } = useAppState();
  const [value, setValue] = useState("");

  const submit = () => {
    const name = value.trim() || null;
    dispatch({ type: "SET_OUTPUT", output: name });
    addMessage("system", "默认输出已设为: " + (name ?? "（未设置）"));
    onClose();
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  };

  return (
    <>
      <div className="dialog-header">默认输出文件名</div>
      <div className="dialog-body">
        <input
          className="dialog-input"
          autoFocus
          placeholder="例如 model.mph（留空则自动生成）"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <div className="dialog-actions">
          <button className="dialog-btn secondary" onClick={onClose}>
            取消
          </button>
          <button className="dialog-btn primary" onClick={submit}>
            确定
          </button>
        </div>
      </div>
    </>
  );
}
