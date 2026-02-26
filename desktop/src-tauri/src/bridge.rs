use serde_json::Value;
use std::path::PathBuf;
use std::sync::Arc;
#[cfg(target_os = "windows")]
#[allow(unused_imports)]
use std::os::windows::process::CommandExt;
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Command, Child};
use tokio::sync::Mutex;

pub type BridgeState = Arc<Mutex<Option<Child>>>;

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

pub async fn init_bridge() -> Result<Child, String> {
    let root = find_project_root().ok_or("Cannot find project root (pyproject.toml)")?;
    let (cmd, args) = find_python_cmd(&root);

    let mut builder = Command::new(&cmd);
    builder
        .args(&args)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .current_dir(&root)
        .env("PYTHONIOENCODING", "utf-8");

    #[cfg(target_os = "windows")]
    {
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        builder.creation_flags(CREATE_NO_WINDOW);
    }

    let child = builder.spawn().map_err(|e| {
        format!(
            "Failed to start Python bridge ({} {}): {}",
            cmd,
            args.join(" "),
            e
        )
    })?;

    if child.stdin.is_none() || child.stdout.is_none() {
        return Err("Failed to capture stdin/stdout".to_string());
    }

    Ok(child)
}

#[tauri::command]
pub async fn bridge_send(
    state: tauri::State<'_, BridgeState>,
    cmd: String,
    payload: Value,
) -> Result<Value, String> {
    let mut guard = state.inner().as_ref().lock().await;
    let child = guard.as_mut().ok_or("Python bridge not initialized")?;

    let mut req = match payload.as_object() {
        Some(obj) => obj.clone(),
        None => serde_json::Map::new(),
    };
    req.insert("cmd".into(), Value::String(cmd));

    let line = serde_json::to_string(&Value::Object(req)).map_err(|e| e.to_string())?;
    let line_with_newline = format!("{}\n", line);

    let stdin = child.stdin.as_mut().ok_or("Stdin not available")?;
    stdin
        .write_all(line_with_newline.as_bytes())
        .await
        .map_err(|e| format!("Write to bridge failed: {}", e))?;
    stdin
        .flush()
        .await
        .map_err(|e| format!("Flush bridge failed: {}", e))?;

    let stdout = child.stdout.as_mut().ok_or("Stdout not available")?;
    let mut reader = BufReader::new(stdout);
    let mut resp_line = String::new();
    let bytes = reader
        .read_line(&mut resp_line)
        .await
        .map_err(|e| format!("Read from bridge failed: {}", e))?;

    if bytes == 0 {
        return Err("Empty response from bridge".to_string());
    }

    let trimmed = resp_line.trim();
    if trimmed.is_empty() {
        return Err("Empty response from bridge".to_string());
    }

    serde_json::from_str(trimmed).map_err(|e| format!("Invalid JSON response: {}", e))
}

#[tauri::command]
pub async fn bridge_send_stream(
    app: AppHandle,
    state: tauri::State<'_, BridgeState>,
    cmd: String,
    payload: Value,
) -> Result<Value, String> {
    let mut guard = state.inner().as_ref().lock().await;
    let child = guard.as_mut().ok_or("Python bridge not initialized")?;

    let mut req = match payload.as_object() {
        Some(obj) => obj.clone(),
        None => serde_json::Map::new(),
    };
    req.insert("cmd".into(), Value::String(cmd));

    let line = serde_json::to_string(&Value::Object(req)).map_err(|e| e.to_string())?;
    let line_with_newline = format!("{}\n", line);

    let stdin = child.stdin.as_mut().ok_or("Stdin not available")?;
    stdin
        .write_all(line_with_newline.as_bytes())
        .await
        .map_err(|e| format!("Write to bridge failed: {}", e))?;
    stdin
        .flush()
        .await
        .map_err(|e| format!("Flush bridge failed: {}", e))?;

    let stdout = child.stdout.as_mut().ok_or("Stdout not available")?;
    let mut reader = BufReader::new(stdout);

    loop {
        let mut resp_line = String::new();
        let bytes = reader
            .read_line(&mut resp_line)
            .await
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

/// 使用系统默认应用打开文件（如 .mph 用 COMSOL 打开）
#[tauri::command]
pub async fn open_path(path: String) -> Result<(), String> {
    let path = path.trim();
    if path.is_empty() {
        return Err("路径为空".to_string());
    }
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(["/C", "start", "", path])
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(path)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        std::process::Command::new("xdg-open")
            .arg(path)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 打开模型所在目录（文件管理器中打开该文件夹，不选中文件）
#[tauri::command]
pub async fn open_in_folder(path: String) -> Result<(), String> {
    let path = path.trim();
    if path.is_empty() {
        return Err("路径为空".to_string());
    }
    let path_buf = std::path::PathBuf::from(path);
    if !path_buf.exists() {
        return Err("文件或目录不存在".to_string());
    }
    let dir = if path_buf.is_dir() {
        path_buf
    } else {
        path_buf
            .parent()
            .map(|p| p.to_path_buf())
            .unwrap_or(path_buf)
    };
    let abs = dir.canonicalize().map_err(|e| e.to_string())?;
    let dir_str = abs.to_string_lossy().to_string();

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer")
            .arg(&dir_str)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(&dir_str)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        std::process::Command::new("xdg-open")
            .arg(&dir_str)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}
