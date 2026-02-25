# 贡献指南

## 提交规范（Commit Conventions）

本项目采用 [Conventional Commits](https://www.conventionalcommits.org/) 风格，并与仓库内设计范式一致。详见 [design-paradigms/commit-conventions.md](agent-design-skills/commit-conventions.md)。

### 格式

```
<type>(<scope>): <description>
```

- **type**：必填，如 `feat` / `fix` / `refactor` / `docs` / `chore` / `ci` / `release`
- **scope**：可选，表示影响范围（如 `core`、`agents`、`cli`、`config`）
- **description**：简短说明，祈使语气，句末不加句号

### 示例

- `feat(core): 添加 EventBus 与会话编排`
- `fix(agents): 修复 keyring 回退逻辑`
- `refactor(cli): 使用 get_agent 统一获取实例`
- `docs: 更新 CONTRIBUTING 与提交规范`

### 发布版本

发布时单独一条 commit：

- `release: Version x.y.z`

版本号与 `pyproject.toml` / `__init__.py` 一致；详细变更写在 CHANGELOG。

## 代码与架构

- 主入口与逻辑以 **agent** 包为准；测试与示例请使用 `agent` 与 `agent.dependencies`，勿依赖已废弃的 **src** 包。
- 设计范式见 [design-paradigms/](design-paradigms/) 目录。

## 测试

- **每次改动业务代码或数据结构，都需同步更新或补充对应的单元测试。** 测试与模块对应关系、运行方式见 [tests/README.md](../../tests/README.md)。
- 修改或新增模块后请运行 `uv run pytest tests/` 确保通过。
