# ReAct 与工具调用范式

Thought-Action-Observation 循环与工具注册/调用的通用模式，与具体业务无关。

## 1. ReAct 循环骨架

- **步骤**：Thought（思考当前情况）→ Action（决定行动，可带参数）→ Observation（执行并观察结果）→ 根据结果判断是否继续或结束。
- **实现**：循环内先调用「思考」得到 thought，再调用「决定行动」得到 action，再调用「观察」（实际执行工具或模拟），再判断 `_is_complete(observation)`；达到最大迭代次数或完成则退出，否则进入下一轮。
- **日志与可观测**：每轮 thought/action/observation 可 append 到 response_parts 或通过 EventBus 发出，便于调试与 UI 展示「推理过程」。

## 2. 工具注册与描述

- **工具列表**：Agent 或 ReAct 引擎持有一个 `tools: List[Tool]`，每个 Tool 有 name、description、parameters（schema），便于生成 function calling 或 ReAct 的 Action 描述。
- **与 LLM 对接**：将 tools 转为模型要求的格式（如 OpenAI function 的 name/description/parameters），在请求时传入；模型返回的 tool_calls 再映射回本地 Tool 执行。

## 3. 工具执行与观察

- **执行层**：根据 action 名称找到对应 Tool，传入解析后的参数，执行（同步或异步），得到结果字符串或结构化结果。
- **Observation**：将执行结果（成功输出或异常信息）格式化为 Observation 文本，回填到对话或下一轮 Thought 的上下文中；若执行失败，Observation 中应包含错误信息，让模型能「看到」失败并决定重试或换策略。
- **安全与权限**：敏感操作（如执行系统命令、写文件）可在执行层做白名单、确认或权限检查，与 ReAct 逻辑解耦。

## 4. 完成条件与迭代上限

- **完成条件**：在 `_is_complete(observation)` 中根据 observation 文本或结构化结果判断（如包含「完成」「成功」或特定标记）；也可由模型在 Thought 中显式输出「任务完成」再由解析器识别。
- **上限**：设置 `max_iterations`（如 5 或 10），防止死循环；达到上限后强制退出并返回当前 response_parts，便于用户看到「未完成但已停止」的状态。

## 5. 可复用要点小结

- ReAct：固定循环 Thought → Action → Observation，带完成判断与迭代上限。
- 工具：name/description/parameters 注册；执行层统一调度，Observation 统一格式化。
- 执行层做安全/权限；ReAct 层只负责调用与拼装上下文，便于测试与替换执行后端。
