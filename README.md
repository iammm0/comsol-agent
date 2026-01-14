# COMSOL Multiphysics Agent

一个智能 Agent，将自然语言描述的二维几何建模需求自动转换为 COMSOL Multiphysics 模型文件（.mph）。

## 功能特性

- 🤖 **Planner Agent**: 将自然语言解析为结构化 JSON
- ⚙️ **Executor Agent**: 自动生成 COMSOL Java API 代码
- 🔧 **COMSOL 集成**: 直接执行代码并生成 .mph 模型文件
- 📐 **基础几何支持**: 矩形、圆形、椭圆
- 💾 **上下文管理**: 自动记录对话历史，生成摘要式记忆，提升解析准确性
- 🎯 **自定义别名**: 支持用户自定义命令别名，提高使用效率
- 🔄 **多 LLM 后端**: 支持 Dashscope (Qwen)、OpenAI、OpenAI 兼容服务、Ollama（本地/远程），灵活选择推理服务

## 安装

### 1. 环境要求

- Python 3.8+
- COMSOL Multiphysics（已安装）
- Java JDK 8+（与 COMSOL 兼容）

### 2. 安装步骤

#### 方式一：从源码安装（开发模式）

```bash
# 克隆项目
git clone <repository-url>
cd agent-for-comsol-multiphysics

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖和包
pip install -r requirements.txt
pip install -e .
```

#### 方式二：构建并安装分发包

```bash
# 构建分发包
python build.py
# 或使用脚本: ./scripts/build.sh (Linux/Mac) 或 scripts\build.bat (Windows)

# 安装分发包
pip install dist/agent-for-comsol-multiphysics-*.whl
```

详细安装说明请参考 [INSTALL.md](INSTALL.md)

### 3. 环境配置（必需）

安装后，**必须**配置以下环境变量：

1. **LLM_BACKEND** - LLM 后端类型（`dashscope`/`openai`/`openai-compatible`/`ollama`，默认 `dashscope`）
2. 根据选择的后端配置相应的 API Key 和 URL（见下方配置示例）
3. **COMSOL_JAR_PATH** - COMSOL JAR 文件路径
4. **JAVA_HOME** - Java 安装路径
5. **MODEL_OUTPUT_DIR** - 模型输出目录（可选，默认为安装目录下的 `models`）

#### 配置方式

**方式一：使用环境变量**
```bash
# Linux/Mac
export DASHSCOPE_API_KEY="your_api_key"
export COMSOL_JAR_PATH="/path/to/comsol.jar"
export JAVA_HOME="/path/to/java"

# Windows
set DASHSCOPE_API_KEY=your_api_key
set COMSOL_JAR_PATH=C:\path\to\comsol.jar
set JAVA_HOME=C:\path\to\java
```

**方式二：使用 .env 文件（推荐）**

在项目根目录或用户主目录创建 `.env` 文件：

**使用 Dashscope (Qwen) 后端：**
```env
LLM_BACKEND=dashscope
DASHSCOPE_API_KEY=your_api_key
COMSOL_JAR_PATH=/path/to/comsol.jar
JAVA_HOME=/path/to/java
MODEL_OUTPUT_DIR=/path/to/output
```

**使用 OpenAI 官方 API：**
```env
LLM_BACKEND=openai
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-3.5-turbo
COMSOL_JAR_PATH=/path/to/comsol.jar
JAVA_HOME=/path/to/java
MODEL_OUTPUT_DIR=/path/to/output
```

**使用 OpenAI 兼容服务（第三方）：**
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

## 使用方法

### 命令行使用

```bash
# 运行完整流程（主入口，自动使用上下文记忆）
comsol-agent run "创建一个宽1米、高0.5米的矩形"

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
├── requirements.txt
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
│   └── executor/
│       └── java_codegen.txt
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
│   │   └── sandbox.py
│   │
│   └── utils/
│       ├── llm.py
│       ├── prompt_loader.py
│       ├── logger.py
│       └── config.py
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
└── scripts/
    ├── run_agent.py
    └── dev_test.py
```

## 开发

### 运行测试

```bash
pytest tests/
```

### 代码格式

```bash
black src/ tests/
```

## 常见问题

### Q: COMSOL JAR 文件找不到？
A: 检查 COMSOL 安装路径，通常在 `安装目录/lib/win64/comsol.jar`

### Q: Java 环境错误？
A: 确保 `JAVA_HOME` 指向正确的 JDK 路径，且版本与 COMSOL 兼容

### Q: API 调用失败？
A: 检查 `DASHSCOPE_API_KEY` 是否正确配置

## 许可证

MIT License
