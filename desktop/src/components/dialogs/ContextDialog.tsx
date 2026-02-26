import { useAppState } from "../../context/AppStateContext";
import { useBridge } from "../../hooks/useBridge";

const OPTIONS = [
  { cmd: "context_show", name: "查看摘要", description: "显示对话上下文摘要" },
  { cmd: "context_history", name: "查看历史", description: "显示最近对话记录" },
  { cmd: "context_stats", name: "统计信息", description: "显示会话统计数据" },
  { cmd: "context_clear", name: "清除历史", description: "清除当前对话历史" },
];

export function ContextDialog({ onClose }: { onClose: () => void }) {
  const { addMessage } = useAppState();
  const { sendCommand } = useBridge();

  const select = (cmd: string) => {
    onClose();
    addMessage("user", `/${cmd.replace("_", " ")}`);
    const payload = cmd === "context_history" ? { limit: 10 } : {};
    sendCommand(cmd, payload);
  };

  return (
    <>
      <div className="dialog-header">上下文</div>
      <div className="dialog-body">
        {OPTIONS.map((opt) => (
          <div
            key={opt.cmd}
            className="dialog-option"
            onClick={() => select(opt.cmd)}
          >
            <span className="dialog-option-name">{opt.name}</span>
            <span className="dialog-option-desc">{opt.description}</span>
          </div>
        ))}
      </div>
    </>
  );
}
