# COMSOL Java API 官方文档链接

本文档集中记录 COMSOL Multiphysics Java API 的官方文档地址，便于团队与 LLM/RAG 检索。版本号（如 6.2、6.3、6.4）可按实际使用的 COMSOL 版本在 URL 中替换。

## 在线文档

| 用途 | 地址 | 说明 |
|------|------|------|
| **API 索引（按类/方法）** | https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/api/index-all.html | 按字母 A–Z 的 Java 类/方法索引；将 `6.3` 改为 `6.4` 等可切换版本 |
| **建模 / Java Shell 使用** | https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_ref_modeling.19.028.html | 在 Model Builder、App Builder、Model Manager 中交互使用 Java API |
| **模型管理器 API** | https://doc.comsol.com/6.2/doc/com.comsol.help.comsol/model_manager_ref_api.59.02.html | 模型管理器相关 API 入门与参考 |

## PDF 手册

| 文档 | 地址 | 说明 |
|------|------|------|
| **Programming Reference Manual** | https://cdn.comsol.com/doc/6.0.0.405/COMSOL_ProgrammingReferenceManual.pdf | 离线完整 API 参考；其他版本可在 [doc.comsol.com](https://doc.comsol.com) 或 [cdn.comsol.com](https://cdn.comsol.com) 查找 |
| **Application Programming Guide** | https://doc.comsol.com/6.0/doc/com.comsol.help.comsol/ApplicationProgrammingGuide.pdf | 应用开发与示例 |

## 学习与支持

- **Learning Center**：https://www.comsol.com/support/learning-center  
- **Support**：https://www.comsol.com/support  
- **Knowledge Base**：https://www.comsol.com/support/knowledgebase  

## 版本说明

- 在线文档根路径一般为 `https://doc.comsol.com/<版本>/doc/...`，例如 `6.2`、`6.3`、`6.4`。
- API 索引页的版本替换示例：`index-all.html` 所在路径中的数字即为文档版本。
- 本仓库当前主要参考 COMSOL 6.3+ 的 `plugins` 目录与 API 行为；开发时请以本机安装的 COMSOL 版本对应文档为准。

## 与本项目的关系

- Agent 生成或调用的 Java 代码遵循上述 API；提示词与 RAG 可引用本文档链接或 [comsol-api-notes.md](comsol-api-notes.md) 中的示例。
- 模型开发器、App 开发器、模型管理器三个模块分别对应建模、Application Builder 方法/界面、Model Manager 相关 API，详见 [comsol-modules-and-context.md](comsol-modules-and-context.md)。
