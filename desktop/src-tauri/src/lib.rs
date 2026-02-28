mod bridge;

use bridge::{bridge_send, bridge_send_stream, bridge_abort, init_bridge, bundled_java_home_from_app, open_path, open_in_folder, BridgeState, BridgeStateInner};
use std::sync::Arc;
use tauri::Manager;
use tokio::sync::Mutex;

/// 应用窗口图标（使用 icons/icon.ico），由前端在加载后调用一次
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
            child: None,
            stream_pid: None,
            bundled_java_home: None,
        })))
        .invoke_handler(tauri::generate_handler![
            bridge_send,
            bridge_send_stream,
            bridge_abort,
            open_path,
            open_in_folder,
            apply_window_icon,
        ])
        .setup(|app| {
            let state = app.state::<BridgeState>().inner().clone();
            let java_home = bundled_java_home_from_app(app);
            let rt = tokio::runtime::Runtime::new().expect("create tokio runtime");
            match rt.block_on(init_bridge(java_home.clone())) {
                Ok(child) => {
                    let mut guard = state.as_ref().blocking_lock();
                    guard.bundled_java_home = java_home;
                    guard.child = Some(child);
                }
                Err(e) => {
                    eprintln!("Warning: Failed to initialize Python bridge: {}", e);
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
