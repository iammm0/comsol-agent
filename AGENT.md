# AGENT 运行说明

这份文档面向维护者、贡献者和需要理解执行链的人。它说明 mph-agent 在 `feat-clawcode-comsol-dispatch` 分支里是怎么工作的，哪些模块是关键路径，以及接入 claw-code 后应该关注什么。

## 这个分支的核心变化

这条分支不是单纯的功能补丁，而是把 COMSOL 执行层换成了更可编排的结构：

- `agent/react/action_executor.py` 负责把高层计划分发给具体动作，并决定是否走 claw-code。
- `agent/executor/clawcode_dispatcher.py` 负责把单个 COMSOL 步骤交给嵌入式 claw-code 执行。
- `agent/executor/java_api_controller.py` 负责补齐官方 Java API 能力，处理材料、物理场、研究、静态调用和节点级兜底。
- `agent/planner/material_agent.py` 对基础材料做了更稳的快速识别，减少 LLM 在简单输入上的漂移。
- `scripts/agent_build_loop.py` 负责端到端回归、失败复现和日志留档。

你可以把它理解为：

`自然语言 -> 计划 -> 单步动作 -> claw-code/Java API 执行 -> 阶段模型写回 -> 继续迭代`

这才是这条分支真正想展示给开源社区的东西。

## 关键执行链

1. 用户在桌面端或 CLI 中输入建模需求。
2. `ReActAgent` 或规划器先生成结构化计划。
3. `ActionExecutor.execute()` 判断动作是否属于 `COMSOL_DELEGATED_ACTIONS`。
4. 如果启用了 `settings.claw_code_enabled`，则动作交给 `ClawCodeComsolDispatcher.dispatch()`。
5. claw-code 运行结束后返回严格 JSON，`ActionExecutor` 再把结果写回上下文、阶段模型和事件流。
6. 如果 claw-code 无法完成，`JavaAPIController` 继续用官方 API 兜底。

## claw-code 如何工作

`ClawCodeComsolDispatcher` 不是一个外部守护进程，它是在 mph-agent 进程内运行的嵌入式执行库。

它会做几件事：

- 组装当前计划、当前步骤、思考内容和目标输出路径。
- 设置最少量的环境变量，只暴露 `MPH_AGENT_ROOT`。
- 构建一个 `LocalCodingAgent`，让它在仓库根目录内执行单步任务。
- 要求结果只能是 JSON，避免自由文本破坏上层解析。

如果你要排查执行问题，优先看这几个点：

- `run_result.stop_reason`
- `run_result.final_output`
- `run_result.turns`
- `run_result.tool_calls`

这些字段会被保留到 `details` 里，方便回放和审计。

## 阶段性模型策略

`ActionExecutor` 不再只维护一个最终模型文件，而是为不同阶段生成独立路径，例如：

- `*_geometry.mph`
- `*_material.mph`
- `*_physics.mph`
- `*_mesh.mph`
- `*_study.mph`
- `*_solve.mph`
- `*_latest.mph`

这样做的好处是：

- 每一步的产物都可见。
- 出错时更容易定位是哪一层出了问题。
- 便于回归测试和社区复现。

## 调试建议

如果你在本分支里工作，建议按这个顺序排查：

1. 先看 `logs/agent-build-loop/` 是否已有一次完整回归记录。
2. 再看对应阶段 `.mph` 是否已生成。
3. 然后看 `ActionExecutor` 发出的事件。
4. 最后再钻进 `clawcode_dispatcher.py` 和 `java_api_controller.py` 的返回内容。

## 环境变量

这条分支仍然依赖原有 COMSOL 与 LLM 配置，同时新增了 claw-code 相关配置：

- `CLAW_CODE_ENABLED`
- `CLAW_CODE_MAX_TURNS`
- `CLAW_CODE_TIMEOUT_SECONDS`
- `CLAW_CODE_MODEL`
- `CLAW_CODE_BASE_URL`
- `CLAW_CODE_API_KEY`

如果没有显式设置 `CLAW_CODE_MODEL` 和 `CLAW_CODE_BASE_URL`，执行层会尽量复用当前桌面端选择的 LLM 后端，减少重复配置。

## 与 README 的分工

`README.md` 面向外部读者，讲项目是什么、能做什么、这条分支为什么值得关注。

`AGENT.md` 面向维护者，讲内部模块怎么协作、claw-code 怎么接入、出了问题先看哪里。

两者分开是故意的。这样 README 可以更像开源项目主页，AGENT 则保留足够的工程细节，方便后续继续演进。
