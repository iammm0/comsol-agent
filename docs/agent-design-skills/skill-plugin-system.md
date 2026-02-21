# 技能/插件系统范式

基于 Markdown 的技能加载、清单解析与按需注入，与具体业务无关。

## 1. 技能目录约定

- 每个技能一个目录，目录内至少包含 `SKILL.md`。
- 可选：`scripts/`（可执行脚本）、`references/` 或 `references/`（参考文档）、`assets/`（二进制或静态资源）。
- 加载器只认「目录 + SKILL.md」，其他目录可选扫描。

## 2. SKILL.md 与 Frontmatter

- **格式**：YAML frontmatter + Markdown 正文。用正则 `^---\n(.*?)\n---\n(.*)$`（DOTALL）可一次拆出 frontmatter 与正文。
- **清单字段建议**：`name`、`description`（必填）、`version`、`author`、`tags`、`triggers`、`prerequisites`。description 用于发现与注入时的匹配。
- **正文**：即「技能说明」内容，注入到系统提示或上下文时直接拼接。

## 3. 加载器职责

- 扫描若干技能根目录（如 `["./skills"]`），对每个子目录查找 `SKILL.md`。
- 解析 frontmatter → 得到清单（dataclass 或 Pydantic）；正文 → 作为 instructions。
- 可选：同时加载同目录下 `scripts/`、`references/`、`assets/` 的路径或内容，放入 Skill 对象，便于按名引用。
- 结果以 `name -> Skill` 的字典缓存，提供 `get_skill(name)`、`get_skills_by_tag(tag)`、`get_skills_by_triggers(query)`、`list_skills()`。

## 4. 按需注入

- **触发匹配**：根据用户 query 与技能的 `triggers`、`tags` 做简单匹配（如关键词 in query），可带权重（trigger 加权高于 tag），取 Top-K 个技能。
- **注入位置**：在调用 LLM 前，将选中技能的 instructions 拼接到系统提示词末尾，或作为单独「技能上下文」块，并打上明确分隔标记（如 `=== RELEVANT SKILLS ===`），避免与主提示混淆。
- **生命周期**：可在「处理前」注入、在「处理后」记录本轮使用了哪些技能，便于日志与统计；不必在每次请求时重新加载所有技能文件。

## 5. 与智能体集成

- 提供「集成器」：在 Agent 的 `before_process(query, system_prompt)` 中调用注入器，返回增强后的 system_prompt；`after_process` 可选记录使用的技能。
- 通过函数扩展 Agent（如 `agent._enhance_prompt_with_skills = lambda q: injector.inject(q, agent.system_prompt)`），而不必改基类，便于在现有 CLI/API 中挂载。

## 6. 可复用要点小结

- 技能 = 目录 + SKILL.md（YAML frontmatter + Markdown）。
- 清单字段：name、description、version、tags、triggers 等。
- 加载器：多目录扫描、解析、缓存；按 name/tag/trigger 查询。
- 注入器：按 query 匹配技能、Top-K、拼接到系统提示或上下文块。
- 与 Agent 解耦：before/after 钩子或函数扩展，不侵入核心 process 逻辑。
