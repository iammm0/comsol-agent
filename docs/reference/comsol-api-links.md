# COMSOL Java API 官方文档链接

本文档集中记录 **COMSOL Multiphysics 6.3** Java API 的官方文档地址，便于团队与 LLM/RAG 检索。本项目当前面向 **6.3** 开发与验证，因此以下链接默认固定为 6.3 版本。

## 在线文档

| 用途 | 地址 | 说明 |
|------|------|------|
| **API 索引（按类/方法）** | https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/api/index-all.html | 按字母 A–Z 的 Java 类/方法索引 |
| **建模 / Java Shell 使用** | https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_ref_modeling.19.028.html | 在 Model Builder、App Builder、Model Manager 中交互使用 Java API |
| **模型管理器 API 入门** | https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/model_manager_ref_api.61.02.html | Model Manager API 的入门说明 |
| **模型管理器 API 访问** | https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/model_manager_ref_api.61.03.html | Accessing the Model Manager API |

## PDF 手册

| 文档 | 地址 | 说明 |
|------|------|------|
| **Application Programming Guide** | https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/ApplicationProgrammingGuide.pdf | 应用开发与示例 |
| **Application Programming Guide：Java Shell** | https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/application_programming_guide.15.13.html | Java Shell 与 Data Viewer 窗口 |

## 学习与支持

- **Learning Center**：https://www.comsol.com/support/learning-center  
- **Support**：https://www.comsol.com/support  
- **Knowledge Base**：https://www.comsol.com/support/knowledgebase  

## 版本说明

- 在线文档根路径一般为 `https://doc.comsol.com/<版本>/doc/...`，本仓库默认采用 `6.3`。
- API 索引页的版本号在路径中直接体现，例如 `.../6.3/doc/...`。
- 本仓库当前主要参考 **COMSOL Multiphysics 6.3** 的 `plugins` 目录与 API 行为；开发时请优先使用本机 6.3 安装对应文档。

## 与本项目的关系

- Agent 生成或调用的 Java 代码遵循上述 API；提示词与 RAG 可引用本文档链接或 [comsol-api-notes.md](comsol-api-notes.md) 中的示例。
- 模型开发器、App 开发器、模型管理器三个模块分别对应建模、Application Builder 方法/界面、Model Manager 相关 API，详见 [comsol-modules-and-context.md](comsol-modules-and-context.md)。
