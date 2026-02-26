use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter};

pub struct BridgeInner {
    stdin: ChildStdin,
    reader: BufReader<ChildStdout>,
    _child: Child,
}

pub struct BridgeState(pub Mutex<Option<BridgeInner>>);

fn find_project_root() -> Option<PathBuf> {
    if let Ok(mut dir) = std::env::current_dir() {
        for _ in 0..10 {
            if dir.join("pyproject.toml").exists() {
                return Some(dir);
            }
            if !dir.pop() {
                break;
            }
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(mut dir) = exe.parent().map(|p| p.to_path_buf()) {
            for _ in 0..10 {
                if dir.join("pyproject.toml").exists() {
                    return Some(dir);
                }
                if !dir.pop() {
                    break;
                }
            }
        }
    }
    None
}

fn find_python_cmd(root: &PathBuf) -> (String, Vec<String>) {
    let cli_path = root.join("cli.py");
    let cli_str = cli_path.to_string_lossy().to_string();

    #[cfg(target_os = "windows")]
    let venv_python = root.join(".venv").join("Scripts").join("python.exe");
    #[cfg(not(target_os = "windows"))]
    let venv_python = root.join(".venv").join("bin").join("python3");

    if venv_python.exists() {
        return (
            venv_python.to_string_lossy().to_string(),
            vec![cli_str, "tui-bridge".to_string()],
        );
    }

    #[cfg(target_os = "windows")]
    {
        (
            "py".to_string(),
            vec!["-3".to_string(), cli_str, "tui-bridge".to_string()],
        )
    }
    #[cfg(not(target_os = "windows"))]
    {
        (
            "python3".to_string(),
            vec![cli_str, "tui-bridge".to_string()],
        )
    }
}

pub fn init_bridge() -> Result<BridgeInner, String> {
    let root = find_project_root().ok_or("Cannot find project root (pyproject.toml)")?;
    let (cmd, args) = find_python_cmd(&root);

    let mut builder = Command::new(&cmd);
    builder
        .args(&args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .current_dir(&root)
        .env("PYTHONIOENCODING", "utf-8");

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        builder.creation_flags(CREATE_NO_WINDOW);
    }

    let mut child = builder.spawn().map_err(|e| {
        format!(
            "Failed to start Python bridge ({} {}): {}",
            cmd,
            args.join(" "),
            e
        )
    })?;

    let stdin = child.stdin.take().ok_or("Failed to capture stdin")?;
    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;

    Ok(BridgeInner {
        stdin,
        reader: BufReader::new(stdout),
        _child: child,
    })
}

#[tauri::command]
pub fn bridge_send(
    state: tauri::State<'_, BridgeState>,
    cmd: String,
    payload: Value,
) -> Result<Value, String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    let bridge = guard.as_mut().ok_or("Python bridge not initialized")?;

    let mut req = match payload.as_object() {
        Some(obj) => obj.clone(),
        None => serde_json::Map::new(),
    };
    req.insert("cmd".into(), Value::String(cmd));

    let line = serde_json::to_string(&Value::Object(req)).map_err(|e| e.to_string())?;
    writeln!(bridge.stdin, "{}", line).map_err(|e| format!("Write to bridge failed: {}", e))?;
    bridge
        .stdin
        .flush()
        .map_err(|e| format!("Flush bridge failed: {}", e))?;

    let mut resp_line = String::new();
    bridge
        .reader
        .read_line(&mut resp_line)
        .map_err(|e| format!("Read from bridge failed: {}", e))?;

    if resp_line.trim().is_empty() {
        return Err("Empty response from bridge".to_string());
    }

    serde_json::from_str(resp_line.trim()).map_err(|e| format!("Invalid JSON response: {}", e))
}

#[tauri::command]
pub fn bridge_send_stream(
    app: AppHandle,
    state: tauri::State<'_, BridgeState>,
    cmd: String,
    payload: Value,
) -> Result<Value, String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    let bridge = guard.as_mut().ok_or("Python bridge not initialized")?;

    let mut req = match payload.as_object() {
        Some(obj) => obj.clone(),
        None => serde_json::Map::new(),
    };
    req.insert("cmd".into(), Value::String(cmd));

    let line = serde_json::to_string(&Value::Object(req)).map_err(|e| e.to_string())?;
    writeln!(bridge.stdin, "{}", line).map_err(|e| format!("Write to bridge failed: {}", e))?;
    bridge
        .stdin
        .flush()
        .map_err(|e| format!("Flush bridge failed: {}", e))?;

    loop {
        let mut resp_line = String::new();
        let bytes = bridge
            .reader
            .read_line(&mut resp_line)
            .map_err(|e| format!("Read from bridge failed: {}", e))?;

        if bytes == 0 {
            return Err("Bridge process closed unexpectedly".to_string());
        }

        let trimmed = resp_line.trim();
        if trimmed.is_empty() {
            continue;
        }

        let parsed: Value =
            serde_json::from_str(trimmed).map_err(|e| format!("Invalid JSON: {}", e))?;

        let is_event = parsed.get("_event").and_then(|v| v.as_bool()) == Some(true);
        if is_event {
            let _ = app.emit("bridge-event", &parsed);
        } else {
            return Ok(parsed);
        }
    }
}
