# 架构设计文档

## 系统架构

```
用户输入（自然语言）
    ↓
Planner Agent（解析为结构化 JSON）
    ↓
Executor Agent（生成 Java 代码 / 直接调用 COMSOL API）
    ↓
COMSOL Multiphysics（执行并生成 .mph 文件）
```

## 核心组件

### 1. Schemas（数据结构）
- `schemas/geometry.py` - 几何建模数据结构
- `schemas/physics.py` - 物理场数据结构
- `schemas/study.py` - 研究类型数据结构
- `schemas/task.py` - 完整任务数据结构

### 2. Planner Agents
- `agent/planner/geometry_agent.py` - 几何建模 Planner
- `agent/planner/physics_agent.py` - 物理场 Planner（预留）
- `agent/planner/study_agent.py` - 研究类型 Planner（预留）

### 3. Executor Agents
- `agent/executor/java_generator.py` - Java 代码生成器
- `agent/executor/comsol_runner.py` - COMSOL API 运行器
- `agent/executor/sandbox.py` - 代码沙箱（预留）

### 4. Utils（工具模块）
- `agent/utils/llm.py` - LLM 客户端封装
- `agent/utils/prompt_loader.py` - Prompt 模板加载器
- `agent/utils/logger.py` - 日志工具
- `agent/utils/config.py` - 配置管理

### 5. Prompts（Prompt 模板）
- `prompts/planner/geometry_planner.txt` - 几何建模 Prompt
- `prompts/planner/physics_planner.txt` - 物理场 Prompt
- `prompts/planner/study_planner.txt` - 研究类型 Prompt
- `prompts/executor/java_codegen.txt` - Java 代码生成 Prompt

## 数据流

1. **输入阶段**：用户提供自然语言描述
2. **规划阶段**：Planner Agent 使用 LLM 解析为结构化 JSON
3. **执行阶段**：Executor Agent 根据 JSON 生成代码或直接调用 API
4. **输出阶段**：生成 .mph 模型文件

## 技术栈

- **Python 3.8+**
- **Qwen API** (Dashscope) - LLM 服务
- **jpype1** - Java 互操作
- **Pydantic** - 数据验证
- **COMSOL Java API** - COMSOL 模型操作

## 扩展性

- 支持添加新的几何形状类型
- 支持添加物理场建模
- 支持添加研究类型
- 支持自定义 Prompt 模板
