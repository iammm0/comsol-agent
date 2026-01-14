# 安装和使用指南

## 打包和安装

### 1. 构建分发包

#### 方式一：使用 Python 脚本
```bash
python build.py
```

#### 方式二：使用 shell 脚本（Linux/Mac）
```bash
chmod +x scripts/build.sh
./scripts/build.sh
```

#### 方式三：使用批处理脚本（Windows）
```cmd
scripts\build.bat
```

#### 方式四：直接使用 build 命令
```bash
python -m pip install --upgrade build wheel
python -m build
```

### 2. 安装分发包

```bash
# 从 wheel 文件安装
pip install dist/agent-for-comsol-multiphysics-*.whl

# 或从源码安装（开发模式）
pip install -e .
```

### 3. 验证安装

```bash
comsol-agent --help
```

## 环境配置

安装后，**必须**配置以下环境变量：

### 必需配置

1. **DASHSCOPE_API_KEY** - 通义千问 API Key
   ```bash
   # Linux/Mac
   export DASHSCOPE_API_KEY="your_api_key_here"
   
   # Windows
   set DASHSCOPE_API_KEY=your_api_key_here
   ```

2. **COMSOL_JAR_PATH** - COMSOL JAR 文件路径或plugins目录
   ```bash
   # Linux/Mac (COMSOL 6.3+ 推荐使用plugins目录)
   export COMSOL_JAR_PATH="/opt/comsol63/multiphysics/plugins"
   
   # Windows (COMSOL 6.3+ 推荐使用plugins目录)
   set COMSOL_JAR_PATH=C:\Program Files\COMSOL\COMSOL63\Multiphysics\plugins
   
   # 也可以使用单个jar文件（COMSOL 6.1及更早版本）
   export COMSOL_JAR_PATH="/path/to/comsol.jar"
   ```
   
   **注意**：
   - COMSOL 6.3+ 版本推荐配置为 `plugins` 目录，程序会自动加载所有jar文件
   - COMSOL 6.1 及更早版本需要配置为单个jar文件路径

3. **JAVA_HOME** - Java 安装路径
   ```bash
   # Linux/Mac
   export JAVA_HOME="/usr/lib/jvm/java-11-openjdk"
   
   # Windows
   set JAVA_HOME=C:\Program Files\Java\jdk-17
   ```

### 可选配置

4. **MODEL_OUTPUT_DIR** - 模型输出目录（默认为安装目录下的 `models` 文件夹）
   ```bash
   # Linux/Mac
   export MODEL_OUTPUT_DIR="/path/to/output"
   
   # Windows
   set MODEL_OUTPUT_DIR=C:\path\to\output
   ```

### 使用 .env 文件（推荐）

在项目根目录或用户主目录创建 `.env` 文件：

```env
DASHSCOPE_API_KEY=your_api_key_here
COMSOL_JAR_PATH=/path/to/comsol.jar
JAVA_HOME=/usr/lib/jvm/java-11-openjdk
MODEL_OUTPUT_DIR=/path/to/output
```

## 环境检查

安装和配置完成后，运行诊断命令检查环境：

```bash
comsol-agent doctor
```

如果所有检查通过，会显示：
```
✅ 环境检查通过
```

如果有问题，会显示详细的错误信息。

## 使用

### 基本使用

```bash
# 运行完整流程
comsol-agent run "创建一个宽1米、高0.5米的矩形"

# 仅解析自然语言（输出 JSON）
comsol-agent plan "创建一个矩形" -o plan.json

# 根据 JSON 计划创建模型
comsol-agent exec plan.json

# 演示功能
comsol-agent demo

# 环境诊断
comsol-agent doctor
```

### 跳过环境检查

如果确定环境已配置正确，可以跳过启动时的环境检查：

```bash
comsol-agent run --skip-check "创建一个矩形"
```

## 故障排除

### 问题 1: 找不到 comsol-agent 命令

**解决方案**：
- 确保已正确安装：`pip install dist/agent-for-comsol-multiphysics-*.whl`
- 检查 Python 环境：`which python` 或 `where python`
- 重新安装：`pip uninstall agent-for-comsol-multiphysics && pip install dist/agent-for-comsol-multiphysics-*.whl`

### 问题 2: 环境变量未生效

**解决方案**：
- 使用 `.env` 文件（推荐）
- 确保环境变量在正确的 shell 中设置
- 重启终端或重新加载配置

### 问题 3: COMSOL JAR 文件找不到

**解决方案**：
- **COMSOL 6.3+ 版本**（推荐）：
  - Windows: `C:\Program Files\COMSOL\COMSOL63\Multiphysics\plugins`
  - Linux: `/opt/comsol63/multiphysics/plugins`
  - Mac: `/Applications/COMSOL63/Multiphysics/plugins`
  - 配置为plugins目录，程序会自动加载所有jar文件
- **COMSOL 6.1 及更早版本**：
  - Windows: `C:\Program Files\COMSOL\COMSOL61\Multiphysics\lib\win64\comsol.jar`
  - Linux: `/opt/comsol61/multiphysics/lib/glnxa64/comsol.jar`
  - Mac: `/Applications/COMSOL61/Multiphysics/lib/darwin64/comsol.jar`

### 问题 4: Java 环境错误

**解决方案**：
- 确保安装了 JDK（不是 JRE）
- 检查 JAVA_HOME 指向正确的 JDK 路径
- 确保 Java 版本与 COMSOL 兼容（通常 JDK 8-17）

## 开发模式安装

如果要在开发模式下安装（修改代码后立即生效）：

```bash
pip install -e .
```

这样安装后，代码修改会立即反映到已安装的包中。
