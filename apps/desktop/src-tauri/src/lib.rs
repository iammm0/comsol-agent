mod bridge;

use bridge::{
    bridge_abort, bridge_init_status, bridge_send, bridge_send_stream, init_sidecar, open_in_folder,
    open_path, BridgeState, BridgeStateInner,
};
use std::sync::Arc;
use tauri::Manager;
use tokio::sync::Mutex;

#[tauri::command]
fn apply_window_icon(window: tauri::WebviewWindow) {
    let icon = tauri::include_image!("icons/icon.ico");
    let _ = window.set_icon(icon);
}

pub fn run() {
    tauri::Builder::default()
        .manage(Arc::new(Mutex::new(BridgeStateInner {
            stdin: None,
            reader: None,
            child: None,
            child_pid: None,
            stream_active: false,
            init_error: None,
        })))
        .invoke_handler(tauri::generate_handler![
            bridge_send,
            bridge_send_stream,
            bridge_abort,
            bridge_init_status,
            open_path,
            open_in_folder,
            apply_window_icon
        ])
        .setup(|app| {
            let state = app.state::<BridgeState>().inner().clone();
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                match init_sidecar(Some(&app_handle)).await {
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
                    }
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
