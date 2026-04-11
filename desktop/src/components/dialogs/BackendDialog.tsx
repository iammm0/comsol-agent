import { useMemo } from "react";
import { useAppState } from "../../context/AppStateContext";
import {
  getProviderCatalog,
  getProviderLabel,
  saveApiConfig,
  loadApiConfig,
  type LLMBackendId,
} from "../../lib/apiConfig";

export function BackendDialog({ onClose }: { onClose: () => void }) {
  const { dispatch, addMessage, state } = useAppState();
  const providers = useMemo(() => getProviderCatalog(), []);

  const selectBackend = (id: LLMBackendId) => {
    dispatch({ type: "SET_BACKEND", backend: id });
    saveApiConfig({ ...loadApiConfig(), preferred_backend: id });
    addMessage("system", "已选择后端: " + getProviderLabel(id));
    onClose();
  };

  return (
    <>
      <div className="dialog-header">LLM 后端</div>
      <div className="dialog-body">
        {providers.map((provider) => (
          <div
            key={provider.id}
            className="dialog-option"
            onClick={() => selectBackend(provider.id)}
          >
            <span className="dialog-option-name">
              {provider.label}
              {state.backend === provider.id ? "（当前）" : ""}
            </span>
            <span className="dialog-option-desc">{provider.description}</span>
          </div>
        ))}
      </div>
    </>
  );
}
