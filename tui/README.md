# COMSOL Agent TUI（OpenTUI + Solid.js）

基于 [@opentui/core](https://opentui.com/) 与 [@opentui/solid](https://opentui.com/docs/bindings/solid) 的全终端交互界面，与 Python 后端通过 **TUI 桥接**（stdin/stdout JSON 行）通信。

## 要求

- [Bun](https://bun.sh/)（当前 OpenTUI 仅支持 Bun）
- 项目 Python 环境已配置（见仓库根目录 README），或已安装 `comsol-agent` 且 `comsol-agent` 在 PATH 中

## 运行

**统一启动命令（推荐）**：在仓库根目录执行

```bash
uv run comsol-agent
```

无参数即启动本 TUI（需已安装 Bun）。亦可进入 `tui/` 后执行：

```bash
bun install
bun run start
```

## 桥接

TUI 会启动子进程运行 Python 桥接（`comsol-agent tui-bridge` 或 `python cli.py tui-bridge`），通过 stdin 接收 JSON 行、调用 `agent.actions`、经 stdout 返回 `{"ok": bool, "message": string}`。桥接实现见 `agent/tui_bridge.py`。

## 功能

主界面：标题、可滚动输出、底部输入、底部栏；斜杠命令：/run、/plan、/help、/demo、/doctor、/context、/backend、/exec、/output、/quit；上下文/后端/执行/输出等菜单与结果展示。
