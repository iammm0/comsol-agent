import { createMemo, createSignal, For, Show, type JSX } from "solid-js";
import {
  apiConfigToEnv,
  getPayloadFromConfig,
  loadApiConfig,
  saveApiConfig,
  type ApiConfig,
  type LlmBackendId
} from "../lib/api-config.js";
import { sendCommand, sendStreamCommand, listenBridgeEvents } from "../services/bridge.js";
import { useSessionStore } from "../stores/session-store.js";

function Backdrop(props: { title: string; onClose: () => void; children: JSX.Element }): JSX.Element {
  return (
    <div class="dialog-backdrop" onClick={props.onClose}>
      <div class="dialog-card" onClick={(event) => event.stopPropagation()}>
        <div class="dialog-head">
          <h3>{props.title}</h3>
          <button class="btn" type="button" onClick={props.onClose}>
            Close
          </button>
        </div>
        <div class="dialog-body">{props.children}</div>
      </div>
    </div>
  );
}

function HelpDialog(props: { onClose: () => void }): JSX.Element {
  return (
    <Backdrop title="Help" onClose={props.onClose}>
      <ul>
        <li>`/run` switch to build mode</li>
        <li>`/plan` switch to plan mode</li>
        <li>`/context` show context commands</li>
        <li>`/backend` choose backend</li>
        <li>`/exec` execute from plan path</li>
        <li>`/settings` open settings</li>
      </ul>
    </Backdrop>
  );
}

function BackendDialog(props: { onClose: () => void }): JSX.Element {
  const store = useSessionStore();
  const backends: LlmBackendId[] = ["ollama", "deepseek", "kimi", "openai-compatible"];
  const isZh = (): boolean => store.state.locale === "zh";
  return (
    <Backdrop title={isZh() ? "模型后端" : "Backend"} onClose={props.onClose}>
      <div class="stack">
        <For each={backends}>
          {(backend) => (
            <button
              class={`btn block ${store.state.backend === backend ? "selected" : ""}`}
              type="button"
              onClick={() => {
                store.setBackend(backend);
                const current = loadApiConfig();
                saveApiConfig({
                  ...current,
                  preferred_backend: backend
                });
                props.onClose();
              }}
            >
              {backend}
            </button>
          )}
        </For>
      </div>
    </Backdrop>
  );
}

function ContextDialog(props: { onClose: () => void }): JSX.Element {
  const store = useSessionStore();
  const [output, setOutput] = createSignal("");
  const conversationId = createMemo(() => store.state.currentConversationId ?? undefined);

  const runCommand = async (
    cmd: "context_show" | "context_history" | "context_stats" | "context_clear"
  ): Promise<void> => {
    const cid = conversationId();
    const response = await sendCommand(
      cmd,
      {
        ...(cid ? { conversation_id: cid } : {})
      },
      cid
    );
    setOutput(response.message);
  };

  return (
    <Backdrop title="Context" onClose={props.onClose}>
      <div class="stack">
        <button class="btn block" type="button" onClick={() => void runCommand("context_show")}>
          Show Summary
        </button>
        <button class="btn block" type="button" onClick={() => void runCommand("context_history")}>
          Show History
        </button>
        <button class="btn block" type="button" onClick={() => void runCommand("context_stats")}>
          Show Stats
        </button>
        <button class="btn block danger" type="button" onClick={() => void runCommand("context_clear")}>
          Clear Context
        </button>
        <pre class="output">{output()}</pre>
      </div>
    </Backdrop>
  );
}

function ExecDialog(props: { onClose: () => void }): JSX.Element {
  const store = useSessionStore();
  const [path, setPath] = createSignal("");
  const [result, setResult] = createSignal("");
  const conversationId = createMemo(() => store.state.currentConversationId ?? undefined);

  const execute = async (): Promise<void> => {
    const cid = conversationId();
    const response = await sendCommand(
      "exec",
      {
        path: path().trim(),
        ...(cid ? { conversation_id: cid } : {})
      },
      cid
    );
    setResult(response.message);
  };

  return (
    <Backdrop title="Execute Plan JSON" onClose={props.onClose}>
      <div class="stack">
        <input
          class="text-input"
          value={path()}
          placeholder="Path to plan.json"
          onInput={(event) => setPath(event.currentTarget.value)}
        />
        <button class="btn block" type="button" onClick={() => void execute()}>
          Execute
        </button>
        <pre class="output">{result()}</pre>
      </div>
    </Backdrop>
  );
}

