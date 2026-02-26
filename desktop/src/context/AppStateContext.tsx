import {
  createContext,
  useContext,
  useReducer,
  useCallback,
  useEffect,
  useMemo,
  type ReactNode,
  type Dispatch,
} from "react";
import type {
  ChatMessage,
  MessageRole,
  RunEvent,
  DialogType,
  Conversation,
} from "../lib/types";
import {
  loadConversations,
  saveConversations,
  loadMessagesByConversation,
  saveMessagesByConversation,
  loadCurrentConversationId,
  saveCurrentConversationId,
} from "../lib/conversationStorage";
import { loadApiConfig } from "../lib/apiConfig";

function genId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

let messageCounter = 0;
function nextMsgId(): string {
  return `msg_${++messageCounter}_${Date.now()}`;
}

interface AppState {
  conversations: Conversation[];
  currentConversationId: string | null;
  /** conversationId -> messages */
  messagesByConversation: Record<string, ChatMessage[]>;
  mode: "run" | "plan";
  backend: string | null;
  outputDefault: string | null;
  execCodeOnly: boolean;
  busy: boolean;
  activeDialog: DialogType;
}

type AppAction =
  | { type: "NEW_CONVERSATION" }
  | { type: "SWITCH_CONVERSATION"; id: string }
  | { type: "SET_CONVERSATION_TITLE"; id: string; title: string }
  | { type: "DELETE_CONVERSATION"; id: string }
  | {
      type: "ADD_MESSAGE";
      conversationId: string;
      role: MessageRole;
      text: string;
      success?: boolean;
      events?: RunEvent[];
    }
  | { type: "APPEND_EVENT"; conversationId: string; event: RunEvent }
  | {
      type: "FINALIZE_LAST";
      conversationId: string;
      text: string;
      success: boolean;
    }
  | { type: "SET_MODE"; mode: "run" | "plan" }
  | { type: "SET_BACKEND"; backend: string | null }
  | { type: "SET_OUTPUT"; output: string | null }
  | { type: "SET_EXEC_CODE_ONLY"; value: boolean }
  | { type: "SET_BUSY"; busy: boolean }
  | { type: "SET_DIALOG"; dialog: DialogType }
  | { type: "HYDRATE"; state: Partial<AppState> };

function getInitialState(): AppState {
  const conversations = loadConversations();
  const messagesByConversation = loadMessagesByConversation() as Record<
    string,
    ChatMessage[]
  >;
  const currentId = loadCurrentConversationId();
  const apiCfg = loadApiConfig();
  const preferred = apiCfg.preferred_backend;
  const validBackends = ["deepseek", "kimi", "ollama", "openai-compatible"] as const;
  const backend =
    preferred && validBackends.includes(preferred as (typeof validBackends)[number])
      ? preferred
      : null;

  if (conversations.length === 0) {
    const first: Conversation = {
      id: genId(),
      title: "新会话",
      createdAt: Date.now(),
    };
    return {
      conversations: [first],
      currentConversationId: first.id,
      messagesByConversation: { [first.id]: [] },
      mode: "run",
      backend,
      outputDefault: null,
      execCodeOnly: false,
      busy: false,
      activeDialog: null,
    };
  }

  const id = currentId && conversations.some((c) => c.id === currentId)
    ? currentId
    : conversations[0].id;
  return {
    conversations,
    currentConversationId: id,
    messagesByConversation,
    mode: "run",
    backend,
    outputDefault: null,
    execCodeOnly: false,
    busy: false,
    activeDialog: null,
  };
}

