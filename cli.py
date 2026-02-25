"""CLI 入口：无参数启动 TUI；tui-bridge 供 TUI 前端子进程调用。"""
import shutil
import subprocess
import sys
from pathlib import Path


def _project_root() -> Path:
    """项目根目录：源码运行时为含 pyproject.toml 的目录，pip 安装后为当前工作目录。"""
    p = Path(__file__).resolve().parent
    if (p / "pyproject.toml").exists():
        return p
    return Path.cwd()


def _launch_tui(root: Path) -> None:
    """启动 TS TUI（bun run start）。"""
    tui_dir = root / "tui"
    if not (tui_dir / "package.json").exists():
        print("错误: 未找到 tui 项目（tui/package.json），请从仓库根目录运行。", file=sys.stderr)
        sys.exit(1)
    if not shutil.which("bun"):
        print("错误: 未检测到 Bun，交互 TUI 需要 Bun。请安装后重试: https://bun.sh", file=sys.stderr)
        sys.exit(1)
    try:
        subprocess.run(
            ["bun", "run", "start"],
            cwd=tui_dir,
            check=False,
        )
    except Exception as e:
        print(f"TUI 启动失败: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """入口：无参数或 --help 启动 TUI；tui-bridge 调用桥接；其它打印用法并退出。"""
    root = _project_root()
    args = sys.argv[1:]

    if not args or (len(args) == 1 and args[0] in ("--help", "-h", "--interactive", "-i")):
        if args and args[0] in ("--help", "-h"):
            print("Usage: comsol-agent  或  comsol-agent tui-bridge")
            print("  无参数启动全终端 TUI；tui-bridge 供 TUI 内部调用，勿直接使用。")
        _launch_tui(root)
        return

    if args[0] == "tui-bridge":
        from dotenv import load_dotenv
        from agent.utils.java_runtime import ensure_java_home_from_venv

        load_dotenv(root / ".env")
        ensure_java_home_from_venv(root)
        from agent.tui_bridge import main as bridge_main
        bridge_main()
        return

    print("Usage: comsol-agent  或  comsol-agent tui-bridge", file=sys.stderr)
    print("  无参数启动全终端 TUI；run/plan/exec 等请在 TUI 内使用。", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