function OutputDialog(props: { onClose: () => void }): JSX.Element {
  const store = useSessionStore();
  const [value, setValue] = createSignal(store.state.outputDefault ?? "");
  return (
    <Backdrop title="Output Default" onClose={props.onClose}>
      <div class="stack">
        <input
          class="text-input"
          value={value()}
          placeholder="output/model.mph"
          onInput={(event) => setValue(event.currentTarget.value)}
        />
        <button
          class="btn block"
          type="button"
          onClick={() => {
            store.setOutputDefault(value().trim() || null);
            props.onClose();
          }}
        >
          Save
        </button>
      </div>
    </Backdrop>
  );
}

function SettingsDialog(props: { onClose: () => void }): JSX.Element {
  const store = useSessionStore();
  const isZh = (): boolean => store.state.locale === "zh";
  const [config, setConfig] = createSignal<ApiConfig>(loadApiConfig());
  const [result, setResult] = createSignal("");
  const conversationId = createMemo(() => store.state.currentConversationId ?? undefined);
  const selectedBackend = createMemo<LlmBackendId>(() => {
    const preferred = config().preferred_backend;
    if (preferred) {
      return preferred;
    }
    if (
      store.state.backend === "deepseek" ||
      store.state.backend === "kimi" ||
      store.state.backend === "openai-compatible" ||
      store.state.backend === "ollama"
    ) {
      return store.state.backend;
    }
    return "ollama";
  });

  const updateConfig = (patch: Partial<ApiConfig>): void => {
    setConfig((prev) => ({ ...prev, ...patch }));
  };

  const saveConfig = async (): Promise<void> => {
    const nextConfig: ApiConfig = {
      ...config(),
      preferred_backend: selectedBackend()
    };
    saveApiConfig(nextConfig);
    store.setBackend(nextConfig.preferred_backend);
    const response = await sendCommand(
      "config_save",
      { config: apiConfigToEnv(nextConfig) },
      conversationId()
    );
    setResult(response.message);
  };

  const loadSummary = async (): Promise<void> => {
    const cid = conversationId();
    const response = await sendCommand(
      "context_get_summary",
      {
        ...(cid ? { conversation_id: cid } : {})
      },
      cid
    );
    setResult(response.message);
  };

  const testOllama = async (): Promise<void> => {
    const url = config().ollama_url.trim();
    if (!url) {
      setResult(isZh() ? "请先填写 Ollama 地址" : "Please input Ollama URL first");
      return;
    }
    const response = await sendCommand(
      "ollama_ping",
      {
        ollama_url: url
      },
      conversationId()
    );
    setResult(response.message);
  };

  return (
    <Backdrop title={isZh() ? "设置" : "Settings"} onClose={props.onClose}>
      <div class="stack">
        <div class="question">
          <h4>{isZh() ? "语言" : "Language"}</h4>
          <div class="stack">
            <button
              class={`btn block ${store.state.locale === "zh" ? "selected" : ""}`}
              type="button"
              onClick={() => store.setLocale("zh")}
            >
              中文
            </button>
            <button
              class={`btn block ${store.state.locale === "en" ? "selected" : ""}`}
              type="button"
              onClick={() => store.setLocale("en")}
            >
              English
            </button>
          </div>
        </div>

        <div class="question">
          <h4>{isZh() ? "LLM 服务商" : "LLM Provider"}</h4>
          <div class="stack">
            <For each={["ollama", "deepseek", "kimi", "openai-compatible"] as LlmBackendId[]}>
              {(backend) => (
                <button
                  class={`btn block ${selectedBackend() === backend ? "selected" : ""}`}
                  type="button"
                  onClick={() => {
                    updateConfig({ preferred_backend: backend });
                    store.setBackend(backend);
                  }}
                >
                  {backend}
                </button>
              )}
            </For>
          </div>
          <Show when={selectedBackend() === "deepseek"}>
            <input
              class="text-input"
              placeholder="DEEPSEEK_API_KEY"
              value={config().deepseek_api_key}
              onInput={(event) => updateConfig({ deepseek_api_key: event.currentTarget.value })}
            />
            <input
              class="text-input"
              placeholder="DEEPSEEK_MODEL"
              value={config().deepseek_model}
              onInput={(event) => updateConfig({ deepseek_model: event.currentTarget.value })}
            />
          </Show>
          <Show when={selectedBackend() === "kimi"}>
            <input
              class="text-input"
              placeholder="KIMI_API_KEY"
              value={config().kimi_api_key}
              onInput={(event) => updateConfig({ kimi_api_key: event.currentTarget.value })}
            />
            <input
              class="text-input"
              placeholder="KIMI_MODEL"
              value={config().kimi_model}
              onInput={(event) => updateConfig({ kimi_model: event.currentTarget.value })}
            />
          </Show>
          <Show when={selectedBackend() === "openai-compatible"}>
            <input
              class="text-input"
              placeholder="OPENAI_COMPATIBLE_BASE_URL"
              value={config().openai_compatible_base_url}
              onInput={(event) =>
                updateConfig({ openai_compatible_base_url: event.currentTarget.value })
              }
            />
            <input
              class="text-input"
              placeholder="OPENAI_COMPATIBLE_API_KEY"
              value={config().openai_compatible_api_key}
              onInput={(event) =>
                updateConfig({ openai_compatible_api_key: event.currentTarget.value })
              }
            />
            <input
              class="text-input"
              placeholder="OPENAI_COMPATIBLE_MODEL"
              value={config().openai_compatible_model}
              onInput={(event) =>
                updateConfig({ openai_compatible_model: event.currentTarget.value })
              }
            />
          </Show>
          <Show when={selectedBackend() === "ollama"}>
            <input
              class="text-input"
              placeholder="OLLAMA_URL"
              value={config().ollama_url}
              onInput={(event) => updateConfig({ ollama_url: event.currentTarget.value })}
            />
            <input
              class="text-input"
              placeholder="OLLAMA_MODEL"
              value={config().ollama_model}
              onInput={(event) => updateConfig({ ollama_model: event.currentTarget.value })}
            />
            <button class="btn block" type="button" onClick={() => void testOllama()}>
              {isZh() ? "测试 Ollama 连接" : "Test Ollama Connectivity"}
            </button>
          </Show>
        </div>

        <div class="question">
          <h4>{isZh() ? "COMSOL 连接" : "COMSOL Connection"}</h4>
          <label class="option">
            <input
              type="checkbox"
              checked={config().mph_agent_enable_comsol}
              onChange={(event) =>
                updateConfig({ mph_agent_enable_comsol: event.currentTarget.checked })
              }
            />
            {isZh() ? "启用 COMSOL 实桥接 (MPH_AGENT_ENABLE_COMSOL)" : "Enable COMSOL bridge"}
          </label>
          <input
            class="text-input"
            placeholder="COMSOL_HOME"
            value={config().comsol_home}
            onInput={(event) => updateConfig({ comsol_home: event.currentTarget.value })}
          />
          <input
            class="text-input"
            placeholder="COMSOL_JAR_DIR"
            value={config().comsol_jar_dir}
            onInput={(event) => updateConfig({ comsol_jar_dir: event.currentTarget.value })}
          />
          <input
            class="text-input"
            placeholder="JAVA_HOME"
            value={config().java_home}
            onInput={(event) => updateConfig({ java_home: event.currentTarget.value })}
          />
        </div>

        <button class="btn block" type="button" onClick={() => void saveConfig()}>
          {isZh() ? "保存并同步配置" : "Save and Sync Config"}
        </button>
        <button class="btn block" type="button" onClick={() => void loadSummary()}>
          {isZh() ? "加载会话记忆摘要" : "Load Memory Summary"}
        </button>
        <pre class="output">{result()}</pre>
      </div>
    </Backdrop>
  );
}

