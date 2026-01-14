# Agent 设计文档

## Planner Agent 设计

### GeometryAgent

**职责**：将自然语言描述的几何建模需求解析为结构化 JSON

**工作流程**：
1. 接收用户自然语言输入
2. 加载 geometry_planner.txt Prompt 模板
3. 调用 LLM API（Qwen）
4. 从响应中提取 JSON
5. 验证并返回 GeometryPlan 对象

**关键方法**：
- `parse(user_input: str) -> GeometryPlan` - 解析自然语言

### Executor Agent 设计

#### JavaGenerator

**职责**：根据 GeometryPlan 生成 COMSOL Java API 代码

**工作流程**：
1. 接收 GeometryPlan 对象
2. 加载 java_codegen.txt Prompt 模板
3. 格式化 Prompt（可选，也可直接生成）
4. 返回 Java 代码字符串

**关键方法**：
- `generate_from_plan(plan: GeometryPlan) -> str` - 生成 Java 代码

#### COMSOLRunner

**职责**：直接调用 COMSOL Java API 创建模型

**工作流程**：
1. 启动 JVM 并加载 COMSOL JAR
2. 创建 COMSOL 模型对象
3. 根据 GeometryPlan 创建几何形状
4. 构建几何
5. 保存为 .mph 文件

**关键方法**：
- `create_model_from_plan(plan: GeometryPlan) -> Path` - 创建并保存模型

## Agent 协作模式

```
用户输入
  ↓
GeometryAgent.parse()
  ↓
GeometryPlan (JSON)
  ↓
COMSOLRunner.create_model_from_plan()
  ↓
.mph 文件
```

## 错误处理

- LLM 调用失败：重试机制（最多 3 次）
- JSON 解析失败：多种提取策略
- COMSOL API 错误：异常捕获和日志记录
- 配置错误：启动时验证

## 未来扩展

- PhysicsAgent：物理场建模
- StudyAgent：研究类型规划
- Sandbox：安全代码执行
