use serde_json::Value;
use std::path::PathBuf;
use std::sync::Arc;
#[cfg(target_os = "windows")]
#[allow(unused_imports)]
use std::os::windows::process::CommandExt;
use tauri::{AppHandle, Emitter, Manager};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin, ChildStdout, Command};
use tokio::sync::Mutex;

pub struct BridgeStateInner {
    pub stdin: Option<ChildStdin>,
    pub reader: Option<BufReader<ChildStdout>>,
    pub child: Option<Child>,
    pub child_pid: Option<u32>,
    pub stream_active: bool,
    pub init_error: Option<String>,
}

pub type BridgeState = Arc<Mutex<BridgeStateInner>>;

const HANDSHAKE_TIMEOUT_SECS: u64 = 20;

fn find_workspace_root() -> Option<PathBuf> {
    if let Ok(root) = std::env::var("MPH_AGENT_ROOT") {
        let path = PathBuf::from(root);
        if path.join("package.json").exists() {
            return Some(path);
        }
    }

    if let Ok(mut dir) = std::env::current_dir() {
        for _ in 0..10 {
            if dir.join("package.json").exists() && dir.join("apps").exists() {
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
                if dir.join("package.json").exists() && dir.join("apps").exists() {
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

fn find_resource_root(app: Option<&AppHandle>) -> Option<PathBuf> {
    if let Ok(path) = std::env::var("MPH_AGENT_RESOURCE_ROOT") {
        let value = PathBuf::from(path);
        if value.exists()
            && (value.join("sidecar").exists()
                || value.join("skills").exists()
                || value.join("prompts").exists())
        {
            return Some(value);
        }
    }
    if let Some(handle) = app {
        if let Ok(path) = handle.path().resource_dir() {
            if path.exists()
                && (path.join("sidecar").exists()
                    || path.join("skills").exists()
                    || path.join("prompts").exists())
            {
                return Some(path);
            }
        }
    }
    None
}

fn resolve_runtime_root(app: Option<&AppHandle>, workspace_root: Option<&PathBuf>) -> Option<PathBuf> {
    if let Ok(path) = std::env::var("MPH_AGENT_ROOT") {
        return Some(PathBuf::from(path));
    }
    if let Some(root) = workspace_root {
        return Some(root.clone());
    }
    if let Some(handle) = app {
        if let Ok(path) = handle.path().app_data_dir() {
            return Some(path);
        }
    }
    std::env::current_dir().ok()
}

fn resolve_node_binary(resource_root: Option<&PathBuf>) -> String {
    if let Ok(path) = std::env::var("MPH_AGENT_NODE_BIN") {
        let bin = PathBuf::from(path);
        if bin.exists() {
            return bin.to_string_lossy().to_string();
        }
    }

    if let Some(resource_root) = resource_root {
        let candidates: Vec<PathBuf> = if cfg!(target_os = "windows") {
            vec![
                resource_root.join("runtime").join("node").join("node.exe"),
                resource_root
                    .join("runtime")
                    .join("node")
                    .join("bin")
                    .join("node.exe"),
            ]
        } else {
            vec![
                resource_root
                    .join("runtime")
                    .join("node")
                    .join("bin")
                    .join("node"),
                resource_root.join("runtime").join("node").join("node"),
            ]
        };
        if let Some(path) = candidates.into_iter().find(|item| item.exists()) {
            return path.to_string_lossy().to_string();
        }
    }

    if cfg!(target_os = "windows") {
        "node.exe".to_string()
    } else {
        "node".to_string()
    }
}

fn sidecar_cmd(
    workspace_root: Option<&PathBuf>,
    resource_root: Option<&PathBuf>,
) -> Result<(String, Vec<String>), String> {
    let node = resolve_node_binary(resource_root);

    if let Ok(entry) = std::env::var("MPH_AGENT_SIDECAR_ENTRY") {
        let path = PathBuf::from(entry);
        if path.exists() {
            return Ok((node, vec![path.to_string_lossy().to_string()]));
        }
    }

    if let Some(resource_root) = resource_root {
        let bundled_entry = resource_root.join("sidecar").join("index.js");
        if bundled_entry.exists() {
            return Ok((node, vec![bundled_entry.to_string_lossy().to_string()]));
        }
    }

    if let Some(root) = workspace_root {
        let dist_entry = root
            .join("apps")
            .join("agent-sidecar")
            .join("dist")
            .join("index.js");
        if dist_entry.exists() {
            return Ok((node, vec![dist_entry.to_string_lossy().to_string()]));
        }

        let src_entry = root
            .join("apps")
            .join("agent-sidecar")
            .join("src")
            .join("index.ts");
        if src_entry.exists() {
            return Ok((
                node,
                vec![
                    "--experimental-strip-types".to_string(),
                    src_entry.to_string_lossy().to_string(),
                ],
            ));
        }
    }

    Err("Agent sidecar entry not found".to_string())
}

pub struct BridgeHandles {
    pub stdin: ChildStdin,
    pub reader: BufReader<ChildStdout>,
    pub child: Child,
    pub pid: u32,
}

async fn wait_for_handshake(reader: &mut BufReader<ChildStdout>) -> Result<(), String> {
    let mut line = String::new();
    let bytes = reader
        .read_line(&mut line)
        .await
        .map_err(|error| format!("Failed to read sidecar handshake: {}", error))?;
    if bytes == 0 {
        return Err("Sidecar exited before handshake".to_string());
    }

    let parsed: Value =
        serde_json::from_str(line.trim()).map_err(|error| format!("Invalid handshake JSON: {}", error))?;
    if parsed.get("_ready").and_then(|value| value.as_bool()) == Some(true) {
        Ok(())
    } else {
        Err(format!("Unexpected handshake payload: {}", line.trim()))
    }
}

pub async fn init_sidecar(app: Option<&AppHandle>) -> Result<BridgeHandles, String> {
    let workspace_root = find_workspace_root();
    let resource_root = find_resource_root(app);
    let runtime_root = resolve_runtime_root(app, workspace_root.as_ref())
        .ok_or("Unable to resolve runtime root")?;
    std::fs::create_dir_all(&runtime_root)
        .map_err(|error| format!("Failed to create runtime root {}: {}", runtime_root.display(), error))?;
    let (cmd, args) = sidecar_cmd(workspace_root.as_ref(), resource_root.as_ref())?;

    let mut builder = Command::new(&cmd);
    builder
        .args(&args)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .current_dir(&runtime_root)
        .env("MPH_AGENT_ROOT", runtime_root.to_string_lossy().to_string());

    if let Some(root) = resource_root {
        builder.env("MPH_AGENT_RESOURCE_ROOT", root.to_string_lossy().to_string());
    }

    #[cfg(target_os = "windows")]
    {
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        builder.creation_flags(CREATE_NO_WINDOW);
    }

    let mut child = builder
        .spawn()
        .map_err(|error| format!("Failed to spawn sidecar ({} {}): {}", cmd, args.join(" "), error))?;

    let pid = child.id().unwrap_or(0);
    let stdin = child.stdin.take().ok_or("Failed to capture sidecar stdin")?;
    let stdout = child.stdout.take().ok_or("Failed to capture sidecar stdout")?;
    let stderr = child.stderr.take();

    if let Some(stderr_pipe) = stderr {
        tokio::spawn(async move {
            let mut stderr_reader = BufReader::new(stderr_pipe);
            let mut line = String::new();
            loop {
                line.clear();
                match stderr_reader.read_line(&mut line).await {
                    Ok(0) => break,
                    Ok(_) => eprint!("[agent-sidecar] {}", line),
                    Err(_) => break,
                }
            }
        });
    }

    let mut reader = BufReader::new(stdout);
    match tokio::time::timeout(
        std::time::Duration::from_secs(HANDSHAKE_TIMEOUT_SECS),
        wait_for_handshake(&mut reader),
    )
    .await
    {
        Ok(Ok(())) => Ok(BridgeHandles {
            stdin,
            reader,
            child,
            pid,
        }),
        Ok(Err(error)) => {
            let _ = child.kill().await;
            Err(error)
        }
        Err(_) => {
            let _ = child.kill().await;
            Err(format!(
                "Sidecar handshake timed out after {}s",
                HANDSHAKE_TIMEOUT_SECS
            ))
        }
    }
}

async fn restart_sidecar(state: &BridgeState, app: Option<&AppHandle>) {
    match init_sidecar(app).await {
        Ok(handles) => {
            let mut guard = state.lock().await;
            guard.stdin = Some(handles.stdin);
            guard.reader = Some(handles.reader);
            guard.child = Some(handles.child);
            guard.child_pid = Some(handles.pid);
            guard.init_error = None;
        }
        Err(error) => {
            let mut guard = state.lock().await;
            guard.init_error = Some(error);
            guard.stdin = None;
            guard.reader = None;
            guard.child = None;
            guard.child_pid = None;
        }
    }
}

#[tauri::command]
pub async fn bridge_send(
    app: AppHandle,
    state: tauri::State<'_, BridgeState>,
    request: Value,
) -> Result<Value, String> {
    let (mut stdin, mut reader) = {
        let mut guard = state.inner().lock().await;
        let stdin = guard.stdin.take().ok_or("Bridge not initialized")?;
        let reader = guard.reader.take().ok_or("Bridge not initialized")?;
        (stdin, reader)
    };

    let line = serde_json::to_string(&request).map_err(|error| error.to_string())?;
    stdin
        .write_all(format!("{}\n", line).as_bytes())
        .await
        .map_err(|error| format!("Failed writing sidecar stdin: {}", error))?;
    stdin
        .flush()
        .await
        .map_err(|error| format!("Failed flushing sidecar stdin: {}", error))?;

    let mut response_line = String::new();
    let bytes = reader
        .read_line(&mut response_line)
        .await
        .map_err(|error| format!("Failed reading sidecar stdout: {}", error))?;
    if bytes == 0 {
        restart_sidecar(state.inner(), Some(&app)).await;
        return Err("Sidecar EOF".to_string());
    }

    let parsed: Value =
        serde_json::from_str(response_line.trim()).map_err(|error| format!("Invalid JSON: {}", error))?;

    {
        let mut guard = state.inner().lock().await;
        guard.stdin = Some(stdin);
        guard.reader = Some(reader);
    }

    Ok(parsed)
}

#[tauri::command]
pub async fn bridge_send_stream(
    app: AppHandle,
    state: tauri::State<'_, BridgeState>,
    request: Value,
) -> Result<Value, String> {
    let (mut stdin, mut reader) = {
        let mut guard = state.inner().lock().await;
        let stdin = guard.stdin.take().ok_or("Bridge not initialized")?;
        let reader = guard.reader.take().ok_or("Bridge not initialized")?;
        guard.stream_active = true;
        (stdin, reader)
    };

    let line = serde_json::to_string(&request).map_err(|error| error.to_string())?;
    stdin
        .write_all(format!("{}\n", line).as_bytes())
        .await
        .map_err(|error| format!("Failed writing sidecar stdin: {}", error))?;
    stdin
        .flush()
        .await
        .map_err(|error| format!("Failed flushing sidecar stdin: {}", error))?;

    let result = loop {
        let mut response_line = String::new();
        let bytes = reader
            .read_line(&mut response_line)
            .await
            .map_err(|error| format!("Failed reading sidecar stdout: {}", error))?;
        if bytes == 0 {
            break Err("Sidecar EOF".to_string());
        }
        let trimmed = response_line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let parsed: Value = serde_json::from_str(trimmed)
            .map_err(|error| format!("Invalid JSON: {} | {}", error, trimmed))?;

        if parsed.get("_event").and_then(|value| value.as_bool()) == Some(true) {
            let _ = app.emit("bridge-event", &parsed);
            continue;
        }
        break Ok(parsed);
    };

    {
        let mut guard = state.inner().lock().await;
        guard.stream_active = false;
        if result.is_ok() {
            guard.stdin = Some(stdin);
            guard.reader = Some(reader);
        } else {
            guard.stdin = None;
            guard.reader = None;
            guard.child = None;
            guard.child_pid = None;
            drop(guard);
            restart_sidecar(state.inner(), Some(&app)).await;
        }
    }

    result
}

#[tauri::command]
pub async fn bridge_abort(
    app: AppHandle,
    state: tauri::State<'_, BridgeState>,
) -> Result<(), String> {
    {
        let mut guard = state.inner().lock().await;
        guard.stdin = None;
        guard.reader = None;
        guard.stream_active = false;
        if let Some(mut child) = guard.child.take() {
            let _ = child.kill().await;
        }
        guard.child_pid = None;
    }
    restart_sidecar(state.inner(), Some(&app)).await;
    let guard = state.inner().lock().await;
    if let Some(error) = &guard.init_error {
        Err(error.clone())
    } else {
        Ok(())
    }
}

#[tauri::command]
pub async fn bridge_init_status(
    state: tauri::State<'_, BridgeState>,
) -> Result<serde_json::Value, String> {
    let guard = state.inner().lock().await;
    let ready = guard.stdin.is_some() && guard.reader.is_some();
    Ok(serde_json::json!({
        "ready": ready,
        "error": guard.init_error
    }))
}

#[tauri::command]
pub async fn open_path(path: String) -> Result<(), String> {
    let path = path.trim();
    if path.is_empty() {
        return Err("Path is empty".to_string());
    }
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(["/C", "start", "", path])
            .spawn()
            .map_err(|error| error.to_string())?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(path)
            .spawn()
            .map_err(|error| error.to_string())?;
    }
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        std::process::Command::new("xdg-open")
            .arg(path)
            .spawn()
            .map_err(|error| error.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub async fn open_in_folder(path: String) -> Result<(), String> {
    let path = path.trim();
    if path.is_empty() {
        return Err("Path is empty".to_string());
    }
    let path_buf = std::path::PathBuf::from(path);
    if !path_buf.exists() {
        return Err("Path not found".to_string());
    }
    let folder = if path_buf.is_dir() {
        path_buf
    } else {
        path_buf
            .parent()
            .map(|item| item.to_path_buf())
            .unwrap_or(path_buf)
    };
    let folder = folder.canonicalize().map_err(|error| error.to_string())?;
    let folder_str = folder.to_string_lossy().to_string();

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer")
            .arg(folder_str)
            .spawn()
            .map_err(|error| error.to_string())?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(folder_str)
            .spawn()
            .map_err(|error| error.to_string())?;
    }
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        std::process::Command::new("xdg-open")
            .arg(folder_str)
            .spawn()
            .map_err(|error| error.to_string())?;
    }
    Ok(())
}
