mod bridge;

use bridge::{bridge_send, bridge_send_stream, init_bridge, BridgeState};
use std::sync::Mutex;
use tauri::Manager;

pub fn run() {
    tauri::Builder::default()
        .manage(BridgeState(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![bridge_send, bridge_send_stream])
        .setup(|app| {
            let state = app.state::<BridgeState>();
            match init_bridge() {
                Ok(inner) => {
                    *state.0.lock().unwrap() = Some(inner);
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
