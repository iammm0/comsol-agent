# agent 包目录说明

本包实现 COMSOL 建模 Agent 的主流程：自然语言 → 规划 → 执行 → .mph 模型。

## 目录结构

```
agent/
├── README.md           # 本说明
├── __init__.py
├── base.py             # BaseAgent 抽象基类（process 接口）
├── dependencies.py     # 依赖注入：get_agent、get_settings、EventBus、prompt_manager 等单例
├── events.py           # EventBus、EventType、Event（事件总线）
├── router.py           # 路由：route(user_input) → 技术/执行/Q&A 等
├── session.py          # 会话编排：与 TUI/CLI 配合，按路由调用 Agent
├── actions.py          # 具体动作：run/plan/exec/demo 等，供 CLI 与 TUI 桥接调用
├── tui_bridge.py       # TUI 桥接：stdin/stdout JSON 行，供仓库根 tui/（TS）前端调用
├── tools.py            # 工具函数（供 Agent 或 CLI 使用）
├── qa_agent.py         # Q&A Agent（通用问答）
├── summary_agent.py    # 摘要 Agent（对执行结果做摘要）
│
├── planner/            # 规划层：自然语言 → 结构化计划
│   ├── geometry_agent.py   # 几何计划（矩形/圆/椭圆）
│   ├── physics_agent.py    # 物理场计划
│   └── study_agent.py      # 研究类型计划
│
├── react/              # ReAct 架构：推理与执行循环
│   ├── react_agent.py      # ReAct 主控
│   ├── reasoning_engine.py # 需求理解、步骤规划、验证与改进
│   ├── action_executor.py  # 执行几何/物理/研究等步骤，调 COMSOL
│   ├── observer.py        # 观察执行结果
│   └── iteration_controller.py  # 迭代控制与计划更新
│
├── executor/           # 执行层：计划 → COMSOL 调用 / Java 代码
│   ├── comsol_runner.py    # 启动 JVM、调用 COMSOL Java API、保存 .mph
│   ├── java_generator.py   # 根据 GeometryPlan 生成 Java 代码
│   ├── java_api_controller.py  # Java API 封装与调用
│   └── sandbox.py          # 沙箱/安全相关（可选）
│
├── skills/             # 技能/隐性知识：加载与注入
│   ├── loader.py           # 扫描 skills/ 目录，解析 SKILL.md
│   ├── injector.py         # 按 query 注入技能到 prompt
│   └── vector_store.py     # SQLite + sqlite-vec 持久化与向量检索
│
└── utils/              # 通用工具与配置
    ├── config.py           # 配置、get_project_root、get_settings
    ├── prompt_manager.py   # 提示词模板加载与格式化
    ├── prompt_loader.py    # 对 prompt_manager 的便捷封装（单例）
    ├── llm.py              # LLM 客户端（DeepSeek/Kimi/Ollama/OpenAI 兼容）
    ├── logger.py           # 日志
    ├── java_runtime.py     # JAVA_HOME、内置 JDK 下载与路径
    ├── env_check.py        # 环境诊断（doctor）
    ├── context_manager.py  # 上下文管理
    └── secrets.py          # API Key 等敏感信息（keyring 等）
```

## 职责概览

| 区域 | 职责 |
|------|------|
| **根目录** | 入口与编排：base、dependencies、events、router、session、actions、tui、qa/summary agent |
| **planner/** | 将自然语言解析为 GeometryPlan / PhysicsPlan / StudyPlan |
| **react/** | ReAct 循环：理解 → 规划 → 执行 → 观察 → 迭代，直至完成或失败 |
| **executor/** | 与 COMSOL 交互：生成/执行 Java 代码、保存 .mph |
| **skills/** | 从 `skills/` 目录加载隐性知识，按 query 注入到 LLM prompt |
| **utils/** | 配置、LLM、日志、Java 环境、提示词、环境检查等 |

## 调用关系（简要）

- **CLI / main.py** → `actions`、`dependencies`（get_agent、get_settings）→ **react.react_agent** 或 **planner** + **executor**。
- **ReActAgent** 使用 **reasoning_engine**、**action_executor**、**observer**、**iteration_controller**；action_executor 内部调 **planner**（geometry/physics/study）与 **executor**（comsol_runner）。
- **Planner** 与 **reasoning_engine** 通过 **skills.get_skill_injector()** 注入隐性知识，通过 **utils.prompt_loader** 加载提示词，通过 **utils.llm** 调用大模型。

架构与伪代码文档见仓库根目录下 `docs/architecture/`。
