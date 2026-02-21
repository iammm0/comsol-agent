"""全终端交互 TUI：Textual App，现代化深色主题、可滚动输出、底部输入、斜杠命令。"""
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, RichLog, Input, OptionList, Static
from textual.widgets.option_list import Option
from textual.screen import Screen
from textual.binding import Binding
from textual import work

from agent.actions import (
    do_run,
    do_plan,
    do_exec_from_file,
    do_demo,
    do_doctor,
    do_context_show,
    do_context_history,
    do_context_stats,
    do_context_clear,
)


@dataclass
class SessionState:
    """会话状态，供 do_run/do_plan 使用"""
    mode: str = "run"
    backend: Optional[str] = None
    output_default: Optional[str] = None
    use_react: bool = True
    no_context: bool = False


WELCOME = """[bold cyan]COMSOL Agent[/bold cyan] — 输入建模需求直接生成模型

[bright_black]• 直接输入[/bright_black] 自然语言 → 生成模型  [dim]|[/dim]  [bright_black]/plan[/bright_black] 计划模式 → JSON
• /context  /exec  /backend  /output  [dim]|[/dim]  [bright_black]/quit[/bright_black] 或 /exit 退出"""

HELP_TEXT = """
[bold cyan]命令[/bold cyan]
  /quit, /exit  退出
  /run          默认模式（自然语言 → 模型）
  /plan         计划模式（自然语言 → JSON）
  /exec         根据 JSON 计划创建模型或生成代码
  /demo         演示示例
  /doctor       环境诊断
  /context      查看或清除对话历史
  /backend      选择 LLM 后端
  /output       设置默认输出文件名
  /help         本帮助
"""


