# Bridge「process closed unexpectedly」相关代码位置

用于定位「请求失败: Bridge process closed unexpectedly」时，需要查看或修改的代码。

---

## 1. 错误产生位置（Rust）

**文件**: `desktop/src-tauri/src/bridge.rs`  
**位置**: 约 **298–307 行**（`bridge_send_stream` 内）

```rust
let bytes = reader.read_line(&mut resp_line).await...;
if bytes == 0 {
    break Err("Bridge process closed unexpectedly".to_string());  // <-- 用户看到的错误
}
```

**含义**: 从 Bridge 子进程的 stdout 读一行时读到 **EOF**（0 字节），说明子进程已退出且未再写数据。

**可做调整**:
- 保持此处逻辑不变即可；真正要保证的是 Python 端在退出前尽量写出一行最终响应。
- 若希望错误信息更易排查，可在此处将错误文案改为提示「请设置 COMSOL_AGENT_BRIDGE_DEBUG=1 并查看 %TEMP%\\comsol-agent-bridge-debug.log」的说明（可选）。

---

## 2. 必须保证「先写最终响应再退出」的位置（Python）

**文件**: `agent/run/tui_bridge.py`

### 2.1 主循环：唯一可能「未写响应就退出」的出口

**位置**: 约 **299–318 行**（`main()` 里 `for line in sys.stdin` 的 `try/except`）

```python
try:
    _handle(req)
except Exception as e:   # <-- 只捕获 Exception；BaseException（如 SystemExit/KeyboardInterrupt）会直接退出，不写 _reply
    ...
    _reply(False, str(e))
```

**问题**: 若 `_handle(req)` 或其中调用的 `do_run` 等抛出 **BaseException**（例如 `SystemExit`、`KeyboardInterrupt`），这里不会捕获，进程会直接退出，**不会** 调用 `_reply()`，Rust 端就会看到 stdout 关闭并报「Bridge process closed unexpectedly」。

**建议调整**: 改为捕获 **BaseException**，在退出前仍调用一次 `_reply(False, ...)`，再 re-raise，这样至少会写出一行最终 JSON，减少「无响应就关闭」的情况（见下方具体修改）。

### 2.2 「run」命令的处理

**位置**: 约 **120–138 行**（`_handle()` 里 `if cmd == "run":` 的 `try/except`）

```python
try:
    ok, msg = do_run(...)
    _reply(ok, msg)
except Exception as e:
    _emit_event(Event(type=EventType.ERROR, ...))
    _reply(False, str(e))
return
```

**含义**:  
- 正常时由 `do_run` 返回后 `_reply(ok, msg)` 写最终一行。  
- `do_run` 抛 `Exception` 时会被这里接住并 `_reply(False, str(e))`，协议上正确。  
- 若 `do_run` 或其底层（如 jpype、LLM 客户端）抛出 **非 Exception 的 BaseException**，会一路冒泡到 2.1 的 `main()`；若 2.1 只捕获 `Exception`，就会未写响应就退出。

因此 **2.1 的修改是当前最值得做的一处**，保证绝大多数「异常退出」前都有一行最终响应。

---

## 3. 可能触发「进程提前退出」的调用链（便于排查）

- 前端发 `run` → **bridge_send_stream**（Rust）→ 写 stdin → 读 stdout。
- Python: **main()** 读一行 → **\_handle(req)** → **do_run()**（`agent/run/actions.py`）→ **get_agent("core").run()**（ReActAgent.run）→ LLM / COMSOL（jpype）等。

若进程在以下情况退出且未先写最终 `_reply`，就会触发「Bridge process closed unexpectedly」：

- **Import 失败**: 在进入 `main()` 前就退出（已有早期日志与 Import 捕获，见 `tui_bridge.py` 顶部）。
- **未捕获的 BaseException**: 在 2.1 改为捕获 BaseException 并先 `_reply` 再 re-raise 可缓解。
- **进程被外部终止**: 如 OOM、taskkill、崩溃（如 jpype 段错误），无法在 Python 里完全避免，只能靠日志（COMSOL_AGENT_BRIDGE_DEBUG + 早期日志）定位。

---

## 4. 建议的具体修改（仅一处）

**文件**: `agent/run/tui_bridge.py`  
**位置**: `main()` 中处理 `_handle(req)` 的 `except`（约 314–318 行）

**当前**:
```python
except Exception as e:
    ...
    _reply(False, str(e))
```

**建议**:
```python
except BaseException as e:
    if _bridge_debug():
        _debug_log("".join(traceback.format_exception(type(e), e, e.__traceback__)))
    _reply(False, str(e))
    raise
```

这样即使发生 `SystemExit`、`KeyboardInterrupt` 等，也会先写出一行 `{"ok": false, "message": "..."}` 再退出，Rust 端就不会误报「Bridge process closed unexpectedly」（除非进程被强杀或崩溃）。
