/** 消息角色 */
export type MessageRole = "user" | "assistant" | "system";

/** 单条对话消息 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  success?: boolean;
  events?: RunEvent[];
  /** 时间戳（可选，用于展示） */
  time?: number;
}

/** 运行/流式事件（与后端 bridge-event 一致） */
export interface RunEvent {
  _event?: boolean;
  type: string;
  data?: Record<string, unknown>;
}

/** 对话框类型 */
export type DialogType =
  | null
  | "help"
  | "backend"
  | "context"
  | "exec"
  | "output"
  | "settings"
  | "ops";

/** 会话摘要 */
export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
}

/** 后端 bridge_send 返回 */
export interface BridgeResponse {
  ok: boolean;
  message: string;
  /** 部分命令（如 list_models）返回的列表 */
  models?: MyComsolModel[];
}

/** 设置页「我创建的模型」列表项 */
export interface MyComsolModel {
  path: string;
  title: string;
  is_latest?: boolean;
}

/** 斜杠命令项（Prompt 下拉用） */
export interface SlashCommandItem {
  name: string;
  display: string;
  description: string;
}

export const SLASH_COMMANDS: SlashCommandItem[] = [
  { name: "help", display: "/help", description: "显示帮助" },
  { name: "ops", display: "/ops", description: "支持的 COMSOL 操作" },
  { name: "run", display: "/run", description: "默认模式（自然语言 → 模型）" },
  { name: "plan", display: "/plan", description: "计划模式（自然语言 → JSON）" },
  { name: "exec", display: "/exec", description: "根据 JSON 创建模型" },
  { name: "backend", display: "/backend", description: "选择 LLM 后端" },
  { name: "context", display: "/context", description: "查看或清除对话历史" },
  { name: "output", display: "/output", description: "设置默认输出文件名" },
  { name: "demo", display: "/demo", description: "演示示例" },
  { name: "doctor", display: "/doctor", description: "环境诊断" },
  { name: "exit", display: "/exit", description: "退出" },
];

/** 常用场景快捷提示（MessageList 空状态） */
export interface QuickPromptItem {
  label: string;
  text: string;
}

export interface QuickPromptGroup {
  title: string;
  hint?: string;
  prompts: QuickPromptItem[];
}

/** 快捷提示：覆盖仅几何、几何+材料、几何+物理场、几何+研究、完整流程，用于测试各链路与中断点 */
export const QUICK_PROMPT_GROUPS: QuickPromptGroup[] = [
  {
    title: "仅几何",
    hint: "只建几何，不走材料/物理/求解",
    prompts: [
      { label: "矩形就行", text: "建个宽 1 米、高 0.5 米的矩形就行" },
      { label: "仅几何-圆", text: "仅几何：创建一个半径为 0.2 米的圆" },
      { label: "仅几何-长方体", text: "只建几何：创建一个 1×0.5×0.3 米的长方体" },
    ],
  },
  {
    title: "几何 + 材料",
    hint: "测试材料链路",
    prompts: [
      { label: "矩形+材料", text: "创建一个宽 1 米、高 0.5 米的矩形，并分配材料" },
    ],
  },
  {
    title: "几何 + 物理场",
    hint: "测试物理场链路",
    prompts: [
      { label: "矩形+传热", text: "创建一个矩形，添加固体传热物理场" },
      { label: "矩形+力学", text: "创建一个矩形，添加固体力学物理场" },
    ],
  },
  {
    title: "几何 + 研究/求解",
    hint: "测试研究与求解链路",
    prompts: [
      { label: "传热稳态", text: "创建一个矩形，添加传热物理场并做稳态研究" },
      { label: "完整流程-传热", text: "创建一个传热模型，包含一个矩形域，设置温度边界条件，进行稳态求解" },
    ],
  },
  {
    title: "诊断与命令",
    hint: "环境/帮助",
    prompts: [
      { label: "环境诊断", text: "/doctor" },
      { label: "帮助", text: "/help" },
    ],
  },
];

/** COMSOL 操作说明（/ops 弹窗） */
export interface ComsolOp {
  action: string;
  label: string;
  description: string;
}

export const COMSOL_OPS: ComsolOp[] = [
  { action: "geometry", label: "几何", description: "创建/编辑几何体与布尔运算" },
  { action: "physics", label: "物理场", description: "添加物理场与边界条件" },
  { action: "mesh", label: "网格", description: "划分网格" },
  { action: "study", label: "研究", description: "稳态/瞬态/特征值等研究" },
  { action: "material", label: "材料", description: "材料分配与属性" },
];