const initialState = getInitialState();

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "NEW_CONVERSATION": {
      const conv: Conversation = {
        id: genId(),
        title: "新会话",
        createdAt: Date.now(),
      };
      return {
        ...state,
        conversations: [conv, ...state.conversations],
        currentConversationId: conv.id,
        messagesByConversation: {
          ...state.messagesByConversation,
          [conv.id]: [],
        },
      };
    }
    case "SWITCH_CONVERSATION":
      return {
        ...state,
        currentConversationId: action.id,
      };
    case "SET_CONVERSATION_TITLE": {
      const list = state.conversations.map((c) =>
        c.id === action.id ? { ...c, title: action.title } : c
      );
      return { ...state, conversations: list };
    }
    case "DELETE_CONVERSATION": {
      const list = state.conversations.filter((c) => c.id !== action.id);
      const nextMessages = { ...state.messagesByConversation };
      delete nextMessages[action.id];
      let nextId = state.currentConversationId;
      let nextList = list;
      if (state.currentConversationId === action.id) {
        nextId = list.length > 0 ? list[0].id : null;
      }
      if (list.length === 0) {
        const newConv: Conversation = {
          id: genId(),
          title: "新会话",
          createdAt: Date.now(),
        };
        nextList = [newConv];
        nextId = newConv.id;
      }
      return {
        ...state,
        conversations: nextList,
        messagesByConversation: nextMessages,
        currentConversationId: nextId,
      };
    }
    case "ADD_MESSAGE": {
      const { conversationId, role, text, success, events } = action;
      const msg: ChatMessage = {
        id: nextMsgId(),
        role,
        text,
        time: Date.now(),
        success,
        events,
      };
      const prev = state.messagesByConversation[conversationId] ?? [];
      return {
        ...state,
        messagesByConversation: {
          ...state.messagesByConversation,
          [conversationId]: [...prev, msg],
        },
      };
    }
    case "APPEND_EVENT": {
      const { conversationId, event } = action;
      const prev = state.messagesByConversation[conversationId] ?? [];
      const last = prev[prev.length - 1];
      if (!last || last.role !== "assistant") return state;
      const updated = [
        ...prev.slice(0, -1),
        { ...last, events: [...(last.events ?? []), event] },
      ];
      return {
        ...state,
        messagesByConversation: {
          ...state.messagesByConversation,
          [conversationId]: updated,
        },
      };
    }
    case "FINALIZE_LAST": {
      const { conversationId, text, success } = action;
      const prev = state.messagesByConversation[conversationId] ?? [];
      const last = prev[prev.length - 1];
      if (!last || last.role !== "assistant") return state;
      const updated = [
        ...prev.slice(0, -1),
        { ...last, text, success },
      ];
      return {
        ...state,
        messagesByConversation: {
          ...state.messagesByConversation,
          [conversationId]: updated,
        },
      };
    }
    case "SET_MODE":
      return { ...state, mode: action.mode };
    case "SET_BACKEND":
      return { ...state, backend: action.backend };
    case "SET_OUTPUT":
      return { ...state, outputDefault: action.output };
    case "SET_EXEC_CODE_ONLY":
      return { ...state, execCodeOnly: action.value };
    case "SET_BUSY":
      return { ...state, busy: action.busy };
    case "SET_DIALOG":
      return { ...state, activeDialog: action.dialog };
    case "HYDRATE":
      return { ...state, ...action.state };
    default:
      return state;
  }
}

interface AppStateContextValue {
  state: AppState;
  dispatch: Dispatch<AppAction>;
  /** 当前会话的消息列表 */
  messages: ChatMessage[];
  /** 当前会话标题 */
  sessionTitle: string;
  addMessage: (
    role: MessageRole,
    text: string,
    opts?: { success?: boolean; events?: RunEvent[] }
  ) => void;
}

const AppStateContext = createContext<AppStateContextValue | undefined>(
  undefined
);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  const messages = useMemo(
    () =>
      state.currentConversationId
        ? state.messagesByConversation[state.currentConversationId] ?? []
        : [],
    [state.currentConversationId, state.messagesByConversation]
  );

  const sessionTitle = useMemo(
    () =>
      state.currentConversationId
        ? state.conversations.find((c) => c.id === state.currentConversationId)
            ?.title ?? "新会话"
        : "新会话",
    [state.currentConversationId, state.conversations]
  );

  const addMessage = useCallback(
    (
      role: MessageRole,
      text: string,
      opts?: { success?: boolean; events?: RunEvent[] }
    ) => {
      const id = state.currentConversationId;
      if (!id) return;
      dispatch({
        type: "ADD_MESSAGE",
        conversationId: id,
        role,
        text,
        success: opts?.success,
        events: opts?.events,
      });
    },
    [state.currentConversationId, dispatch]
  );

  useEffect(() => {
    saveConversations(state.conversations);
  }, [state.conversations]);

  useEffect(() => {
    saveMessagesByConversation(
      state.messagesByConversation as unknown as Record<string, unknown[]>
    );
  }, [state.messagesByConversation]);

  useEffect(() => {
    if (state.currentConversationId) {
      saveCurrentConversationId(state.currentConversationId);
    }
  }, [state.currentConversationId]);

  const value: AppStateContextValue = {
    state,
    dispatch,
    messages,
    sessionTitle,
    addMessage,
  };

  return (
    <AppStateContext.Provider value={value}>
      {children}
    </AppStateContext.Provider>
  );
}

export function useAppState() {
  const ctx = useContext(AppStateContext);
  if (!ctx)
    throw new Error("useAppState must be used within AppStateProvider");
  return ctx;
}
