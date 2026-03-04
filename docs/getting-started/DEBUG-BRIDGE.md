# 调试 Python Bridge

当桌面端出现 **「请求失败: Bridge process closed unexpectedly」** 时，表示 Python Bridge 子进程在流式请求过程中异常退出。可按下面方式显式调试。

**桌面端（Rust）会输出该报错的代码块**：见 [desktop/src-tauri/src/BRIDGE-ERROR-LOCATIONS.md](../../desktop/src-tauri/src/BRIDGE-ERROR-LOCATIONS.md)，便于在 PC 端桥接代码内逐块排查。

## 1. 开启 Bridge 调试模式（推荐）

设置环境变量 **`COMSOL_AGENT_BRIDGE_DEBUG=1`** 后启动桌面应用，Bridge 的 stderr 会输出到启动应用所在的终端，便于看到 Python 端的报错和堆栈。

**Windows（PowerShell，开发环境）：**

```powershell
$env:COMSOL_AGENT_BRIDGE_DEBUG = "1"
cd E:\sensorai\comsol-agent\desktop
npm run tauri dev
```

**Windows（CMD）：**

```cmd
set COMSOL_AGENT_BRIDGE_DEBUG=1
cd E:\sensorai\comsol-agent\desktop
npm run tauri dev
```

**Linux / macOS：**

```bash
export COMSOL_AGENT_BRIDGE_DEBUG=1
cd /path/to/comsol-agent/desktop
npm run tauri dev
```

效果：

- **Rust 端**：子进程的 stderr 不再被丢弃，会继承到当前终端，因此 Python 的调试输出与未捕获异常会显示在该终端。
- **Python 端**：在调试模式下会：
  - 向 **stderr** 和 **调试日志文件** 同时写入（每次写入后立即 flush，避免进程异常退出时丢失）
  - 启动时打印：`[bridge] 调试模式已开启，日志文件: <路径>`
  - 每行请求摘要：`[bridge] 收到请求: ...`
  - 任意异常时的完整 traceback
  - 设置全局 `excepthook`，未捕获异常也会写入上述位置

复现一次导致「Bridge process closed unexpectedly」的操作后，在终端或下述日志文件中查看报错即可定位问题。

### 若终端里仍没有任何报错

可能原因：从开始菜单/快捷方式启动（无控制台）、进程在写 stderr 前被结束、或异常发生在子线程。此时请查看 **Bridge 调试日志文件**（调试模式下每次启动都会写入该路径）：

| 平台   | 路径 |
|--------|------|
| Windows | `%TEMP%\comsol-agent-bridge-debug.log`（如 `C:\Users\<用户名>\AppData\Local\Temp\comsol-agent-bridge-debug.log`） |
| Linux/macOS | `$TMPDIR/comsol-agent-bridge-debug.log` 或 `/tmp/comsol-agent-bridge-debug.log` |

请先设置 `COMSOL_AGENT_BRIDGE_DEBUG=1` 并重启桌面应用（若从开始菜单运行，需在快捷方式或系统环境中设置该变量），复现问题后打开上述日志文件查看最后几行的 traceback。

### 若连日志文件都没有

说明 Bridge 进程很可能在写任何日志之前就退出了，常见有两种情况：

1. **Import 失败**（依赖缺失、Python 环境不对）  
   Bridge 启动时会**无条件**在日志里写一行 `Bridge process started` 以及当前工作目录和可执行路径；若 import 失败，会再写 `Import failed:` 和完整 traceback。请再次复现问题后查看 `%TEMP%\comsol-agent-bridge-debug.log`：
   - 若文件**存在**且含 `Import failed:` → 按其中的 traceback 修依赖或环境。
   - 若文件**存在**且只有 `Bridge process started` → 进程曾启动，但在后续逻辑中退出，可再设 `COMSOL_AGENT_BRIDGE_DEBUG=1` 以看到更多请求/异常日志。
   - 若文件**不存在** → 进程可能根本没跑到 Python 代码（例如未找到 bridge 可执行文件、或从错误的工作目录启动）。请从项目根目录在终端执行 `python cli.py tui-bridge`，看是否报错并是否生成上述日志文件。

2. **未从正确环境启动**  
   开发时请务必在**项目根目录**用 `npm run tauri dev` 启动桌面，这样 Bridge 会以 `python cli.py tui-bridge` 方式启动；若用安装包，需保证安装包内已包含 `comsol-agent-bridge-*.exe` 且 Tauri 能正确找到并启动它。

## 2. 手动运行 Bridge（管道调试）

若需要更底层地看 stdin/stdout 的 JSON 行，可在项目根目录手动启动 Bridge，用管道喂入请求（仅用于调试，不通过 Tauri 启动桌面）：

```bash
# 在项目根目录，激活 venv 后
python cli.py tui-bridge
```

此时 stdin 非 TTY，Bridge 会正常读入 JSON 行。可在另一终端用 echo 发送一行 JSON 测试，例如：

```bash
echo '{"cmd":"doctor"}' | python cli.py tui-bridge
```

注意：桌面应用运行时已经启动了一个 Bridge 进程，不要在同一项目目录同时再起一个 Bridge 做「管道调试」；若要手动管道调试，请先关闭桌面应用。

## 3. 常见原因简述

- **依赖缺失**：缺少 `jpype1`、LLM 相关包等，导致 import 或首次调用时崩溃。  
  解决：在项目根 `pip install -e ".[dev]"` 或按 [INSTALL.md](INSTALL.md) 安装依赖。
- **Java / COMSOL 未配置**：`JAVA_HOME` 错误或 COMSOL 未安装，执行到 Java 相关代码时崩溃。  
  解决：配置 `JAVA_HOME`，或使用桌面安装包内嵌的 JDK（安装包会设置 `COMSOL_AGENT_USE_BUNDLED_JAVA=1`）。
- **OOM 或超时**：模型或任务过大导致进程被系统杀掉或长时间无响应。  
  解决：看 stderr 是否有 MemoryError / 被 kill 的日志，或减小任务/模型规模。

开启 `COMSOL_AGENT_BRIDGE_DEBUG=1` 后，上述多数问题都会在终端或调试日志文件中看到具体异常和 traceback。
