# COMSOL Multiphysics Agent

一个基于 ReAct（Reasoning & Acting）架构的专业级智能 Agent，将自然语言描述的 COMSOL 建模需求自动转换为完整的 COMSOL Multiphysics 模型文件（.mph），支持从几何建模到物理场设置、网格划分、研究配置和求解的完整仿真流程。

## 功能特性

### 核心架构

- 🧠 **ReAct 架构**: 采用 Reasoning & Acting 模式，实现推理链路和执行链路的完整闭环
  - **推理链路**: 需求理解 → 步骤规划 → 验证 → 错误处理 → 迭代改进
  - **执行链路**: 几何建模 → 物理场设置 → 网格划分 → 研究配置 → 求解
  - **自动迭代**: 根据执行结果自动改进计划，确保模型质量

### Agent 组件

- 🤖 **Planner Agent**: 将自然语言解析为结构化 JSON，支持几何、物理场、研究类型规划
- ⚙️ **Executor Agent**: 自动生成 COMSOL Java API 代码或直接调用 API
- 👁️ **Observer**: 观察执行结果，验证模型状态
- 🔄 **Iteration Controller**: 控制迭代流程，根据观察结果改进计划

### 技术特性

- 🔧 **COMSOL 集成**: 直接执行代码并生成 .mph 模型文件
- 📐 **几何支持**: 矩形、圆形、椭圆等基础几何形状
- 🔬 **完整流程**: 支持几何、物理场、网格、研究、求解的完整建模流程
- 💾 **上下文管理**: 自动记录对话历史，生成摘要式记忆，提升解析准确性
- 🎯 **自定义别名**: 支持用户自定义命令别名，提高使用效率
- 🔄 **多 LLM 后端**: 支持 Dashscope (Qwen)、OpenAI、OpenAI 兼容服务、Ollama（本地/远程），灵活选择推理服务
- 🎛️ **混合 API 控制**: 简单操作直接调用 Java API，复杂操作生成代码执行

## 安装

### 1. 环境要求

- Python 3.8+
- COMSOL Multiphysics（已安装）
- Java JDK 8+（与 COMSOL 兼容）

### 2. 安装步骤

#### 方式一：从源码安装（开发模式，推荐使用 uv）

```bash
# 克隆项目
git clone <repository-url>
cd agent-for-comsol-multiphysics

# 使用 uv 安装依赖与可编辑安装（需先安装 uv: https://docs.astral.sh/uv/）
uv sync
# 验证
uv run comsol-agent --help
```

#### 方式二：构建并安装分发包

```bash
# 构建分发包
uv run python build.py
# 或使用脚本: ./scripts/build.sh (Linux/Mac) 或 scripts\build.bat (Windows)

# 安装分发包
uv pip install dist/agent-for-comsol-multiphysics-*.whl
```

详细安装说明请参考 [INSTALL.md](INSTALL.md)

### 3. 环境配置（必需）

安装后，**必须**配置以下环境变量：

1. **LLM_BACKEND** - LLM 后端类型（`deepseek`/`kimi`/`ollama`/`openai-compatible`，默认 `ollama`）
2. 根据选择的后端配置相应的 API Key 和 URL（见下方配置示例）
3. **COMSOL_JAR_PATH** - COMSOL JAR 文件路径或 plugins 目录
   - **COMSOL 6.3+**（推荐）：配置为 `plugins` 目录，程序会自动加载所有 jar 文件
   - **COMSOL 6.1及更早版本**：配置为单个 jar 文件路径
4. **JAVA_HOME** - 可选。不配置时优先使用系统环境变量；若仍无，首次使用 COMSOL 功能会自动下载内置 JDK 11 到项目 `runtime/java`
5. **JAVA_DOWNLOAD_MIRROR** - 可选。内置 JDK 下载镜像，国内加速可设为 `tsinghua`（清华 TUNA 镜像）
6. **MODEL_OUTPUT_DIR** - 模型输出目录（可选，默认为安装目录下的 `models`）

#### 配置方式

