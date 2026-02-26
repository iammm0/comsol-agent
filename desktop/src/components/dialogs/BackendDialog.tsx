import { useAppState } from "../../context/AppStateContext";

const BACKENDS = [
  { id: "deepseek", name: "DeepSeek", description: "DeepSeek API" },
  { id: "kimi", name: "Kimi", description: "Moonshot Kimi" },
  { id: "ollama", name: "Ollama", description: "本地 Ollama" },
  {
    id: "openai-compatible",
    name: "OpenAI 兼容中转",
    description: "自定义 OpenAI 兼容 API",
  },
];

export function BackendDialog({ onClose }: { onClose: () => void }) {
  const { dispatch, addMessage } = useAppState();

  const selectBackend = (id: string) => {
    dispatch({ type: "SET_BACKEND", backend: id });
    addMessage("system", "已选择后端: " + id);
    onClose();
  };

  return (
    <>
      <div className="dialog-header">LLM 后端</div>
      <div className="dialog-body">
        {BACKENDS.map((b) => (
          <div
            key={b.id}
            className="dialog-option"
            onClick={() => selectBackend(b.id)}
          >
            <span className="dialog-option-name">{b.name}</span>
            <span className="dialog-option-desc">{b.description}</span>
          </div>
        ))}
      </div>
    </>
  );
}
