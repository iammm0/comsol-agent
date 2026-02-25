# COMSOL Multiphysics Agent

基于 ReAct（Reasoning & Acting）架构的智能 Agent，将自然语言描述的 COMSOL 建模需求自动转换为完整的 COMSOL Multiphysics 模型文件（.mph），支持从几何建模到物理场设置、网格划分、研究配置和求解的完整仿真流程。

## 功能特性

### 核心架构

- **ReAct 架构**：采用 Reasoning & Acting 模式，实现推理链路和执行链路的完整闭环
  - **推理链路**：需求理解、步骤规划、验证、错误处理、迭代改进
  - **执行链路**：几何建模、物理场设置、网格划分、研究配置、求解
  - **自动迭代**：根据执行结果自动改进计划，确保模型质量

### Agent 组件

- **Planner Agent**：将自然语言解析为结构化 JSON，支持几何、物理场、研究类型规划
- **Executor Agent**：自动生成 COMSOL Java API 代码或直接调用 API
- **Observer**：观察执行结果，验证模型状态
- **Iteration Controller**：控制迭代流程，根据观察结果改进计划

### 技术特性

- **COMSOL 集成**：直接执行代码并生成 .mph 模型文件
- **几何支持**：矩形、圆形、椭圆等基础几何形状
- **完整流程**：支持几何、物理场、网格、研究、求解的完整建模流程
- **上下文管理**：自动记录对话历史，生成摘要式记忆，提升解析准确性
- **自定义别名**：支持用户自定义命令别名
- **多 LLM 后端**：支持 Dashscope (Qwen)、OpenAI、OpenAI 兼容服务、Ollama（本地/远程）
- **混合 API 控制**：简单操作直接调用 Java API，复杂操作生成代码执行

## 安装

### 1. 环境要求

- Python 3.8+
- COMSOL Multiphysics（已安装）
- Java JDK 8+（与 COMSOL 兼容）

### 2. 安装步骤

#### 方式一：从源码安装（推荐使用 uv）

```bash
# 克隆项目
git clone <repository-url>
cd comsol-agent

# 使用 uv 安装依赖与可编辑安装（需先安装 uv: https://docs.astral.sh/uv/）
uv sync
# 验证
uv run comsol-agent
```

#### 方式二：构建并安装分发包

```bash
# 构建分发包
uv run python build.py
# 或使用脚本: ./scripts/build.sh (Linux/Mac) 或 scripts\build.bat (Windows)

# 安装分发包
uv pip install dist/agent-for-comsol-multiphysics-*.whl
```

详细安装说明请参考 [docs/getting-started/INSTALL.md](docs/getting-started/INSTALL.md)

### 3. 环境配置（必需）

安装后，**必须**配置以下环境变量：

1. **LLM_BACKEND**：LLM 后端类型（如 `deepseek`、`kimi`、`ollama`、`openai-compatible`，默认 `ollama`）
2. 根据选择的后端配置相应的 API Key 和 URL（见下方配置示例）
3. **COMSOL_JAR_PATH**：COMSOL JAR 文件路径或 plugins 目录
   - **COMSOL 6.3+**（推荐）：配置为 `plugins` 目录，程序会自动加载所有 jar 文件
   - **COMSOL 6.1 及更早**：配置为单个 jar 文件路径
4. **JAVA_HOME**：可选。不配置时优先使用系统环境变量；若无，首次使用 COMSOL 功能会自动下载内置 JDK 11 到项目 `runtime/java`
5. **JAVA_DOWNLOAD_MIRROR**：可选。内置 JDK 下载镜像，国内可设为 `tsinghua`（清华 TUNA 镜像）
6. **MODEL_OUTPUT_DIR**：模型输出目录（可选，默认为 **comsol-agent 根目录下的 `models`**，该目录为唯一且首要的模型存放位置；项目根目录上一级的 `models` 不再使用）

#### 配置方式

**方式一：使用环境变量**

