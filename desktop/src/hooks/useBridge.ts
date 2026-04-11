import { useCallback, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useAppState } from "../context/AppStateContext";
import { loadApiConfig, getPayloadFromConfig } from "../lib/apiConfig";
import type {
  RunEvent,
  BridgeResponse,
  ClarifyingQuestion,
} from "../lib/types";
import { normalizeClarifyingQuestions } from "../lib/clarifying";

function extractClarifyingQuestionsFromResponse(
  res: BridgeResponse
): ClarifyingQuestion[] {
  const topLevel = normalizeClarifyingQuestions(res.clarifying_questions);
  if (topLevel.length > 0) return topLevel;

  const planQuestions = normalizeClarifyingQuestions(
    (res.plan as Record<string, unknown> | null | undefined)?.clarifying_questions
  );
  return planQuestions;
}

export function useBridge() {
  const { state, dispatch, addMessage, messages } = useAppState();
  const cid = state.currentConversationId;
  const abortedRef = useRef(false);

  const sendCommand = useCallback(
    async (cmd: string, payload: Record<string, unknown> = {}) => {
      if (!cid) return;
      dispatch({ type: "SET_BUSY_CONVERSATION", conversationId: cid });
      try {
        const res = await invoke<BridgeResponse>("bridge_send", {
          cmd,
          payload: { ...payload, conversation_id: cid },
        });

        if (cmd === "plan") {
          const questions: ClarifyingQuestion[] =
            extractClarifyingQuestionsFromResponse(res);
          const unresolvedCount = Array.isArray(
            (res.plan as Record<string, unknown> | null | undefined)
              ?.unresolved_clarifications
          )
            ? (
                (res.plan as Record<string, unknown>).unresolved_clarifications as
                  | unknown[]
                  | null
              )?.length ?? 0
            : 0;
          const hasUnresolvedInPlan = unresolvedCount > 0;
          const needsClarification =
            Boolean(res.plan_needs_clarification) ||
            hasUnresolvedInPlan ||
            (questions.length > 0 && !Boolean(res.plan_confirmed));
          if (needsClarification && questions.length > 0) {
            dispatch({ type: "SET_PLAN_QUESTIONS", questions });
            dispatch({ type: "SET_DIALOG", dialog: "planQuestions" });
          } else {
            dispatch({ type: "CLEAR_PLAN_QUESTIONS" });
          }
        }

        if (cmd === "discuss") {
          const card = res.discussion_card;
          const finalized = Boolean(
            card &&
              typeof card === "object" &&
              (card as { finalized?: unknown }).finalized === true
          );
          dispatch({ type: "SET_DISCUSSION_READY_FOR_PLAN", value: finalized });
        }

        addMessage("assistant", res.message, { success: res.ok });
        return res;
      } catch (e) {
        addMessage("assistant", "请求失败: " + String(e), { success: false });
        return null;
      } finally {
        dispatch({ type: "SET_BUSY_CONVERSATION", conversationId: null });
      }
    },
    [cid, dispatch, addMessage]
  );

  const sendStreamCommand = useCallback(
    async (cmd: string, payload: Record<string, unknown> = {}) => {
      if (!cid) return;
      abortedRef.current = false;
      dispatch({ type: "SET_BUSY_CONVERSATION", conversationId: cid });
      dispatch({
        type: "ADD_MESSAGE",
        conversationId: cid,
        role: "assistant",
        text: "",
        events: [],
      });

      const unlisten = await listen<RunEvent>("bridge-event", (event) => {
        const payload = event.payload;
        dispatch({ type: "APPEND_EVENT", conversationId: cid, event: payload });

        if (payload.type === "plan_end") {
          const data = payload.data ?? {};
          const questionsRaw =
            (data as Record<string, unknown>).clarifying_questions ??
            (data as Record<string, unknown>).questions;
          const questions: ClarifyingQuestion[] =
            normalizeClarifyingQuestions(questionsRaw);
          const unresolvedCount = Array.isArray(
            (data as Record<string, unknown>).unresolved_clarifications
          )
            ? (
                (data as Record<string, unknown>).unresolved_clarifications as
                  | unknown[]
                  | null
              )?.length ?? 0
            : 0;
          const requiresClarification =
            Boolean((data as Record<string, unknown>).requires_clarification) ||
            unresolvedCount > 0 ||
            questions.length > 0;

          if (requiresClarification && questions.length > 0) {
            dispatch({ type: "SET_PLAN_QUESTIONS", questions });
            dispatch({ type: "SET_DIALOG", dialog: "planQuestions" });
          }
        }
      });

      try {
        const res = await invoke<BridgeResponse>("bridge_send_stream", {
          cmd,
          payload: { ...payload, conversation_id: cid },
        });
        dispatch({
          type: "FINALIZE_LAST",
          conversationId: cid,
          text: res.message,
          success: res.ok,
        });
        // 若仅生成 Plan 且需要澄清问题，则由 PLAN_END 事件驱动对话框，消息文本保持简短提示
      } catch (e) {
        if (!abortedRef.current) {
          dispatch({
            type: "FINALIZE_LAST",
            conversationId: cid,
            text: "请求失败: " + String(e),
            success: false,
          });
        }
      } finally {
        unlisten();
        dispatch({ type: "SET_BUSY_CONVERSATION", conversationId: null });
      }
    },
    [cid, dispatch],
  );

  const abortRun = useCallback(async () => {
    const busyId = state.busyConversationId;
    if (!busyId) return;
    abortedRef.current = true;
    try {
      await invoke("bridge_abort");
    } catch (_) {}
    dispatch({
      type: "FINALIZE_LAST",
      conversationId: busyId,
      text: "已取消",
      success: false,
    });
    dispatch({ type: "SET_BUSY_CONVERSATION", conversationId: null });
  }, [state.busyConversationId, dispatch]);

  const handleSubmit = useCallback(
    (raw: string) => {
      const line = raw.trim();
      if (!line) return;
      if (!cid) return;

      if (line.startsWith("/")) {
        const cmd = line.toLowerCase().split(/\s/)[0];
        if (cmd === "/quit" || cmd === "/exit") {
          window.close();
          return;
        }
        if (cmd === "/run") {
          dispatch({ type: "SET_MODE", mode: "run" });
          addMessage("system", "已切换为执行模式（/run）");
          return;
        }
        if (cmd === "/discuss") {
          dispatch({ type: "SET_MODE", mode: "discuss" });
          addMessage("system", "已切换为 Discuss 模式（/discuss），可与 LLM 闲聊");
          return;
        }
        if (cmd === "/plan") {
          dispatch({ type: "SET_MODE", mode: "plan" });
          addMessage("system", "已切换为规划模式（/plan）");
          return;
        }
        if (cmd === "/help") {
          dispatch({ type: "SET_DIALOG", dialog: "help" });
          return;
        }
        if (cmd === "/ops") {
          dispatch({ type: "SET_DIALOG", dialog: "ops" });
          return;
        }
        if (cmd === "/case") {
          const modelPath = line.slice(cmd.length).trim();
          if (!modelPath) {
            addMessage("system", "用法: /case <path_to_model.mph>", { success: false });
            return;
          }
          addMessage("user", line);
          sendCommand("case", { model_path: modelPath });
          return;
        }
        if (cmd === "/api") {
          dispatch({ type: "SET_DIALOG", dialog: "api" });
          return;
        }
        if (cmd === "/demo") {
          addMessage("user", line);
          sendCommand("demo");
          return;
        }
        if (cmd === "/doctor") {
          addMessage("user", line);
          sendCommand("doctor");
          return;
        }
        if (cmd === "/context") {
          dispatch({ type: "SET_DIALOG", dialog: "context" });
          return;
        }
        if (cmd === "/backend") {
          dispatch({ type: "SET_DIALOG", dialog: "backend" });
          return;
        }
        if (cmd === "/exec") {
          dispatch({ type: "SET_DIALOG", dialog: "exec" });
          return;
        }
        if (cmd === "/output") {
          dispatch({ type: "SET_DIALOG", dialog: "output" });
          return;
        }
        addMessage("system", "未知命令: " + cmd + "，输入 /help 查看帮助", {
          success: false,
        });
        return;
      }

      addMessage("user", line);
      // 记录本次用于触发 /run 的用户输入，供 PlanQuestionsDialog 二次调用使用
      dispatch({ type: "SET_LAST_PLAN_INPUT", input: line });

      const userCount = messages.filter((m) => m.role === "user").length;
      void (async () => {
        const apiPayload = getPayloadFromConfig(state.backend, loadApiConfig());

        if (userCount <= 1) {
          try {
            const res = await invoke<{ ok: boolean; message: string; title?: string }>("bridge_send", {
              cmd: "conversation_title_suggest",
              payload: {
                input: line,
                ...apiPayload,
              },
            });
            const suggested = (res.title ?? res.message ?? "").trim();
            if (suggested) {
              dispatch({ type: "SET_CONVERSATION_TITLE", id: cid, title: suggested });
            }
          } catch {
            const fallback = line.length > 50 ? line.slice(0, 47) + "..." : line;
            dispatch({ type: "SET_CONVERSATION_TITLE", id: cid, title: fallback });
          }
        }

        if (state.mode === "discuss") {
          await sendCommand("discuss", {
            input: line,
            ...apiPayload,
          });
        } else if (state.mode === "plan") {
          await sendCommand("plan", { input: line, ...apiPayload });
        } else {
          await sendStreamCommand("run", {
            input: line,
            output: state.outputDefault ?? undefined,
            workspace_dir: state.workspaceDir ?? undefined,
            use_react: true,
            no_context: false,
            ...apiPayload,
          });
        }
      })();
    },
    [
      cid,
      state.mode,
      state.outputDefault,
      state.workspaceDir,
      state.backend,
      messages,
      dispatch,
      addMessage,
      sendCommand,
      sendStreamCommand,
    ],
  );

  return { handleSubmit, sendCommand, sendStreamCommand, abortRun };
}