class ComsolTuiApp(App[None]):
    """COMSOL Agent 全终端交互 — 现代化深色主题"""
    CSS = """
    Screen {
        background: $surface;
    }
    Header {
        background: $primary 35%;
        color: $text;
        text-style: bold;
    }
    #output {
        height: 1fr;
        padding: 1 2;
        border: round $primary 40%;
        background: $panel;
        scrollbar-background: $surface;
        scrollbar-color: $primary 50%;
    }
    #input-area {
        height: auto;
        padding: 1 2 1 2;
        background: $surface;
        border-top: heavy $primary 25%;
    }
    Input {
        border: round $primary 60%;
        padding: 0 1;
        min-height: 1;
    }
    Input:focus {
        border: round $primary;
    }
    Footer {
        background: $primary 20%;
        color: $text-muted;
    }
    OptionList {
        padding: 1 2;
        border: round $primary 40%;
    }
    OptionList:focus > .option-list--highlight {
        background: $primary 35%;
    }
    Static {
        padding: 0 0 1 0;
    }
    """
    TITLE = "COMSOL Agent"
    SUB_TITLE = "默认模式"

    BINDINGS = [
        Binding("q", "quit", "退出", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.state = SessionState()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="output", markup=True, highlight=False, auto_scroll=True)
        yield Container(Input(placeholder=" 输入建模需求或斜杠命令，如 /help …", id="cmd"), id="input-area")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#output", RichLog).write(WELCOME)
        self.query_one("#cmd", Input).focus()

    def _update_subtitle(self) -> None:
        self.sub_title = "计划模式" if self.state.mode == "plan" else "默认模式"
        if self.state.backend:
            self.sub_title += f" · {self.state.backend}"

    def _write(self, text: str, success: bool = True) -> None:
        log = self.query_one("#output", RichLog)
        if success:
            log.write(f"[green]{text}[/green]")
        else:
            log.write(f"[red]{text}[/red]")

    def _handle_slash(self, line: str) -> bool:
        """处理斜杠命令，返回 True 表示已处理（不需再执行 run/plan）。"""
        line = line.strip().lower()
        if line in ("/quit", "/exit"):
            self.exit()
            return True
        if line == "/run":
            self.state.mode = "run"
            self._update_subtitle()
            self._write("已切换为默认模式（run）")
            return True
        if line == "/plan":
            self.state.mode = "plan"
            self._update_subtitle()
            self._write("已切换为计划模式（plan）")
            return True
        if line == "/help":
            self.query_one("#output", RichLog).write(HELP_TEXT)
            return True
        if line == "/demo":
            self._run_demo()
            return True
        if line == "/doctor":
            self._run_doctor()
            return True
        if line == "/context":
            self.push_screen(ContextMenuScreen())
            return True
        if line == "/backend":
            self.push_screen(BackendMenuScreen())
            return True
        if line == "/exec":
            self.push_screen(ExecMenuScreen(), self._on_exec_menu_done)
            return True
        if line == "/output":
            self.push_screen(OutputScreen())
            return True
        return False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = (event.value or "").strip()
        event.input.clear()
        if not value:
            return
        if value.startswith("/"):
            if self._handle_slash(value):
                return
            self._write(f"未知斜杠命令: {value}，输入 /help 查看帮助", success=False)
            return
        if self.state.mode == "plan":
            self._run_plan(value)
        else:
            self._run_run(value)

    @work(thread=True, exclusive=True)
    def _run_run(self, user_input: str) -> None:
        out = self.state.output_default
        ok, msg = do_run(
            user_input,
            output=out,
            use_react=self.state.use_react,
            no_context=self.state.no_context,
            backend=self.state.backend,
        )
        self.call_from_thread(self._write, msg, ok)

    @work(thread=True, exclusive=True)
    def _run_plan(self, user_input: str) -> None:
        ok, msg = do_plan(user_input)
        self.call_from_thread(self._write, msg, ok)

    @work(thread=True, exclusive=True)
    def _run_demo(self) -> None:
        ok, msg = do_demo()
        self.call_from_thread(self._write, msg, ok)

    @work(thread=True, exclusive=True)
    def _run_doctor(self) -> None:
        ok, msg = do_doctor()
        self.call_from_thread(self._write, msg, ok)

    def _on_exec_menu_done(self, code_only: bool) -> None:
        self.push_screen(ExecPathScreen(code_only=code_only))

    def action_quit(self) -> None:
        self.exit()


class ContextMenuScreen(Screen[Optional[str]]):
    """上下文子菜单：摘要/历史/统计/清除"""
    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]上下文[/bold cyan] — 选择操作", id="menu-title")
        yield OptionList(
            Option("查看摘要", id="show"),
            Option("查看历史", id="history"),
            Option("统计信息", id="stats"),
            Option("清除历史", id="clear"),
            id="opts",
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt = event.option.id
        if opt == "show":
            ok, msg = do_context_show()
        elif opt == "history":
            ok, msg = do_context_history(10)
        elif opt == "stats":
            ok, msg = do_context_stats()
        else:
            ok, msg = do_context_clear()
        app = self.app
        if isinstance(app, ComsolTuiApp):
            app._write(msg, ok)
        self.dismiss(None)


class BackendMenuScreen(Screen[Optional[str]]):
    """后端选择"""
    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]LLM 后端[/bold cyan] — 选择后端", id="menu-title")
        yield OptionList(
            Option("DeepSeek", id="deepseek"),
            Option("Kimi", id="kimi"),
            Option("Ollama", id="ollama"),
            Option("OpenAI 兼容中转", id="openai-compatible"),
            id="opts",
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        backend = event.option.id
        app = self.app
        if isinstance(app, ComsolTuiApp):
            app.state.backend = backend
            app._update_subtitle()
            app._write(f"已选择后端: {backend}")
        self.dismiss(backend)


class ExecMenuScreen(Screen[bool]):
    """执行方式：根据 JSON 创建模型 / 仅生成代码，dismiss 时传出 code_only"""

    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]执行方式[/bold cyan] — 选择操作", id="menu-title")
        yield OptionList(
            Option("根据 JSON 文件创建模型", id="run"),
            Option("仅生成 Java 代码", id="code"),
            id="opts",
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        code_only = event.option.id == "code"
        self.dismiss(code_only)


class ExecPathScreen(Screen[None]):
    """输入 JSON 计划文件路径"""
    BINDINGS = [Binding("escape", "cancel", "取消")]

    def __init__(self, code_only: bool = False) -> None:
        super().__init__()
        self.code_only = code_only

    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]JSON 计划文件[/bold cyan] — 输入路径", id="label")
        yield Input(placeholder="例如 plan.json", id="path")

    def on_mount(self) -> None:
        self.query_one("#path", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        path = Path((event.value or "").strip())
        if not path.exists():
            app = self.app
            if isinstance(app, ComsolTuiApp):
                app._write(f"文件不存在: {path}", success=False)
            self.dismiss()
            return
        ok, msg = do_exec_from_file(path, code_only=self.code_only)
        if isinstance(self.app, ComsolTuiApp):
            self.app._write(msg, ok)
        self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()


class OutputScreen(Screen[Optional[str]]):
    """设置默认输出文件名"""
    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]默认输出文件名[/bold cyan] — 不含路径", id="label")
        yield Input(placeholder="例如 model.mph", id="name")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        name = (event.value or "").strip()
        if isinstance(self.app, ComsolTuiApp):
            self.app.state.output_default = name if name else None
            self.app._write(f"默认输出已设为: {name or '（未设置）'}")
        self.dismiss(name)


def run_tui() -> None:
    """启动全终端 TUI（供 cli 无参数时调用）。"""
    app = ComsolTuiApp()
    app.run()

