const STORAGE_KEY = "mph-agent-ts-api-config";

export type LlmBackendId = "deepseek" | "kimi" | "ollama" | "openai-compatible";

export interface ApiConfig {
  preferred_backend: LlmBackendId | null;
  deepseek_api_key: string;
  deepseek_model: string;
  kimi_api_key: string;
  kimi_model: string;
  openai_compatible_base_url: string;
  openai_compatible_api_key: string;
  openai_compatible_model: string;
  ollama_url: string;
  ollama_model: string;
  comsol_home: string;
  comsol_jar_dir: string;
  java_home: string;
  mph_agent_enable_comsol: boolean;
}

const defaultConfig: ApiConfig = {
  preferred_backend: null,
  deepseek_api_key: "",
  deepseek_model: "deepseek-reasoner",
  kimi_api_key: "",
  kimi_model: "moonshot-v1-8k",
  openai_compatible_base_url: "",
  openai_compatible_api_key: "",
  openai_compatible_model: "gpt-4o-mini",
  ollama_url: "http://localhost:11434",
  ollama_model: "llama3",
  comsol_home: "",
  comsol_jar_dir: "",
  java_home: "",
  mph_agent_enable_comsol: false
};

export function loadApiConfig(): ApiConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { ...defaultConfig };
    }
    const parsed = JSON.parse(raw) as Partial<ApiConfig>;
    return {
      ...defaultConfig,
      ...parsed,
      mph_agent_enable_comsol: Boolean(parsed.mph_agent_enable_comsol)
    };
  } catch {
    return { ...defaultConfig };
  }
}

export function saveApiConfig(config: ApiConfig): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  } catch {
    // ignore localStorage write failures
  }
}

export function apiConfigToEnv(config: ApiConfig): Record<string, string> {
  const env: Record<string, string> = {};
  if (config.preferred_backend) {
    env.LLM_BACKEND = config.preferred_backend;
  }
  if (config.deepseek_api_key) {
    env.DEEPSEEK_API_KEY = config.deepseek_api_key;
  }
  if (config.deepseek_model) {
    env.DEEPSEEK_MODEL = config.deepseek_model;
  }
  if (config.kimi_api_key) {
    env.KIMI_API_KEY = config.kimi_api_key;
  }
  if (config.kimi_model) {
    env.KIMI_MODEL = config.kimi_model;
  }
  if (config.openai_compatible_base_url) {
    env.OPENAI_COMPATIBLE_BASE_URL = config.openai_compatible_base_url;
  }
  if (config.openai_compatible_api_key) {
    env.OPENAI_COMPATIBLE_API_KEY = config.openai_compatible_api_key;
  }
  if (config.openai_compatible_model) {
    env.OPENAI_COMPATIBLE_MODEL = config.openai_compatible_model;
  }
  if (config.ollama_url) {
    env.OLLAMA_URL = config.ollama_url;
  }
  if (config.ollama_model) {
    env.OLLAMA_MODEL = config.ollama_model;
  }
  if (config.comsol_home) {
    env.COMSOL_HOME = config.comsol_home;
  }
  if (config.comsol_jar_dir) {
    env.COMSOL_JAR_DIR = config.comsol_jar_dir;
    // legacy compatibility
    env.COMSOL_JAR_PATH = config.comsol_jar_dir;
  }
  if (config.java_home) {
    env.JAVA_HOME = config.java_home;
  }
  env.MPH_AGENT_ENABLE_COMSOL = config.mph_agent_enable_comsol ? "1" : "0";
  return env;
}

export function getPayloadFromConfig(
  backend: string | null,
  config: ApiConfig
): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  switch (backend) {
    case "deepseek":
      if (config.deepseek_api_key) {
        payload.api_key = config.deepseek_api_key;
      }
      if (config.deepseek_model) {
        payload.model = config.deepseek_model;
      }
      if (config.openai_compatible_base_url) {
        payload.base_url = config.openai_compatible_base_url;
      }
      break;
    case "kimi":
      if (config.kimi_api_key) {
        payload.api_key = config.kimi_api_key;
      }
      if (config.kimi_model) {
        payload.model = config.kimi_model;
      }
      if (config.openai_compatible_base_url) {
        payload.base_url = config.openai_compatible_base_url;
      }
      break;
    case "openai-compatible":
      if (config.openai_compatible_base_url) {
        payload.base_url = config.openai_compatible_base_url;
      }
      if (config.openai_compatible_api_key) {
        payload.api_key = config.openai_compatible_api_key;
      }
      if (config.openai_compatible_model) {
        payload.model = config.openai_compatible_model;
      }
      break;
    case "ollama":
      if (config.ollama_url) {
        payload.ollama_url = config.ollama_url;
      }
      if (config.ollama_model) {
        payload.model = config.ollama_model;
      }
      break;
    default:
      break;
  }
  return payload;
}
