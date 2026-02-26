mod bridge;

use bridge::{bridge_send, bridge_send_stream, init_bridge, open_path, open_in_folder, BridgeState};
use std::sync::Arc;
use tauri::Manager;
use tokio::process::Child;
use tokio::sync::Mutex;

pub fn run() {
    tauri::Builder::default()
        .manage(Arc::new(Mutex::new(None::<Child>)))
        .invoke_handler(tauri::generate_handler![bridge_send, bridge_send_stream, open_path, open_in_folder])
        .setup(|app| {
            let state = app.state::<BridgeState>().inner().clone();
            let rt = tokio::runtime::Runtime::new().expect("create tokio runtime");
            match rt.block_on(init_bridge()) {
                Ok(child) => {
                    let mut guard = state.as_ref().blocking_lock();
                    *guard = Some(child);
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
