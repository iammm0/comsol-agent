# 提交方式与 Commit 信息习惯

基于 Conventional Commits，结合本项目实际历史的提交格式约定。与具体业务无关，可在 CLI 智能体或其他项目中复用。

## 1. 基本格式

```
<type>(<scope>): <description>
```

- **type**：必填，小写，表示变更性质。
- **scope**：可选，括号包裹，表示影响范围（模块/包/目录）。
- **description**：必填，简短说明，中文或英文均可；句末不加句号；使用祈使语气（如「添加」「修复」而非「添加了」「修复了」）。

示例：

- `feat(core): 智能体与安全 ReAct 统一使用 _create_llm`
- `refactor(hackbot): CLI 与交互流程`
- `fix(agents): qa_agent 小改动`
- `chore(deps): pyproject.toml 更新`

## 2. Type 约定

| type       | 含义           | 典型用法 |
|-----------|----------------|----------|
| **feat**  | 新功能         | 新模块、新 API、新能力 |
| **fix**   | 缺陷修复       | 修 bug、修正错误行为 |
| **refactor** | 重构（不修 bug、不增功能） | 结构调整、重命名、抽公共逻辑 |
| **docs**  | 文档           | README、CHANGELOG、注释、站点 |
| **chore** | 杂项/维护      | 依赖更新、目录调整、清理、发布相关 |
| **ci**    | 持续集成       | GitHub Actions、构建/测试流水线 |
| **release** | 发布版本     | 版本号提交、Release 说明（见下） |

不常用但可保留：`perf`（性能）、`test`（测试）、`style`（格式/风格）。

## 3. Scope 习惯

按**代码/功能边界**划分，与目录或包名对应，便于从 commit 快速定位改动范围。本项目常见 scope 示例：

- `core`、`agents`、`utils`、`tools`、`tui`、`router`、`defense`、`controller`、`database`、`prompts`
- `hackbot`（CLI 入口与交互）
- `config`、`deps`、`deploy`、`ci`

单次提交影响多个模块时，可只写主要模块，或拆成多个 commit；scope 可省略（如 `feat: 主流程集成`）。

## 4. Release 提交

发布版本时单独一条 commit，格式可固定为：

- `release: Version <x.y.z>`
- 或带简短说明：`release: Version 1.2.5`、`release: Version 1.2.3 - Fix config command name`

版本号与 `pyproject.toml` / `__init__.py` 一致；详细变更写在 CHANGELOG，不塞进 commit body。

## 5. Description 写法

- **简短**：一行能说清「做了什么」即可；细节放 commit body 或 PR 描述。
- **祈使语气**：用「添加」「修复」「更新」「移除」，不用「添加了」「修复了」。
- **中文/英文**：与项目日常沟通一致即可；本项目以中文为主，新项目可自定。
- **避免**：无信息量的「更新」「修改」「fix」「update」等单独成句；尽量带上对象（更新了什么、修复了哪类问题）。

## 6. 多行 Commit（Body）

需要补充说明时，在首行后空一行再写 body：

```
feat(config): 添加密钥环配置系统和独立配置 CLI

- 使用 keyring 存储 API Key
- 新增 configure 子命令
```

Body 不强制格式，可用于列出要点、原因、影响范围等。

## 7. 可复用要点小结

- 格式：`<type>(<scope>): <description>`，Conventional Commits 风格。
- Type：feat / fix / refactor / docs / chore / ci / release 等。
- Scope：与模块/目录对应，可选。
- Description：简短、祈使、一句说清；release 用固定句式。
- 细节与列表放 body 或 CHANGELOG，不堆在首行。
