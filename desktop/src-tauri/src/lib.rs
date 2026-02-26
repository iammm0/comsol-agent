mod bridge;

use bridge::{bridge_send, bridge_send_stream, init_bridge, BridgeState};
use std::sync::Arc;
use tauri::Manager;

pub fn run() {
    tauri::Builder::default()
        .manage(BridgeState(Arc::new(Mutex::new(None))))
        .invoke_handler(tauri::generate_handler![bridge_send, bridge_send_stream])
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
