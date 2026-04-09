import type { ClarifyingOption, ClarifyingQuestion } from "./types";

/**
 * 固定的“补充选项”ID，前后端可据此识别并允许用户补充文本。
 */
export const SUPPLEMENT_OPTION_ID = "opt_supplement";

/**
 * 固定的“自动决策”兜底选项。
 */
export const AUTO_OPTION_ID = "opt_auto";

/**
 * 澄清问题规范化配置。
 */
export interface NormalizeClarifyingQuestionOptions {
  /**
   * 当问题缺少 type 时使用的默认值。
   * 默认 single。
   */
  defaultType?: ClarifyingQuestion["type"];

  /**
   * 补充选项的展示文本。
   */
  supplementLabel?: string;

  /**
   * 补充选项的语义值。
   */
  supplementValue?: string;

  /**
   * 自动决策选项的展示文本。
   */
  autoLabel?: string;

  /**
   * 自动决策选项的语义值。
   */
  autoValue?: string;
}

const DEFAULT_NORMALIZE_OPTIONS: Required<NormalizeClarifyingQuestionOptions> = {
  defaultType: "single",
  supplementLabel: "其他（请补充）",
  supplementValue: "supplement",
  autoLabel: "推荐：采用当前描述中的合理默认",
  autoValue: "auto",
};

function normalizeText(input: unknown): string {
  return String(input ?? "").trim();
}

function normalizeQuestionType(
  type: unknown,
  fallback: ClarifyingQuestion["type"]
): ClarifyingQuestion["type"] {
  const t = normalizeText(type).toLowerCase();
  return t === "multi" ? "multi" : t === "single" ? "single" : fallback;
}

function isPlaceholderQuestionText(text: string): boolean {
  const t = normalizeText(text).toLowerCase();
  if (!t) return true;
  return /^(问题|question)\s*\d+$/.test(t);
}

function isMeaningfulOption(option: ClarifyingOption): boolean {
  const id = normalizeText(option.id).toLowerCase();
  const value = normalizeText(option.value).toLowerCase();
  if (!id) return false;
  if (id === SUPPLEMENT_OPTION_ID || id === AUTO_OPTION_ID) return false;
  if (value === "supplement" || value === "auto" || value === "skip") return false;
  return true;
}

function dedupeOptions(options: ClarifyingOption[]): ClarifyingOption[] {
  const seen = new Set<string>();
  const out: ClarifyingOption[] = [];
  for (const opt of options) {
    const key = normalizeText(opt.id) || normalizeText(opt.value) || normalizeText(opt.label);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(opt);
  }
  return out;
}

function normalizeOptionLike(
  raw: unknown,
  index: number
): ClarifyingOption | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const id = normalizeText(r.id) || `opt_${index + 1}`;
  const label = normalizeText(r.label) || normalizeText(r.value) || `选项 ${index + 1}`;
  const value = normalizeText(r.value) || id;
  const recommended = r.recommended === true;
  return { id, label, value, recommended };
}

function ensureSupplementOption(
  options: ClarifyingOption[],
  config: Required<NormalizeClarifyingQuestionOptions>
): ClarifyingOption[] {
  const hasSupplement = options.some((o) => normalizeText(o.id) === SUPPLEMENT_OPTION_ID);
  if (hasSupplement) return options;
  return [
    ...options,
    {
      id: SUPPLEMENT_OPTION_ID,
      label: config.supplementLabel,
      value: config.supplementValue,
    },
  ];
}

function ensureFallbackOptions(
  options: ClarifyingOption[],
  config: Required<NormalizeClarifyingQuestionOptions>
): ClarifyingOption[] {
  if (options.length > 0) return options;
  return [
    {
      id: AUTO_OPTION_ID,
      label: config.autoLabel,
      value: config.autoValue,
    },
  ];
}

/**
 * 将任意输入规范化为可渲染的 ClarifyingQuestion。
 *
 * 约束：
 * 1) 一定有 question 文本；
 * 2) type 只能是 single / multi（按问题类型区分）；
 * 3) 至少有 1 个常规选项；
 * 4) 始终追加“补充选项”（SUPPLEMENT_OPTION_ID）。
 */
export function normalizeClarifyingQuestion(
  raw: unknown,
  index: number,
  options?: NormalizeClarifyingQuestionOptions
): ClarifyingQuestion {
  const config = { ...DEFAULT_NORMALIZE_OPTIONS, ...(options ?? {}) };

  const r = (
    raw && typeof raw === "object"
      ? raw
      : { text: raw }
  ) as Record<string, unknown>;
  const id = normalizeText(r.id) || `q${index + 1}`;
  const text = normalizeText(r.text) || `问题 ${index + 1}`;
  const type = normalizeQuestionType(r.type, config.defaultType);

  const rawOptions = Array.isArray(r.options) ? r.options : [];
  const parsed = rawOptions
    .map((item, i) => normalizeOptionLike(item, i))
    .filter((x): x is ClarifyingOption => x !== null);

  const withFallback = ensureFallbackOptions(dedupeOptions(parsed), config);
  const finalOptions = dedupeOptions(ensureSupplementOption(withFallback, config));

  return {
    id,
    text,
    type,
    options: finalOptions,
  };
}

/**
 * 批量规范化澄清问题列表。
 *
 * 若输入为空，返回 []。
 */
export function normalizeClarifyingQuestions(
  rawQuestions: unknown,
  options?: NormalizeClarifyingQuestionOptions
): ClarifyingQuestion[] {
  if (!Array.isArray(rawQuestions)) return [];
  const normalized = rawQuestions.map((q, i) => normalizeClarifyingQuestion(q, i, options));
  return normalized.filter((q) => {
    if (isPlaceholderQuestionText(q.text)) return false;
    const hasMeaningfulOption = q.options.some((opt) => isMeaningfulOption(opt));
    return hasMeaningfulOption;
  });
}

/**
 * 判断某问题是否为多选。
 */
export function isMultiSelectQuestion(question: ClarifyingQuestion): boolean {
  return question.type === "multi";
}

/**
 * 判断某选项是否为“补充选项”。
 */
export function isSupplementOption(option: ClarifyingOption): boolean {
  return normalizeText(option.id) === SUPPLEMENT_OPTION_ID;
}
