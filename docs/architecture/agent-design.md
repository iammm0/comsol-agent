# Agent 设计文档

本文档描述 **当前已实现** 的 Agent 职责与协作方式：路由、ReAct 核心、Planner、Executor、Q&A/Summary。完整架构与流程图见 [architecture.md](architecture.md)。

---

## 一、入口与路由

- **入口**：桌面端通过 TUI Bridge 调用 `agent.actions.do_run` 等；CLI 通过 `cli.py` 调用相同 actions。
- **路由**：`agent.router.route(user_input)` 返回 `"qa"` 或 `"technical"`。
  - **qa**：问候、帮助、短句无操作词 → 使用 `QAAgent.process()`，直接返回助手回复。
  - **technical**：包含操作类动词（创建、添加、建模、几何、物理、网格、求解等）→ 使用 `ReActAgent.run()`，再经 `SummaryAgent.process()` 返回执行结果摘要。

---

## 二、ReActAgent（Core Agent）

**职责**：协调 Think → Act → Observe → Iterate 循环，直至任务完成或失败/达到最大迭代。

**主要方法**：

- `run(user_input, output_filename, memory_context, output_dir)`：执行完整 ReAct 流程，返回生成的 .mph 路径。
- `think(plan)`：调用 ReasoningEngine.reason，返回下一步 thought（含 action、parameters）。
- `act(plan, thought)`：调用 ActionExecutor.execute，执行当前步骤。
- `observe(plan, result)`：调用 Observer.observe，得到 Observation。
- `iterate(plan, observation)`：调用 IterationController.update_plan，更新计划（含错误恢复判断）。

**依赖**：LLMClient、ReasoningEngine、ActionExecutor、Observer、IterationController；可选 EventBus、ContextManager。

---

## 三、ReasoningEngine（推理引擎）

**职责**：理解需求、规划执行路径与推理检查点、在每轮 ReAct 中推理下一步行动。

**关键方法**：

- `understand_and_plan(user_input, model_name, memory_context)`：理解用户需求并生成初始 ReActTaskPlan（execution_path、reasoning_path、plan_description）。
- `reason(plan)`：根据当前计划与历史观察，返回 thought（action、parameters 等）；action 为 `complete` 时表示任务完成。

---

## 四、ActionExecutor（行动执行器）

**职责**：根据 thought 中的 action 执行具体建模操作，内部调用 Planner 与 Executor。

**支持的 action**：`create_geometry`、`add_material`、`add_physics`、`generate_mesh`、`configure_study`、`solve`、`retry`、`skip`。

**典型流程**：

- **create_geometry**：若无 geometry_plan 则用 GeometryAgent.parse 解析，再交给 COMSOLRunner 创建几何并保存/更新模型。
- **add_material**：MaterialAgent 解析 → JavaAPIController / COMSOLRunner 添加材料。
- **add_physics**：PhysicsAgent 解析 → 执行器添加物理场。
- **generate_mesh** / **configure_study** / **solve**：调用 COMSOLRunner / JavaAPIController 执行对应步骤。

---

## 五、Planner Agents

| Agent | 职责 | 产出 |
|-------|------|------|
| **GeometryAgent** | 自然语言几何需求 → 结构化几何计划 | GeometryPlan |
| **PhysicsAgent** | 物理场需求 → 物理场计划 | PhysicsPlan |
| **StudyAgent** | 研究类型与求解需求 → 研究计划 | StudyPlan |
| **MaterialAgent** | 材料需求 → 材料计划 | 材料相关结构 |

均由 ActionExecutor 按 step 类型按需调用；ReAct 循环中可能多次调用同一 Planner（例如多步几何）。

---

## 六、Executor

- **COMSOLRunner**：启动/复用 JVM、加载 COMSOL JAR、根据 GeometryPlan 等创建模型、构建几何、保存 .mph；对外主要接口如 `create_model_from_plan`、保存/更新模型文件。
- **JavaAPIController**：封装 COMSOL Java API 的细粒度调用（材料、物理场、网格、研究、求解等），供 ActionExecutor 使用。
- **JavaGenerator**：根据 GeometryPlan 生成 Java 代码（可选路径，当前主流程以 COMSOLRunner/JavaAPIController 直接调用为主）。

---

## 七、Observer 与 IterationController

- **Observer**：根据 ExecutionStep 的执行结果（result）与计划状态，生成 Observation（status：success / warning / error，message）。
- **IterationController**：根据 Observation 更新 ReActTaskPlan（修正步骤、回退或重试）；对不可恢复错误设置 plan.status = "failed"，ReActAgent 据此终止循环。

---

## 八、QAAgent 与 SummaryAgent

- **QAAgent**：处理问答、帮助、介绍类输入，不调用工具，快速返回回复。
- **SummaryAgent**：对技术路径的执行结果（如「模型已生成: path」或异常信息）做摘要，供前端展示。

---

## 九、协作流程概览

```
用户输入
  → route() → qa ? QAAgent.process() → 回复
            → technical ? ReActAgent.run() → ActionExecutor 多次调用 Planner + Executor
                                            → Observer → IterationController（若需）
                                            → SummaryAgent.process() → 摘要
```

错误处理与可观测性：

- LLM 调用失败：重试（在 LLM 客户端或调用处）。
- JSON/计划解析失败：多策略提取与验证（见各 Planner）。
- COMSOL/执行错误：Observer 标记为 error/warning，IterationController 决定是否更新计划继续或置为 failed。
- 事件：通过 EventBus 发送 PLAN_START/END、THINK_CHUNK、ACTION_START、EXEC_RESULT、OBSERVATION、STEP_START/END 等，TUI Bridge 转发给桌面端做流式展示。

---

## 十、参考

- 系统架构与 ReAct 流程图：[architecture.md](architecture.md)
- 多智能体范式与路由：[agent-design-skills/agent-architecture.md](../agent-design-skills/agent-architecture.md)
- 会话与 EventBus：[agent-design-skills/session-and-events.md](../agent-design-skills/session-and-events.md)
