import { useState, useEffect, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useTheme, ACCENT_PRESETS } from "../../context/ThemeContext";
import { useAppState } from "../../context/AppStateContext";
import {
  loadApiConfig,
  saveApiConfig,
  apiConfigToEnv,
  type ApiConfig,
  type LLMBackendId,
} from "../../lib/apiConfig";
import type { BridgeResponse, MyComsolModel } from "../../lib/types";

type SettingsTab = "theme" | "llm" | "comsol" | "memory" | "models";

const TABS: { id: SettingsTab; label: string }[] = [
  { id: "theme", label: "主题风格" },
  { id: "llm", label: "LLM 配置" },
  { id: "comsol", label: "COMSOL 配置" },
  { id: "memory", label: "记忆管理" },
  { id: "models", label: "我创建的 COMSOL 模型" },
];

interface SettingsDialogProps {
  onClose: () => void;
}

export function SettingsDialog({ onClose }: SettingsDialogProps) {
  const { themeMode, accentColor, setThemeMode, setAccentColor } = useTheme();
  const { state, dispatch } = useAppState();
  const cid = state.currentConversationId;

  const [activeTab, setActiveTab] = useState<SettingsTab>("theme");
  const [apiConfig, setApiConfig] = useState<ApiConfig>(() => loadApiConfig());
  const [memoryText, setMemoryText] = useState("");
  const [memoryStatus, setMemoryStatus] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("");
  const [ollamaTestResult, setOllamaTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [syncStatus, setSyncStatus] = useState("");
  const [modelsList, setModelsList] = useState<MyComsolModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);

  useEffect(() => {
    setApiConfig(loadApiConfig());
    setOllamaUrl(loadApiConfig().ollama_url);
  }, []);

  /** 保存到本地并同步到后端 .env，加载最新配置 */
  const saveAndSync = useCallback(async (config: ApiConfig, statusKey: "llm" | "comsol") => {
    saveApiConfig(config);
    setApiConfig(loadApiConfig());
    if (statusKey === "llm") setMemoryStatus("正在同步到后端…");
    else setSyncStatus("正在同步到后端…");
    try {
      const res = await invoke<{ ok: boolean; message: string }>("bridge_send", {
        cmd: "config_save",
        payload: { config: apiConfigToEnv(config) },
      });
      const msg = res.ok ? res.message : res.message;
      if (statusKey === "llm") setMemoryStatus(res.ok ? "已保存，" + msg : msg);
      else if (statusKey === "comsol") setSyncStatus(res.ok ? "COMSOL 已保存，" + msg : msg);
      if (!res.ok && statusKey !== "comsol") setSyncStatus(msg);
    } catch (e) {
      const err = "同步失败: " + String(e);
      setSyncStatus(err);
      if (statusKey === "llm") setMemoryStatus(err);
      else if (statusKey === "comsol") setSyncStatus(err);
    }
    setTimeout(() => {
      setSyncStatus("");
      if (statusKey === "llm") setMemoryStatus("");
    }, 4000);
  }, []);

  const setPreferredBackend = useCallback(
    (value: LLMBackendId | null) => {
      setApiConfig((c: ApiConfig) => ({ ...c, preferred_backend: value }));
      saveApiConfig({ ...apiConfig, preferred_backend: value });
      dispatch({ type: "SET_BACKEND", backend: value });
    },
    [apiConfig, dispatch]
  );

  const saveConfig = useCallback(() => {
    saveAndSync(apiConfig, "llm");
  }, [apiConfig, saveAndSync]);

  const loadMemory = useCallback(async () => {
    if (!cid) {
      setMemoryStatus("无当前会话");
      return;
    }
    setMemoryStatus("加载中…");
    try {
      const res = await invoke<{ ok: boolean; message: string }>("bridge_send", {
        cmd: "context_get_summary",
        payload: { conversation_id: cid },
      });
      setMemoryText(res.ok ? res.message : "");
      setMemoryStatus(res.ok ? "已加载" : res.message);
    } catch (e) {
      setMemoryStatus("加载失败: " + String(e));
    }
    setTimeout(() => setMemoryStatus(""), 3000);
  }, [cid]);

  const saveMemory = useCallback(async () => {
    if (!cid) {
      setMemoryStatus("无当前会话");
      return;
    }
    setMemoryStatus("保存中…");
    try {
      const res = await invoke<{ ok: boolean; message: string }>("bridge_send", {
        cmd: "context_set_summary",
        payload: { conversation_id: cid, text: memoryText },
      });
      setMemoryStatus(res.ok ? "记忆已保存" : res.message);
    } catch (e) {
      setMemoryStatus("保存失败: " + String(e));
    }
    setTimeout(() => setMemoryStatus(""), 3000);
  }, [cid, memoryText]);

  const clearMemory = useCallback(async () => {
    if (!cid) return;
    if (!confirm("确定清除本会话的对话历史与记忆？")) return;
    setMemoryStatus("清除中…");
    try {
      const res = await invoke<{ ok: boolean; message: string }>("bridge_send", {
        cmd: "context_clear",
        payload: { conversation_id: cid },
      });
      setMemoryText("");
      setMemoryStatus(res.ok ? "已清除" : res.message);
    } catch (e) {
      setMemoryStatus("清除失败: " + String(e));
    }
    setTimeout(() => setMemoryStatus(""), 3000);
  }, [cid]);

  const testOllama = useCallback(async () => {
    const url = ollamaUrl.trim() || apiConfig.ollama_url;
    setOllamaTestResult(null);
    try {
      const res = await invoke<{ ok: boolean; message: string }>("bridge_send", {
        cmd: "ollama_ping",
        payload: { ollama_url: url },
      });
      setOllamaTestResult({ ok: res.ok, msg: res.message });
    } catch (e) {
      setOllamaTestResult({ ok: false, msg: String(e) });
    }
  }, [ollamaUrl, apiConfig.ollama_url]);

  const loadModelsList = useCallback(async () => {
    setModelsLoading(true);
    try {
      const res = await invoke<BridgeResponse>("bridge_send", {
        cmd: "models_list",
        payload: { limit: 50 },
      });
      setModelsList(res.ok && Array.isArray(res.models) ? res.models : []);
    } catch {
      setModelsList([]);
    } finally {
      setModelsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "models") loadModelsList();
  }, [activeTab, loadModelsList]);

  const openInFolder = useCallback((path: string) => {
    invoke("open_in_folder", { path }).catch(() => {
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(path);
        alert("已复制路径到剪贴板");
      }
    });
  }, []);

  /** 打开与模型同目录的 operations.md */
  const openPreviewMd = useCallback((modelPath: string) => {
    const dir = modelPath.replace(/[/\\][^/\\]*$/, "") || modelPath;
    const mdPath = dir + (dir.endsWith("/") || dir.endsWith("\\") ? "" : "/") + "operations.md";
    invoke("open_path", { path: mdPath }).catch(() => {
      alert("未找到操作记录文件 operations.md，请确认模型所在目录。");
    });
  }, []);

  const renderRow = (label: string, control: React.ReactNode, rowKey?: string) => (
    <div className={`settings-pane-row ${!label ? "settings-pane-row--full" : ""}`} key={rowKey ?? (label || "action")}>
      <span className="settings-pane-label">{label}</span>
      <span className="settings-pane-control">{control}</span>
    </div>
  );

  return (
    <div className="settings-dialog">
      <header className="settings-dialog-header">
        <h2 className="settings-dialog-title">设置</h2>
        <button type="button" className="settings-dialog-close" onClick={onClose} aria-label="关闭">
          ✕
        </button>
      </header>
      <div className="settings-dialog-body">
        <nav className="settings-sidebar" aria-label="设置分类">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`settings-sidebar-item ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="settings-sidebar-label">{tab.label}</span>
            </button>
          ))}
        </nav>
        <div className="settings-pane">
          {activeTab === "theme" && (
            <div className="settings-card">
              {renderRow(
                  "外观",
                  <div className="theme-toggle">
                    <button
                      type="button"
                      className={`theme-toggle-btn ${themeMode === "light" ? "active" : ""}`}
                      onClick={() => setThemeMode("light")}
                    >
                      浅色
                    </button>
                    <button
                      type="button"
                      className={`theme-toggle-btn ${themeMode === "dark" ? "active" : ""}`}
                      onClick={() => setThemeMode("dark")}
                    >
                      深色
                    </button>
                    <button
                      type="button"
                      className={`theme-toggle-btn ${themeMode === "system" ? "active" : ""}`}
                      onClick={() => setThemeMode("system")}
                    >
                      系统
                    </button>
                  </div>
                )}
                {renderRow(
                  "强调色",
                  <>
                    <div className="accent-chips">
                      {ACCENT_PRESETS.map((preset) => (
                        <button
                          key={preset.value}
                          type="button"
                          className={`accent-chip ${accentColor === preset.value ? "active" : ""}`}
                          style={{ backgroundColor: preset.value }}
                          onClick={() => setAccentColor(preset.value)}
                          title={preset.name}
                        >
                          {preset.name}
                        </button>
                      ))}
                    </div>
                    <input
                      type="color"
                      className="accent-color-input"
                      value={accentColor}
                      onChange={(e) => setAccentColor(e.target.value)}
                    />
                    <span className="accent-hex">{accentColor}</span>
                  </>
                )}
              </div>
          )}

          {activeTab === "llm" && (
            <div className="settings-card">
              <p className="settings-hint">选择默认模型（LLM 后端），并填写对应配置；保存后同步到 .env。</p>
              {renderRow(
                "默认模型 (LLM_BACKEND)",
                <div className="settings-backend-options">
                  {[
                    { id: "deepseek" as const, name: "DeepSeek" },
                    { id: "kimi" as const, name: "Kimi" },
                    { id: "openai-compatible" as const, name: "OpenAI 兼容" },
                    { id: "ollama" as const, name: "Ollama" },
                  ].map(({ id, name }) => (
                    <button
                      key={id}
                      type="button"
                      className={`theme-toggle-btn ${(apiConfig.preferred_backend ?? null) === id ? "active" : ""}`}
                      onClick={() => setPreferredBackend(id)}
                    >
                      {name}
                    </button>
                  ))}
                </div>
              )}
              {apiConfig.preferred_backend === "deepseek" && (
                <>
                  {renderRow("API Key (DEEPSEEK_API_KEY)", (
                    <input
                      type="password"
                      className="dialog-input settings-api-input"
                      placeholder="sk-…"
                      value={apiConfig.deepseek_api_key}
                      onChange={(e) =>
                        setApiConfig((c: ApiConfig) => ({ ...c, deepseek_api_key: e.target.value }))
                      }
                    />
                  ))}
                  {renderRow("模型 (DEEPSEEK_MODEL)", (
                    <input
                      type="text"
                      className="dialog-input settings-api-input"
                      placeholder="deepseek-reasoner"
                      value={apiConfig.deepseek_model}
                      onChange={(e) =>
                        setApiConfig((c: ApiConfig) => ({ ...c, deepseek_model: e.target.value }))
                      }
                    />
                  ))}
                </>
              )}
              {apiConfig.preferred_backend === "kimi" && (
                <>
                  {renderRow("API Key (KIMI_API_KEY)", (
                    <input
                      type="password"
                      className="dialog-input settings-api-input"
                      placeholder="…"
                      value={apiConfig.kimi_api_key}
                      onChange={(e) =>
                        setApiConfig((c: ApiConfig) => ({ ...c, kimi_api_key: e.target.value }))
                      }
                    />
                  ))}
                  {renderRow("模型 (KIMI_MODEL)", (
                    <input
                      type="text"
                      className="dialog-input settings-api-input"
                      placeholder="moonshot-v1-8k"
                      value={apiConfig.kimi_model}
                      onChange={(e) =>
                        setApiConfig((c: ApiConfig) => ({ ...c, kimi_model: e.target.value }))
                      }
                    />
                  ))}
                </>
              )}
              {apiConfig.preferred_backend === "openai-compatible" && (
                <>
                  {renderRow("Base URL (OPENAI_COMPATIBLE_BASE_URL)", (
                    <input
                      type="url"
                      className="dialog-input settings-api-input"
                      placeholder="https://api.example.com/v1"
                      value={apiConfig.openai_compatible_base_url}
                      onChange={(e) =>
                        setApiConfig((c: ApiConfig) => ({
                          ...c,
                          openai_compatible_base_url: e.target.value,
                        }))
                      }
                    />
                  ))}
                  {renderRow("API Key (OPENAI_COMPATIBLE_API_KEY)", (
                    <input
                      type="password"
                      className="dialog-input settings-api-input"
                      placeholder="…"
                      value={apiConfig.openai_compatible_api_key}
                      onChange={(e) =>
                        setApiConfig((c: ApiConfig) => ({
                          ...c,
                          openai_compatible_api_key: e.target.value,
                        }))
                      }
                    />
                  ))}
                  {renderRow("模型 (OPENAI_COMPATIBLE_MODEL)", (
                    <input
                      type="text"
                      className="dialog-input settings-api-input"
                      placeholder="gpt-3.5-turbo"
                      value={apiConfig.openai_compatible_model}
                      onChange={(e) =>
                        setApiConfig((c: ApiConfig) => ({
                          ...c,
                          openai_compatible_model: e.target.value,
                        }))
                      }
                    />
                  ))}
                </>
              )}
              {apiConfig.preferred_backend === "ollama" && (
                <>
                  {renderRow("Ollama 地址 (OLLAMA_URL)", (
                    <input
                      type="text"
                      className="dialog-input settings-api-input"
                      placeholder="http://localhost:11434"
                      value={ollamaUrl}
                      onChange={(e) => {
                        setOllamaUrl(e.target.value);
                        setApiConfig((c: ApiConfig) => ({ ...c, ollama_url: e.target.value }));
                      }}
                    />
                  ))}
                  {renderRow("Ollama 模型 (OLLAMA_MODEL)", (
                    <input
                      type="text"
                      className="dialog-input settings-api-input"
                      placeholder="llama3"
                      value={apiConfig.ollama_model}
                      onChange={(e) =>
                        setApiConfig((c: ApiConfig) => ({ ...c, ollama_model: e.target.value }))
                      }
                    />
                  ))}
                  {renderRow(
                    "",
                    <>
                      <button type="button" className="dialog-btn secondary" onClick={testOllama}>
                        测试连接
                      </button>
                      {ollamaTestResult && (
                        <span
                          className={`settings-status ${ollamaTestResult.ok ? "settings-status-ok" : "settings-status-err"}`}
                        >
                          {ollamaTestResult.msg}
                        </span>
                      )}
                    </>,
                    "ollama-test"
                  )}
                </>
              )}
              {renderRow(
                "",
                <>
                  <button type="button" className="dialog-btn primary" onClick={saveConfig}>
                    保存并同步到后端
                  </button>
                  {memoryStatus && (
                    <span className="settings-status">{memoryStatus}</span>
                  )}
                </>,
                "llm-save"
              )}
            </div>
          )}

          {activeTab === "comsol" && (
            <div className="settings-card">
              <p className="settings-hint">COMSOL JAR 路径为执行几何/物理/求解时使用；保存后将同步到 .env 并加载。</p>
              <div className="settings-field">
                <label>COMSOL JAR 路径 (COMSOL_JAR_PATH)</label>
                  <input
                    type="text"
                    className="dialog-input settings-api-input"
                    placeholder="D:\comsol\COMSOL63\Multiphysics\plugins"
                    value={apiConfig.comsol_jar_path}
                    onChange={(e) =>
                      setApiConfig((c: ApiConfig) => ({ ...c, comsol_jar_path: e.target.value }))
                    }
                  />
                </div>
                {renderRow(
                  "",
                  <>
                    <button type="button" className="dialog-btn primary" onClick={() => saveAndSync(apiConfig, "comsol")}>
                      保存并同步到后端
                    </button>
                    {syncStatus && (
                      <span className={syncStatus.startsWith("COMSOL") ? "settings-status settings-status-ok" : "settings-status settings-status-err"}>
                        {syncStatus}
                      </span>
                    )}
                  </>,
                  "comsol-save"
                )}
              </div>
          )}

          {activeTab === "memory" && (
            <div className="settings-card">
                <p className="settings-hint">当前会话的摘要记忆，将参与后续推理。可编辑后保存。</p>
                {renderRow(
                  "",
                  <div className="settings-memory-actions">
                    <button type="button" className="dialog-btn secondary" onClick={loadMemory}>
                      加载
                    </button>
                    <button type="button" className="dialog-btn primary" onClick={saveMemory}>
                      保存
                    </button>
                    <button type="button" className="dialog-btn secondary" onClick={clearMemory}>
                      清除本会话记忆
                    </button>
                  </div>,
                  "memory-actions"
                )}
                <div className="settings-field">
                  <label>会话记忆摘要</label>
                  <textarea
                    className="dialog-input settings-memory-textarea"
                    placeholder="加载后在此编辑本会话记忆…"
                    value={memoryText}
                    onChange={(e) => setMemoryText(e.target.value)}
                    rows={6}
                  />
                </div>
                {memoryStatus && !memoryStatus.includes("API") && (
                  <div className="settings-status">{memoryStatus}</div>
                )}
            </div>
          )}

          {activeTab === "models" && (
            <div className="settings-card">
              <p className="settings-hint">以下为各会话中生成过的 COMSOL 模型，可在此打开模型所在目录。</p>
              {renderRow(
                "",
                <button type="button" className="dialog-btn secondary" onClick={loadModelsList} disabled={modelsLoading}>
                  {modelsLoading ? "加载中…" : "刷新列表"}
                </button>,
                "models-refresh"
              )}
              <div className="settings-models-list">
                {modelsLoading && modelsList.length === 0 && <div className="settings-models-loading">加载中…</div>}
                {!modelsLoading && modelsList.length === 0 && <div className="settings-models-empty">暂无模型记录</div>}
                {modelsList.map((m) => (
                  <div key={m.path} className="settings-models-item">
                    <span className="settings-models-item-title" title={m.path}>
                      {m.title}
                      {m.is_latest && <span className="settings-models-item-latest">最新</span>}
                    </span>
                    <div className="settings-models-item-actions">
                      <button type="button" className="dialog-btn secondary" onClick={() => openInFolder(m.path)}>在文件管理器中打开</button>
                      <button type="button" className="dialog-btn secondary" onClick={() => openPreviewMd(m.path)}>预览</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
