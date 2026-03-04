mod bridge;

use bridge::{
    bridge_abort, bridge_init_status, bridge_send, bridge_send_stream, bundled_java_home_from_app,
    init_bridge, open_in_folder, open_path, BridgeState, BridgeStateInner,
};
use std::sync::Arc;
use tauri::Manager;
use tokio::sync::Mutex;

#[tauri::command]
fn apply_window_icon(window: tauri::WebviewWindow) {
    let icon = tauri::include_image!("icons/icon.ico");
    if let Err(e) = window.set_icon(icon) {
        eprintln!("Failed to set window icon: {}", e);
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(Arc::new(Mutex::new(BridgeStateInner {
            stdin: None,
            reader: None,
            child: None,
            child_pid: None,
            stream_active: false,
            bundled_java_home: None,
            init_error: None,
            stderr_buf: Arc::new(std::sync::Mutex::new(String::new())),
        })))
        .invoke_handler(tauri::generate_handler![
            bridge_send,
            bridge_send_stream,
            bridge_abort,
            bridge_init_status,
            open_path,
            open_in_folder,
            apply_window_icon,
        ])
        .setup(|app| {
            let state = app.state::<BridgeState>().inner().clone();
            let java_home = bundled_java_home_from_app(app);
            tauri::async_runtime::spawn(async move {
                match init_bridge(java_home.clone()).await {
                    Ok(handles) => {
                        let mut guard = state.lock().await;
                        guard.bundled_java_home = java_home;
                        guard.stdin = Some(handles.stdin);
                        guard.reader = Some(handles.reader);
                        guard.child = Some(handles.child);
                        guard.child_pid = Some(handles.pid);
                        guard.stderr_buf = handles.stderr_buf;
                        guard.init_error = None;
                    }
                    Err(e) => {
                        eprintln!("Warning: Failed to initialize Python bridge: {}", e);
                        let mut guard = state.lock().await;
                        guard.bundled_java_home = java_home;
                        guard.init_error = Some(e);
                    }
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
