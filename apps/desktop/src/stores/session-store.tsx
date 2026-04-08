import {
  createContext,
  createEffect,
  createMemo,
  createSignal,
  type Accessor,
  type JSX,
  useContext
} from "solid-js";
import { createStore } from "solid-js/store";
import type { BridgeEvent } from "@mph-agent/contracts";
import { loadApiConfig } from "../lib/api-config.js";
import type {
  AppMode,
  ChatMessage,
  ClarifyingQuestion,
  Conversation,
  DialogType,
  LocaleMode,
  MessageRole
} from "../types/app.js";

interface State {
  conversations: Conversation[];
  currentConversationId: string | null;
  messagesByConversation: Record<string, ChatMessage[]>;
  mode: AppMode;
  locale: LocaleMode;
  backend: string | null;
  outputDefault: string | null;
  busyConversationId: string | null;
  activeDialog: DialogType;
  pendingPlanQuestions: ClarifyingQuestion[] | null;
  lastPlanInput: string | null;
  editingDraft: string | null;
}

interface StoreContext {
  state: State;
  messages: Accessor<ChatMessage[]>;
  sessionTitle: Accessor<string>;
  addMessage: (
    role: MessageRole,
    text: string,
    opts?: { success?: boolean; events?: BridgeEvent[] }
  ) => void;
  setMode: (mode: AppMode) => void;
  setDialog: (dialog: DialogType) => void;
  setBusyConversation: (conversationId: string | null) => void;
  setLocale: (locale: LocaleMode) => void;
  setBackend: (backend: string | null) => void;
  setOutputDefault: (output: string | null) => void;
  setPendingPlanQuestions: (questions: ClarifyingQuestion[] | null) => void;
  setLastPlanInput: (input: string | null) => void;
  appendEvent: (conversationId: string, event: BridgeEvent) => void;
  finalizeLast: (conversationId: string, text: string, success: boolean) => void;
  newConversation: () => void;
  switchConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;
  deleteConversation: (id: string) => void;
}

const CONVERSATIONS_KEY = "mph-agent-ts-conversations";
const MESSAGES_KEY = "mph-agent-ts-messages";
const CURRENT_ID_KEY = "mph-agent-ts-current-id";
const PREFERENCES_KEY = "mph-agent-ts-preferences";

