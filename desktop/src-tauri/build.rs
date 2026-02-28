fn main() {
    #[cfg(target_os = "windows")]
    ensure_windows_icon_format();

    tauri_build::build()
}

/// 在 Windows 上生成符合 RC 要求的 ICO 格式，避免 RC2175（not in 3.00 format）
#[cfg(target_os = "windows")]
fn ensure_windows_icon_format() {
    use std::path::Path;

    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR");
    let icon_path = Path::new(&manifest_dir).join("icons").join("icon.ico");

    // 32x32 RGBA，简单蓝色
    let rgba: Vec<u8> = (0..32 * 32 * 4)
        .map(|i| {
            if i % 4 == 3 {
                255
            } else {
                [0x25u8, 0x63, 0xeb][i % 4]
            }
        })
        .collect();

    let image = ico::IconImage::from_rgba_data(32, 32, rgba);
    let mut icon_dir = ico::IconDir::new(ico::ResourceType::Icon);
    icon_dir.add_entry(ico::IconDirEntry::encode(&image).expect("encode icon"));
    let file = std::fs::File::create(&icon_path).expect("create icon.ico");
    icon_dir.write(file).expect("write icon.ico");
}
