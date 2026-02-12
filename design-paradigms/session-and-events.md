# 会话与事件总线范式

会话编排与 EventBus 解耦核心逻辑与 UI，与具体业务无关。

## 1. 会话编排器职责

- **会话管理**：创建/切换/恢复会话，维护「当前会话」指针；每个会话可有 id、名称、创建时间、关联的 Agent 类型等元数据。
- **流程编排**：根据「路由结果」决定本轮走 Q&A 还是「Planner → Core Agent → Summary」；在编排层调用各 Agent，而不是在 Agent 内互相调用，便于测试与替换。
- **上下文传递**：当轮的工具执行结果、待办状态等，由编排器收集并传给 Summary 或下一阶段；编排器持有「当前轮次工具结果」等临时状态，请求结束后可清空或归档。

## 2. 依赖注入与可选回调

- **构造注入**：EventBus、Console、agents 字典、planner/qa/summary 实例、以及可选的 `get_root_password`、`resolve_agent` 等，通过构造函数传入，便于单测时替换。
- **默认实例**：若未传入 planner/qa/summary，在编排器内部 new 默认实现，保证「只传 EventBus + Console」也能跑通最小流程。

## 3. EventBus 设计

- **类型**：使用枚举定义事件类型（如 `PLAN_START`、`THINK_CHUNK`、`EXEC_RESULT`、`CONTENT`、`ERROR` 等），避免魔法字符串。
- **事件体**：统一结构，如 `Event(type: EventType, data: dict, timestamp, iteration)`，便于订阅方按 type 过滤、按 data 取数。
- **订阅**：支持按事件类型注册 handler；可支持「全局 handler」接收所有事件，用于日志或监控。
- **发射**：核心逻辑（Agent、Planner、工具执行）只调用 `bus.emit(event)`，不依赖任何 UI；UI 层订阅感兴趣的事件并更新界面（如进度条、流式文本、任务阶段标签）。
- **异步**：若 handler 可能为 async，可在 emit 时用 asyncio 调度，或约定「同步 emit、handler 内自行 asyncio.create_task」，避免阻塞主流程。

## 4. UI 与核心解耦

- **核心不引用 UI**：SessionManager、Agent、Planner 不 import 任何 TUI/Web 组件；仅依赖 EventBus 和传入的 Console（若需打印兜底信息）。
- **UI 订阅事件**：TUI 或 Web 层在启动时订阅 EventBus，根据 EventType 更新对应组件（如 plan_start → 显示规划中；think_chunk → 追加思考流；exec_result → 更新结果区）。
- **任务阶段**：可定义 `TASK_PHASE` 类事件，payload 为当前阶段名（如 "planning"、"executing"、"summarizing"），供 UI 显示「当前在做什么」，提升可观测性。

## 5. 可复用要点小结

- 会话编排器：管会话生命周期 + 按路由调用各 Agent + 收集当轮结果。
- 依赖通过构造函数注入，可选回调（如 get_root_password）便于扩展。
- EventBus：枚举事件类型、统一 Event 结构、按类型订阅、核心只 emit。
- 核心层不依赖 UI；UI 只订阅事件并更新界面，实现解耦。