function OpsDialog(props: { onClose: () => void }): JSX.Element {
  return (
    <Backdrop title="COMSOL Operations" onClose={props.onClose}>
      <ul>
        <li>geometry.create</li>
        <li>physics.add</li>
        <li>mesh.generate</li>
        <li>study.setup</li>
        <li>solve.run</li>
        <li>postprocess.export</li>
      </ul>
    </Backdrop>
  );
}

function ApiDialog(props: { onClose: () => void }): JSX.Element {
  const store = useSessionStore();
  const [query, setQuery] = createSignal("");
  const [items, setItems] = createSignal<Array<Record<string, unknown>>>([]);
  const [message, setMessage] = createSignal("");
  const conversationId = createMemo(() => store.state.currentConversationId ?? undefined);

  const search = async (): Promise<void> => {
    const keyword = query().trim();
    const response = await sendCommand(
      "list_apis",
      {
        ...(keyword ? { query: keyword } : {}),
        limit: 100,
        offset: 0
      },
      conversationId()
    );
    setMessage(response.message);
    const payloadItems = response.data?.apis;
    if (Array.isArray(payloadItems)) {
      setItems(payloadItems as Array<Record<string, unknown>>);
    } else {
      setItems([]);
    }
  };

  return (
    <Backdrop title="API Browser" onClose={props.onClose}>
      <div class="stack">
        <input
          class="text-input"
          value={query()}
          placeholder="search wrapper or owner"
          onInput={(event) => setQuery(event.currentTarget.value)}
        />
        <button class="btn block" type="button" onClick={() => void search()}>
          Search
        </button>
        <div class="api-list">
          <For each={items()}>
            {(item) => (
              <div class="api-item">
                <strong>{String(item.wrapper_name ?? "")}</strong>
                <span>{String(item.owner ?? "")}</span>
                <span>{String(item.method_name ?? "")}</span>
              </div>
            )}
          </For>
        </div>
        <pre class="output">{message()}</pre>
      </div>
    </Backdrop>
  );
}