```bash
# Linux/Mac (COMSOL 6.3+ 推荐使用 plugins 目录)
export DEEPSEEK_API_KEY="your_api_key"
export COMSOL_JAR_PATH="/opt/comsol63/multiphysics/plugins"

# Windows
set DEEPSEEK_API_KEY=your_api_key
set COMSOL_JAR_PATH=C:\Program Files\COMSOL\COMSOL63\Multiphysics\plugins
```

**方式二：使用 .env 文件（推荐）**

在项目根目录或用户主目录创建 `.env` 文件：

**使用 DeepSeek：**
```env
LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=your_api_key
COMSOL_JAR_PATH=/opt/comsol63/multiphysics/plugins
JAVA_HOME=/path/to/java
MODEL_OUTPUT_DIR=/path/to/output
```

**使用 Kimi（Moonshot）：**
```env
LLM_BACKEND=kimi
KIMI_API_KEY=your_api_key
COMSOL_JAR_PATH=/path/to/comsol.jar
JAVA_HOME=/path/to/java
MODEL_OUTPUT_DIR=/path/to/output
```

**使用符合 OpenAI 规范的中转 API：**
```env
LLM_BACKEND=openai-compatible
OPENAI_COMPATIBLE_API_KEY=your_api_key
OPENAI_COMPATIBLE_BASE_URL=https://api.example.com/v1
OPENAI_COMPATIBLE_MODEL=your-model-name
COMSOL_JAR_PATH=/path/to/comsol.jar
JAVA_HOME=/path/to/java
MODEL_OUTPUT_DIR=/path/to/output
```

**使用 Ollama（本地）：**
```env
LLM_BACKEND=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3
COMSOL_JAR_PATH=/path/to/comsol.jar
JAVA_HOME=/path/to/java
MODEL_OUTPUT_DIR=/path/to/output
```

**使用 Ollama（远程）：**
```env
LLM_BACKEND=ollama
OLLAMA_URL=http://192.168.1.100:11434
OLLAMA_MODEL=llama3
COMSOL_JAR_PATH=/path/to/comsol.jar
JAVA_HOME=/path/to/java
MODEL_OUTPUT_DIR=/path/to/output
```

详细 LLM 后端配置请参考 [docs/getting-started/llm-backends.md](docs/getting-started/llm-backends.md)

### 4. 环境检查

在 TUI 内输入 `/doctor` 可进行环境诊断。详见 [docs/getting-started/CONFIG.md](docs/getting-started/CONFIG.md)。

### 5. 环境就绪与测试

**第一步：启动 TUI**

```bash
uv run comsol-agent
```

