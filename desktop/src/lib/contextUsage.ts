import type { AgentMode } from "./types";
import {
  getContextWindowInfo,
  type ApiConfig,
  type LLMBackendId,
} from "./apiConfig";

const CJK_CHAR_PATTERN =
  /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]/g;

const ASCII_PUNCTUATION_PATTERN = /[.,!?;:()[\]{}<>"'`~@#$%^&*_+=/\\|-]/g;

const MODE_OVERHEAD_TOKENS: Record<AgentMode, number> = {
  discuss: 1400,
  plan: 1900,
  run: 2600,
};

const MODE_RESPONSE_RESERVE_TOKENS: Record<AgentMode, number> = {
  discuss: 4096,
  plan: 6144,
  run: 8192,
};

export type ContextUsageStatus = "normal" | "warning" | "danger";

export interface ContextUsageEstimate {
  maxTokens: number;
  usedTokens: number;
  remainingTokens: number;
  safeRemainingTokens: number;
  reserveTokens: number;
  ratio: number;
  percent: number;
  status: ContextUsageStatus;
  providerLabel: string;
  modelLabel: string;
  windowSourceLabel: string;
  memoryTokens: number;
  inputTokens: number;
  overheadTokens: number;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function estimateTextTokens(text: string): number {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) return 0;

  const cjkCount = (normalized.match(CJK_CHAR_PATTERN) ?? []).length;
  const punctuationCount =
    (normalized.match(ASCII_PUNCTUATION_PATTERN) ?? []).length;
  const asciiCount = Math.max(0, normalized.length - cjkCount);

  return Math.max(
    1,
    Math.ceil(cjkCount * 1.15 + asciiCount / 4 + punctuationCount * 0.15)
  );
}

export function formatCompactTokenCount(value: number): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(value >= 10000000 ? 0 : 1)}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(value >= 100000 ? 0 : 1)}k`;
  }
  return `${value}`;
}

function getWindowSourceLabel(
  source: "model-pattern" | "provider-default" | "fallback"
): string {
  switch (source) {
    case "model-pattern":
      return "按模型名估算";
    case "provider-default":
      return "按 provider 默认估算";
    default:
      return "按通用上限估算";
  }
}

export function estimateContextUsage(options: {
  config: ApiConfig;
  backend?: LLMBackendId | null;
  mode: AgentMode;
  memoryContextText: string;
  draftText: string;
}): ContextUsageEstimate {
  const windowInfo = getContextWindowInfo(options.config, options.backend);
  const memoryTokens = estimateTextTokens(options.memoryContextText);
  const inputTokens = estimateTextTokens(options.draftText);
  const overheadTokens = MODE_OVERHEAD_TOKENS[options.mode];
  const reserveTokens = Math.min(
    MODE_RESPONSE_RESERVE_TOKENS[options.mode],
    Math.max(2048, Math.floor(windowInfo.maxTokens * 0.12))
  );

  const usedTokens = clamp(
    memoryTokens + inputTokens + overheadTokens,
    0,
    windowInfo.maxTokens
  );
  const remainingTokens = Math.max(0, windowInfo.maxTokens - usedTokens);
  const safeRemainingTokens = Math.max(0, remainingTokens - reserveTokens);
  const ratio = clamp(usedTokens / windowInfo.maxTokens, 0, 1);

  let status: ContextUsageStatus = "normal";
  if (ratio >= 0.88) {
    status = "danger";
  } else if (ratio >= 0.7) {
    status = "warning";
  }

  return {
    maxTokens: windowInfo.maxTokens,
    usedTokens,
    remainingTokens,
    safeRemainingTokens,
    reserveTokens,
    ratio,
    percent: Math.round(ratio * 100),
    status,
    providerLabel: windowInfo.providerLabel,
    modelLabel: windowInfo.model || "未设置模型",
    windowSourceLabel: getWindowSourceLabel(windowInfo.source),
    memoryTokens,
    inputTokens,
    overheadTokens,
  };
}