function PlanQuestionsDialog(props: { onClose: () => void }): JSX.Element {
  const store = useSessionStore();
  const [result, setResult] = createSignal("");
  const [selections, setSelections] = createSignal<Record<string, string>>({});
  const conversationId = createMemo(() => store.state.currentConversationId ?? undefined);
  const isZh = (): boolean => store.state.locale === "zh";

  const submit = async (): Promise<void> => {
    const answers = (store.state.pendingPlanQuestions ?? []).map((question) => ({
      question_id: question.id,
      selected_option_ids: selections()[question.id] ? [selections()[question.id]] : []
    }));

    const baseInput = store.state.lastPlanInput ?? "";
    if (!baseInput) {
      setResult(isZh() ? "缺少上一轮输入" : "Missing last input");
      return;
    }

    store.setBusyConversation(conversationId() ?? null);
    store.addMessage("assistant", "", { events: [] });
    const cid = conversationId() ?? "default";
    const unlisten = await listenBridgeEvents((event) => {
      store.appendEvent(cid, event);
    });

    const backend = store.state.backend;
    const output = store.state.outputDefault;
    const apiPayload = getPayloadFromConfig(backend, loadApiConfig());

    const response = await sendStreamCommand(
      "run",
      {
        input: baseInput,
        clarifying_answers: answers,
        use_react: true,
        no_context: false,
        ...(backend ? { backend } : {}),
        ...(output ? { output } : {}),
        ...apiPayload
      },
      conversationId()
    );
    store.finalizeLast(cid, response.message, response.ok);
    store.setBusyConversation(null);
    store.setPendingPlanQuestions(null);
    setResult(response.message);
    unlisten();
  };

  return (
    <Backdrop title={isZh() ? "计划澄清问题" : "Plan Clarification"} onClose={props.onClose}>
      <div class="stack">
        <For each={store.state.pendingPlanQuestions ?? []}>
          {(question) => (
            <div class="question">
              <h4>{question.text}</h4>
              <For each={question.options}>
                {(option) => (
                  <label class="option">
                    <input
                      type={question.type === "multi" ? "checkbox" : "radio"}
                      name={question.id}
                      checked={selections()[question.id] === option.id}
                      onChange={() =>
                        setSelections((prev) => ({
                          ...prev,
                          [question.id]: option.id
                        }))
                      }
                    />
                    {option.label}
                  </label>
                )}
              </For>
            </div>
          )}
        </For>
        <button class="btn block" type="button" onClick={() => void submit()}>
          {isZh() ? "提交答案并继续" : "Submit Answers"}
        </button>
        <pre class="output">{result()}</pre>
      </div>
    </Backdrop>
  );
}

export function DialogHost(): JSX.Element {
  const store = useSessionStore();
  const close = (): void => {
    store.setDialog(null);
  };

  return (
    <Show when={store.state.activeDialog !== null}>
      <SwitchDialog dialog={store.state.activeDialog} onClose={close} />
    </Show>
  );
}

function SwitchDialog(props: { dialog: string | null; onClose: () => void }): JSX.Element {
  switch (props.dialog) {
    case "help":
      return <HelpDialog onClose={props.onClose} />;
    case "backend":
      return <BackendDialog onClose={props.onClose} />;
    case "context":
      return <ContextDialog onClose={props.onClose} />;
    case "exec":
      return <ExecDialog onClose={props.onClose} />;
    case "output":
      return <OutputDialog onClose={props.onClose} />;
    case "settings":
      return <SettingsDialog onClose={props.onClose} />;
    case "ops":
      return <OpsDialog onClose={props.onClose} />;
    case "api":
      return <ApiDialog onClose={props.onClose} />;
    case "planQuestions":
      return <PlanQuestionsDialog onClose={props.onClose} />;
    default:
      return <></>;
  }
}