无参数执行即进入全终端 TUI（需安装 [Bun](https://bun.sh/)）。若有环境错误，按 TUI 内提示或使用 `/doctor` 查看诊断。

**第二步：在 TUI 中测试**

在 TUI 底部输入自然语言建模需求（如「创建一个宽1米、高0.5米的矩形」）即可生成模型；输入 `/demo` 可运行内置示例。详见 [tui/README.md](tui/README.md)。

## 使用方法

### 全终端交互模式（推荐）

```bash
uv run comsol-agent
```

无参数启动即进入 **OpenTUI + Solid.js** TUI（需安装 [Bun](https://bun.sh/)）。

- **默认模式**：在底部输入框输入自然语言建模需求，直接生成 COMSOL 模型（等同 `run`）
- **计划模式**：输入 `/plan` 切换为计划模式，下一句输入仅解析为 JSON（等同 `plan`）；输入 `/run` 切回默认模式
- **退出**：输入 `/quit` 或 `/exit`
- **斜杠命令**：`/exec`（根据 JSON 创建模型或生成 Java 代码）、`/demo`（演示）、`/doctor`（环境诊断）、`/context`（摘要/历史/统计/清除）、`/backend`（选择 LLM 后端）、`/output`（设置默认输出文件名）、`/help`（帮助）

详见 [docs/getting-started/CONTEXT.md](docs/getting-started/CONTEXT.md)。例如 **Linux/Mac** 可设 `alias ca="comsol-agent"`；**Windows** 可设 `Set-Alias ca comsol-agent`。

### Python 代码使用

#### ReAct 架构（推荐）

```python
from agent.react.react_agent import ReActAgent

react_agent = ReActAgent(max_iterations=10)
model_path = react_agent.run("创建一个宽1米、高0.5米的矩形")
print(f"模型已生成: {model_path}")
```

#### 传统架构

```python
from agent.planner.geometry_agent import GeometryAgent
from agent.executor.comsol_runner import COMSOLRunner

planner = GeometryAgent()
plan = planner.parse("在原点放置一个半径为0.3米的圆")

runner = COMSOLRunner()
model_path = runner.create_model_from_plan(plan)
print(f"模型已生成: {model_path}")
```

#### ReAct 组件

```python
from agent.react.reasoning_engine import ReasoningEngine
from agent.react.action_executor import ActionExecutor
from agent.react.observer import Observer
from agent.utils.llm import LLMClient

llm = LLMClient(backend="deepseek", api_key="your_key")
reasoning_engine = ReasoningEngine(llm)
action_executor = ActionExecutor()
observer = Observer()

plan = reasoning_engine.understand_and_plan("创建传热模型", "heat_model")
result = action_executor.execute(plan, plan.execution_path[0], {})
observation = observer.observe(plan, plan.execution_path[0], result)
```

更多示例与 TUI 内用法见 [docs/getting-started/EXAMPLE.md](docs/getting-started/EXAMPLE.md)。开发测试：

```bash
python scripts/dev_test.py
```

## 项目结构

```
comsol-agent/
├── README.md, pyproject.toml, uv.lock, env.example, main.py
├── docs/           # 文档（索引见 [docs/README.md](docs/README.md)）
├── prompts/        # 提示词模板（planner / executor / react）
├── schemas/        # 数据模型（geometry, physics, study, task）
├── agent/          # 主流程包（目录说明见 [agent/README.md](agent/README.md)）
├── java/           # COMSOL Java API 源码与脚本
├── scripts/        # 构建与测试脚本
└── tests/          # 单元测试
```

## 架构说明

### ReAct 工作流程

```
用户输入（自然语言）
    ↓
[Think] 推理引擎：理解需求、规划步骤、验证计划
    ↓
[Act] 行动执行器：执行建模操作（几何/物理场/网格/研究）
    ↓
[Observe] 观察器：检查执行结果、验证模型状态
    ↓
[Iterate] 迭代控制器：根据观察结果改进计划
    ↓
完整的 .mph 模型文件
```

### 核心组件

- **ReActAgent**：协调推理与执行的主 Agent
- **ReasoningEngine**：需求理解与步骤规划
- **ActionExecutor**：具体建模操作执行
- **Observer**：观察执行结果并验证模型状态
- **IterationController**：控制迭代与计划改进
- **JavaAPIController**：混合模式控制 Java API 调用

详细架构见 [docs/architecture/architecture.md](docs/architecture/architecture.md) 与 [java/API_ARCHITECTURE_PSEUDOCODE.md](java/API_ARCHITECTURE_PSEUDOCODE.md)。

## 开发

提交规范与设计范式见 [docs/project/CONTRIBUTING.md](docs/project/CONTRIBUTING.md) 与 [docs/agent-design-skills/](docs/agent-design-skills/)。

### 运行测试

```bash
pytest tests/
pytest tests/test_react.py -v
```

### 调试

```bash
uv run comsol-agent
# 或
python main.py
python main.py --interactive
```

### 代码格式

```bash
black agent/ tests/ main.py
```

## 常见问题

**Q: COMSOL JAR 找不到？**  
A: COMSOL 6.3+ 请配置为 `plugins` 目录（如 `C:\Program Files\COMSOL\COMSOL63\Multiphysics\plugins`）；6.1 及更早版本配置为单个 jar（如 `安装目录/lib/win64/comsol.jar`）。

**Q: Java 环境报错？**  
A: 项目可自动使用内置 JDK 11；若用系统 Java，请确保 `JAVA_HOME` 指向与 COMSOL 兼容的 JDK。

**Q: API 调用失败？**  
A: 检查当前 LLM 后端对应的 API Key（如 DEEPSEEK_API_KEY、KIMI_API_KEY）是否已在 `.env` 或环境变量中配置。
