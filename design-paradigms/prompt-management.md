# 提示词管理范式

模板目录、链式结构与存储结合，与具体业务无关。

## 1. 模板目录与加载

- **目录约定**：集中放在如 `prompts/templates/`，按用途或角色命名文件（如 `assistant`、`expert`、`hackbot_security`）。管理器启动时扫描或显式注册，得到 `templates: Dict[str, str]`（名字 → 模板正文）。
- **格式**：模板为纯文本或 Markdown；若需变量，使用占位符（如 `{{name}}`）或约定格式，由调用方传入上下文后替换。
- **默认模板**：在代码里内联若干「默认」模板（如 assistant、expert、technical），保证无外部文件时也能运行；文件模板可覆盖默认。

## 2. 链式结构（Prompt Chain）

- **概念**：一个「链」由多段组成，每段可有名称、内容、顺序，用于组合系统提示、少样本、规则等。可用 Builder 模式构建链，再渲染成最终字符串。
- **存储**：若链需要持久化，可存数据库（如表 prompt_chains，字段：id、name、config/json、updated_at）；PromptManager 启动时从 DB 加载链到内存，并提供增删改查接口，与「文件模板」并存。
- **使用**：Agent 或 Planner 通过 `prompt_manager.get_chain(name)` 或 `get_template(name)` 获取内容，再注入变量、拼接用户输入后发给 LLM。

## 3. 与数据库结合

- **表设计**：链的元数据与内容（或引用）存 DB，便于多环境同步、版本与审计；大文本可存 blob 或外键到对象存储，按需。
- **加载顺序**：先加载内联默认 → 再加载目录下文件 → 再从 DB 加载链，后加载的可覆盖先前的同名项（若需要）。
- **依赖**：PromptManager 构造函数接受可选的 `db_manager`；无 DB 时仅用内存与文件，有 DB 时支持链的持久化。

## 4. 可复用要点小结

- 模板：目录 + 名字到正文的映射，支持默认内联与文件覆盖。
- 链：多段组合、Builder 构建、可持久化到 DB；管理器统一 get_chain / get_template。
- 变量替换与拼接在调用方或管理器内统一做，避免散落。