**方式一：使用环境变量**
```bash
# Linux/Mac (COMSOL 6.3+ 推荐使用 plugins 目录；JAVA_HOME 可选)
export DEEPSEEK_API_KEY="your_api_key"
export COMSOL_JAR_PATH="/opt/comsol63/multiphysics/plugins"
# export JAVA_HOME="/path/to/java"  # 不设则使用内置 JDK 11

# Windows (COMSOL 6.3+ 推荐使用 plugins 目录；JAVA_HOME 可选，不设则使用内置 JDK 11)
set DEEPSEEK_API_KEY=your_api_key
set COMSOL_JAR_PATH=C:\Program Files\COMSOL\COMSOL63\Multiphysics\plugins
rem set JAVA_HOME=C:\path\to\java
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

**使用 Ollama 后端（本地）：**
```env
LLM_BACKEND=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3
COMSOL_JAR_PATH=/path/to/comsol.jar
JAVA_HOME=/path/to/java
MODEL_OUTPUT_DIR=/path/to/output
```

**使用 Ollama 后端（远程）：**
```env
LLM_BACKEND=ollama
OLLAMA_URL=http://192.168.1.100:11434
OLLAMA_MODEL=llama3
COMSOL_JAR_PATH=/path/to/comsol.jar
JAVA_HOME=/path/to/java
MODEL_OUTPUT_DIR=/path/to/output
```

详细 LLM 后端配置说明请参考 [docs/llm-backends.md](docs/llm-backends.md)

### 4. 环境检查

运行诊断命令检查配置：
```bash
comsol-agent doctor
```

详细配置说明请参考 [INSTALL.md](INSTALL.md)

### 5. 环境就绪与自动化建模测试

环境已配置好后，建议按以下步骤确认并测试完整流程：

**第一步：环境诊断**

```bash
uv run comsol-agent doctor
```

- 若有**错误**（红色），按提示补齐 `.env` 或环境变量（如 `COMSOL_JAR_PATH`、当前 LLM 后端的 API Key）。
- 若 Java 已就绪（本机已装或已存在 `runtime/java`），可在 `.env` 中设置 `JAVA_SKIP_AUTO_DOWNLOAD=1`，避免再触发自动下载。

**第二步：测试自动化建模（一条命令生成模型）**

```bash
# 示例：从自然语言生成 .mph 模型（ReAct 架构，默认）
uv run comsol-agent run "创建一个宽1米、高0.5米的矩形" -o test_rect.mph
```

- 成功时会输出模型路径；模型文件在默认输出目录（如项目下的 `models/`）或 `-o` 指定位置。
- 也可先只做规划、不跑 COMSOL：`uv run comsol-agent plan "创建一个宽1米高0.5米的矩形"`，查看解析出的 JSON。

**第三步：交互式使用（可选）**

```bash
uv run comsol-agent
```

进入全终端 TUI 后，直接输入建模需求即可生成模型；输入 `/demo` 可跑内置示例。

## 使用方法

### 全终端交互模式（推荐）

直接运行以下命令即可进入**占据整个终端的交互界面**，无需子命令：

```bash
comsol-agent
```

- **默认模式**：在底部输入框中输入自然语言建模需求，直接生成 COMSOL 模型（等同 `run`）。
- **计划模式**：输入 `/plan` 切换为计划模式，下一句输入将仅解析为 JSON 计划（等同 `plan`）；输入 `/run` 切回默认模式。
- **退出**：输入 `/quit` 或 `/exit` 退出；也可按 `q`（若已绑定）。
- **斜杠命令**（输入后通过方向键选择或按提示操作）：
  - `/exec`：根据 JSON 计划创建模型或仅生成 Java 代码
  - `/demo`：运行演示示例
  - `/doctor`：环境诊断
  - `/context`：查看摘要 / 历史 / 统计 / 清除对话历史
  - `/backend`：选择 LLM 后端（DeepSeek / Kimi / Ollama / OpenAI 兼容中转）
  - `/output`：设置默认输出文件名
  - `/help`：显示斜杠命令帮助

脚本或非交互场景仍可使用子命令：`comsol-agent run "..."`、`comsol-agent plan "..."` 等。

### 命令行使用（子命令）

```bash
# 运行完整流程（使用 ReAct 架构，默认启用）
comsol-agent run "创建一个宽1米、高0.5米的矩形"

