# 设计范式与程序设计经验

本目录收纳**与具体业务无关**的程序设计经验与范式，来源于本项目的架构与实现，可在其他项目（如 CLI 智能体）中直接引用或改编。

## 文档索引

| 文档 | 说明 |
|------|------|
| [agent-architecture.md](agent-architecture.md) | 多智能体架构：基类抽象、消息模型、路由分发 |
| [skill-plugin-system.md](skill-plugin-system.md) | 技能/插件系统：Markdown 技能加载、清单解析、按需注入 |
| [cli-and-dependencies.md](cli-and-dependencies.md) | CLI 入口与依赖：极简入口、按需实例化、单例与 Depends |
| [config-and-env.md](config-and-env.md) | 配置与环境：.env 分层、敏感信息 keyring、env.example 约定 |
| [session-and-events.md](session-and-events.md) | 会话与事件：会话编排、EventBus 解耦 UI 与核心逻辑 |
| [prompt-management.md](prompt-management.md) | 提示词管理：模板目录、链式结构、与存储结合 |
| [react-and-tool-calling.md](react-and-tool-calling.md) | ReAct 与工具调用：Thought-Action-Observation 循环、工具注册与调用 |
| [commit-conventions.md](commit-conventions.md) | 提交方式与 commit 信息习惯：Conventional Commits、type/scope、release 格式 |

## 使用方式

- 在新项目（如 CLI 智能体）中可将本目录整体复制或通过子模块引用。
- 单篇文档可独立阅读，按需采纳其中的模式与代码片段。
- 文档内尽量不依赖本项目专有名词，仅保留通用范式与示例。
