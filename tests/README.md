# 单元测试说明

本目录包含各模块的单元测试，与 `agent/`、`schemas/` 等代码一一对应。

## 重要约定

**每次改动业务代码或数据结构时，必须同步更新或补充对应的测试程序。**

- 修改 `agent/` 下某模块后，请更新本目录下对应的 `test_*.py`。
- 修改 `schemas/` 下某 schema 后，请更新 `test_schemas.py` 或相关测试中的序列化/校验用例。
- 新增模块或公开接口时，请新增或扩展测试用例，保证新行为可被断言。

运行测试：在项目根目录执行 `uv run pytest tests/` 或 `pytest tests/`。

---

## 测试文件与模块对应关系

| 测试文件 | 对应模块 | 说明 |
|----------|----------|------|
| **test_planner.py** | `agent/planner/` | GeometryAgent 解析、JSON 提取、矩形/圆/椭圆 plan |
| **test_react.py** | `agent/react/` | ReasoningEngine、ActionExecutor、Observer、IterationController、ReActAgent |
| **test_executor.py** | `agent/executor/` | JavaGenerator 代码生成、形状代码片段（不启动 JVM） |
| **test_skills.py** | `agent/skills/` | SkillLoader 解析 SKILL.md、SkillInjector 注入、可选向量检索 |
| **test_schemas.py** | `schemas/` | GeometryPlan/Shape、PhysicsPlan、StudyPlan、TaskPlan/ReActTaskPlan 等序列化与校验 |
| **test_integration.py** | 跨模块 | 集成用例：Plan 序列化、端到端数据流（可扩展） |

---

## 运行与过滤

```bash
# 运行全部测试
uv run pytest tests/ -v

# 仅运行某文件
uv run pytest tests/test_planner.py -v

# 仅运行某类或某用例
uv run pytest tests/test_schemas.py::TestGeometryPlan -v
```

测试中通过 Mock 隔离 LLM、COMSOL JVM 等外部依赖，无需配置真实 API 或 COMSOL 即可通过。