# 使用 ReAct 架构创建完整模型（几何+物理场+网格+研究+求解）
comsol-agent run "创建一个传热模型，包含一个矩形域，设置温度边界条件，进行稳态求解" --react

# 使用传统架构（仅几何建模）
comsol-agent run "创建一个矩形" --no-react

# 设置最大迭代次数
comsol-agent run "创建复杂模型" --max-iterations 20

# 仅解析自然语言（输出 JSON）
comsol-agent plan "创建一个矩形" -o plan.json

# 根据 JSON 计划创建模型
comsol-agent exec plan.json

# 上下文管理
comsol-agent context              # 查看上下文摘要
comsol-agent context --stats      # 查看统计信息
comsol-agent context --history    # 查看对话历史
comsol-agent context --clear      # 清除对话历史

# 演示功能
comsol-agent demo

# 环境诊断
comsol-agent doctor
```

### 调试模式（使用 main.py）

```bash
# 使用 ReAct 架构
python main.py --react "创建一个宽1米、高0.5米的矩形"

# 使用传统架构
python main.py --no-react "创建一个矩形"

# 交互模式（与 comsol-agent 无参数启动相同，进入全终端 TUI）
python main.py --interactive

# 指定输出文件
python main.py "创建模型" -o my_model.mph
```

### 自定义命令别名

用户可以自定义命令别名，提高使用效率。详细说明请参考 [CONTEXT.md](CONTEXT.md)。

**Linux/Mac 示例**（添加到 `~/.bashrc` 或 `~/.zshrc`）：
```bash
alias ca="comsol-agent"
alias carun="comsol-agent run"
```

**Windows 示例**（添加到 PowerShell 配置文件）：
```powershell
Set-Alias ca comsol-agent
function carun { comsol-agent run $args }
```

### Python 代码使用

#### 使用 ReAct 架构（推荐）

```python
from agent.react.react_agent import ReActAgent

# 创建 ReAct Agent
react_agent = ReActAgent(max_iterations=10)

# 运行完整流程（自动推理、执行、观察、迭代）
model_path = react_agent.run("创建一个宽1米、高0.5米的矩形")
print(f"模型已生成: {model_path}")
```

#### 使用传统架构

```python
from agent.planner.geometry_agent import GeometryAgent
from agent.executor.comsol_runner import COMSOLRunner

# 创建 Planner Agent
planner = GeometryAgent()
plan = planner.parse("在原点放置一个半径为0.3米的圆")

# 创建 COMSOL 模型
runner = COMSOLRunner()
model_path = runner.create_model_from_plan(plan)
print(f"模型已生成: {model_path}")
```

#### 使用 ReAct 组件

```python
from agent.react.reasoning_engine import ReasoningEngine
from agent.react.action_executor import ActionExecutor
from agent.react.observer import Observer
from agent.utils.llm import LLMClient

# 初始化组件
llm = LLMClient(backend="deepseek", api_key="your_key")
reasoning_engine = ReasoningEngine(llm)
action_executor = ActionExecutor()
observer = Observer()

# 理解需求并规划
plan = reasoning_engine.understand_and_plan("创建传热模型", "heat_model")

# 执行步骤
result = action_executor.execute(plan, plan.execution_path[0], {})