function genId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function loadConversations(): Conversation[] {
  try {
    const value = localStorage.getItem(CONVERSATIONS_KEY);
    if (!value) {
      return [];
    }
    const parsed = JSON.parse(value) as Conversation[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function loadMessagesByConversation(): Record<string, ChatMessage[]> {
  try {
    const value = localStorage.getItem(MESSAGES_KEY);
    if (!value) {
      return {};
    }
    const parsed = JSON.parse(value) as Record<string, ChatMessage[]>;
    return parsed ?? {};
  } catch {
    return {};
  }
}

function loadPreference(): {
  locale: LocaleMode;
  backend: string | null;
  outputDefault: string | null;
} {
  try {
    const value = localStorage.getItem(PREFERENCES_KEY);
    if (!value) {
      return { locale: "zh", backend: null, outputDefault: null };
    }
    const parsed = JSON.parse(value) as {
      locale?: LocaleMode;
      backend?: string | null;
      outputDefault?: string | null;
    };
    return {
      locale: parsed.locale === "en" ? "en" : "zh",
      backend: parsed.backend ?? null,
      outputDefault: parsed.outputDefault ?? null
    };
  } catch {
    return { locale: "zh", backend: null, outputDefault: null };
  }
}

function createInitialState(): State {
  const conversations = loadConversations();
  const messagesByConversation = loadMessagesByConversation();
  const preference = loadPreference();
  const apiConfig = loadApiConfig();
  const currentConversationId = localStorage.getItem(CURRENT_ID_KEY);

  if (conversations.length === 0) {
    const defaultTitle = preference.locale === "zh" ? "新会话" : "New Conversation";
    const first: Conversation = {
      id: genId("conv"),
      title: defaultTitle,
      createdAt: Date.now()
    };
    return {
      conversations: [first],
      currentConversationId: first.id,
      messagesByConversation: { [first.id]: [] },
      mode: "run",
      locale: preference.locale,
      backend: apiConfig.preferred_backend ?? preference.backend,
      outputDefault: preference.outputDefault,
      busyConversationId: null,
      activeDialog: null,
      pendingPlanQuestions: null,
      lastPlanInput: null,
      editingDraft: null
    };
  }

  const nextCurrent =
    currentConversationId && conversations.some((item) => item.id === currentConversationId)
      ? currentConversationId
      : conversations[0]?.id ?? null;

  return {
    conversations,
    currentConversationId: nextCurrent,
    messagesByConversation,
    mode: "run",
    locale: preference.locale,
    backend: apiConfig.preferred_backend ?? preference.backend,
    outputDefault: preference.outputDefault,
    busyConversationId: null,
    activeDialog: null,
    pendingPlanQuestions: null,
    lastPlanInput: null,
    editingDraft: null
  };
}

const SessionStoreContext = createContext<StoreContext>();

export function SessionStoreProvider(props: { children: JSX.Element }): JSX.Element {
  const [state, setState] = createStore<State>(createInitialState());
  const [messageCounter, setMessageCounter] = createSignal(0);

  const messages = createMemo(() => {
    if (!state.currentConversationId) {
      return [];
    }
    return state.messagesByConversation[state.currentConversationId] ?? [];
  });

  const sessionTitle = createMemo(() => {
    if (!state.currentConversationId) {
      return state.locale === "zh" ? "新会话" : "New Conversation";
    }
    const found = state.conversations.find((item) => item.id === state.currentConversationId);
    return found?.title ?? (state.locale === "zh" ? "新会话" : "New Conversation");
  });

  const addMessage: StoreContext["addMessage"] = (role, text, opts) => {
    if (!state.currentConversationId) {
      return;
    }

    setMessageCounter((current) => current + 1);

    const message: ChatMessage = {
      id: `msg_${messageCounter() + 1}_${Date.now()}`,
      role,
      text,
      time: Date.now(),
      ...(typeof opts?.success === "boolean" ? { success: opts.success } : {}),
      ...(opts?.events ? { events: opts.events } : {})
    };

    const previous = state.messagesByConversation[state.currentConversationId] ?? [];
    setState("messagesByConversation", state.currentConversationId, [...previous, message]);
  };

  const appendEvent: StoreContext["appendEvent"] = (conversationId, event) => {
    const previous = state.messagesByConversation[conversationId] ?? [];
    const last = previous[previous.length - 1];
    if (!last || last.role !== "assistant") {
      return;
    }
    const updated: ChatMessage[] = [
      ...previous.slice(0, -1),
      {
        ...last,
        events: [...(last.events ?? []), event]
      }
    ];
    setState("messagesByConversation", conversationId, updated);
  };

  const finalizeLast: StoreContext["finalizeLast"] = (conversationId, text, success) => {
    const previous = state.messagesByConversation[conversationId] ?? [];
    const last = previous[previous.length - 1];
    if (!last || last.role !== "assistant") {
      return;
    }

    let modelPath: string | null | undefined = last.modelPath;
    for (let index = (last.events?.length ?? 0) - 1; index >= 0; index -= 1) {
      const event = last.events?.[index];
      const maybePath = event?.data.model_path;
      if (typeof maybePath === "string" && maybePath.length > 0) {
        modelPath = maybePath;
        break;
      }
    }

    const resolvedModelPath = modelPath ?? last.modelPath;

    const updatedLast: ChatMessage = {
      ...last,
      text,
      success,
      ...(resolvedModelPath !== undefined ? { modelPath: resolvedModelPath } : {})
    };

    const updated: ChatMessage[] = [...previous.slice(0, -1), updatedLast];
    setState("messagesByConversation", conversationId, updated);
  };

  const newConversation = (): void => {
    const conversation: Conversation = {
      id: genId("conv"),
      title: state.locale === "zh" ? "新会话" : "New Conversation",
      createdAt: Date.now()
    };
    setState("conversations", [conversation, ...state.conversations]);
    setState("currentConversationId", conversation.id);
    setState("messagesByConversation", conversation.id, []);
  };

  const switchConversation = (id: string): void => {
    setState("currentConversationId", id);
  };

  const renameConversation = (id: string, title: string): void => {
    setState(
      "conversations",
      state.conversations.map((item) => (item.id === id ? { ...item, title } : item))
    );
  };

  const deleteConversation = (id: string): void => {
    const filtered = state.conversations.filter((item) => item.id !== id);
    const nextMessages = { ...state.messagesByConversation };
    delete nextMessages[id];
    if (filtered.length === 0) {
      const first: Conversation = {
        id: genId("conv"),
        title: state.locale === "zh" ? "新会话" : "New Conversation",
        createdAt: Date.now()
      };
      setState("conversations", [first]);
      setState("currentConversationId", first.id);
      setState("messagesByConversation", { [first.id]: [] });
      return;
    }
    setState("conversations", filtered);
    setState("messagesByConversation", nextMessages);
    if (state.currentConversationId === id) {
      setState("currentConversationId", filtered[0]?.id ?? null);
    }
  };

  createEffect(() => {
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(state.conversations));
  });

  createEffect(() => {
    localStorage.setItem(MESSAGES_KEY, JSON.stringify(state.messagesByConversation));
  });

  createEffect(() => {
    if (state.currentConversationId) {
      localStorage.setItem(CURRENT_ID_KEY, state.currentConversationId);
    }
  });

  createEffect(() => {
    localStorage.setItem(
      PREFERENCES_KEY,
      JSON.stringify({
        locale: state.locale,
        backend: state.backend,
        outputDefault: state.outputDefault
      })
    );
  });

  const context: StoreContext = {
    state,
    messages,
    sessionTitle,
    addMessage,
    setMode: (mode) => setState("mode", mode),
    setDialog: (dialog) => setState("activeDialog", dialog),
    setBusyConversation: (conversationId) => setState("busyConversationId", conversationId),
    setLocale: (locale) => setState("locale", locale),
    setBackend: (backend) => setState("backend", backend),
    setOutputDefault: (output) => setState("outputDefault", output),
    setPendingPlanQuestions: (questions) => setState("pendingPlanQuestions", questions),
    setLastPlanInput: (input) => setState("lastPlanInput", input),
    appendEvent,
    finalizeLast,
    newConversation,
    switchConversation,
    renameConversation,
    deleteConversation
  };

  return (
    <SessionStoreContext.Provider value={context}>{props.children}</SessionStoreContext.Provider>
  );
}

export function useSessionStore(): StoreContext {
  const context = useContext(SessionStoreContext);
  if (!context) {
    throw new Error("useSessionStore must be used inside SessionStoreProvider");
  }
  return context;
}