# 观察结果
observation = observer.observe(plan, plan.execution_path[0], result)
```

## 示例

查看 `examples/` 目录获取示例文件：
- `examples/nl/` - 自然语言输入示例
- `examples/geometry/` - JSON 格式示例
- `examples/outputs/` - 生成的模型文件

运行开发测试：
```bash
python scripts/dev_test.py
```

## 项目结构

```
agent-for-comsol-multiphysics/
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
│
├── docs/                         # 论文 & 架构
│   ├── architecture.md
│   ├── agent-design.md
│   ├── comsol-api-notes.md
│   └── thesis-outline.md
│
├── prompts/                      # Prompt = 核心资产
│   ├── planner/
│   │   ├── geometry_planner.txt
│   │   ├── physics_planner.txt
│   │   └── study_planner.txt
│   │
│   ├── executor/
│   │   └── java_codegen.txt
│   │
│   └── react/                    # ReAct Prompt 模板
│       ├── reasoning.txt
│       ├── planning.txt
│       └── validation.txt
│
├── schemas/                      # Agent 中枢
│   ├── __init__.py
│   ├── geometry.py
│   ├── physics.py
│   ├── study.py
│   └── task.py
│
├── agent/
│   ├── __init__.py
│   │
│   ├── react/                        # ReAct 架构核心
│   │   ├── __init__.py
│   │   ├── react_agent.py           # ReAct Agent 核心类
│   │   ├── reasoning_engine.py      # 推理引擎
│   │   ├── action_executor.py       # 行动执行器
│   │   ├── observer.py              # 观察器
│   │   └── iteration_controller.py  # 迭代控制器
│   │
│   ├── planner/
│   │   ├── __init__.py
│   │   ├── geometry_agent.py
│   │   ├── physics_agent.py
│   │   └── study_agent.py
│   │
│   ├── executor/
│   │   ├── __init__.py
│   │   ├── java_generator.py
│   │   ├── comsol_runner.py
│   │   ├── java_api_controller.py  # Java API 控制器
│   │   └── sandbox.py
│   │
│   └── utils/
│       ├── llm.py
│       ├── prompt_loader.py
│       ├── logger.py
│       ├── config.py
│       └── context_manager.py
│
├── java/                         # COMSOL Java API
│   ├── src/
│   │   └── main/
│   │       └── java/
│   │           └── com/
│   │               └── comsol/
│   │                   └── agent/
│   │                       ├── BaseModelBuilder.java
│   │                       ├── GeometryBuilder.java
│   │                       └── Main.java
│   │
│   ├── run.sh
│   ├── compile.sh
│   └── README.md
│
├── examples/                     # 毕设实验直接用
│   ├── geometry/
│   │   └── rectangle.json
│   │
│   ├── nl/
│   │   └── rectangle.txt
│   │
│   └── outputs/
│       └── rect.mph
│
├── scripts/
│   ├── run_agent.py
│   └── dev_test.py
│
└── main.py                        # 主启动程序（用于调试）
```

## 架构说明

### ReAct 架构工作流程

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

- **ReActAgent**: 协调推理和执行的主 Agent
- **ReasoningEngine**: 负责需求理解和步骤规划
- **ActionExecutor**: 执行具体的建模操作
- **Observer**: 观察执行结果并验证模型状态
- **IterationController**: 控制迭代流程，改进计划
- **JavaAPIController**: 混合模式控制 Java API 调用

详细架构说明请参考 [docs/architecture.md](docs/architecture.md) 和 [agent/ARCHITECTURE_PSEUDOCODE.md](agent/ARCHITECTURE_PSEUDOCODE.md)

## 开发

提交规范与架构范式见 [CONTRIBUTING.md](docs/CONTRIBUTING.md) 与 [design-paradigms/](docs/agent-design-skills/)。

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行 ReAct 架构测试
pytest tests/test_react.py -v
```

### 调试模式

使用 `main.py` 进行调试：

```bash
# 交互模式调试
python main.py --interactive

# 单次执行调试
python main.py --react "创建模型"
```

### 代码格式

```bash
black agent/ tests/ main.py
```

## 常见问题

### Q: COMSOL JAR 文件找不到？
A: 
- **COMSOL 6.3+版本**：配置为 `plugins` 目录，例如 `C:\Program Files\COMSOL\COMSOL63\Multiphysics\plugins`
- **COMSOL 6.1及更早版本**：配置为单个jar文件，例如 `安装目录/lib/win64/comsol.jar`

### Q: Java 环境错误？
A: 项目已集成 JDK 11，无需单独配置；若使用系统 Java，请确保 `JAVA_HOME` 指向正确 JDK 路径且与 COMSOL 兼容

### Q: API 调用失败？
A: 检查当前 LLM 后端对应的 API Key（如 DEEPSEEK_API_KEY、KIMI_API_KEY）是否已配置