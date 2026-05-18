#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod models;
mod project_reader;
mod watcher;

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager,
};

use std::process::Command as StdCommand;

/// Find dashboard_server.py by searching from the exe directory upward.
fn find_dashboard_server() -> Option<std::path::PathBuf> {
    let exe_dir = std::env::current_exe()
        .ok()?
        .parent()?
        .to_path_buf();

    let mut dir = exe_dir;
    loop {
        let candidate = dir.join("dashboard_server.py");
        if candidate.exists() {
            return Some(candidate);
        }
        if !dir.pop() {
            break;
        }
    }
    None
}

/// Spawn the dashboard server as a background process if not already running.
fn ensure_dashboard_server() {
    // Quick check: try to connect to port 8000
    if std::net::TcpStream::connect("127.0.0.1:8000").is_ok() {
        // Server already running
        return;
    }

    if let Some(server_path) = find_dashboard_server() {
        let server_dir = server_path.parent().unwrap().to_path_buf();
        // Try "python" first, fall back to "py"
        let python = if StdCommand::new("python").arg("--version").output().is_ok() {
            "python"
        } else {
            "py"
        };

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            let _ = StdCommand::new(python)
                .arg(&server_path)
                .current_dir(&server_dir)
                .creation_flags(CREATE_NO_WINDOW)
                .spawn();
        }

        #[cfg(not(windows))]
        {
            let _ = StdCommand::new(python)
                .arg(&server_path)
                .current_dir(&server_dir)
                .spawn();
        }
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            // 已有实例运行时，将已有窗口显示并聚焦
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .invoke_handler(tauri::generate_handler![
            commands::get_projects,
            commands::get_dashboard_data,
            commands::set_always_on_top,
            commands::read_window_sizes,
            commands::write_window_sizes,
        ])
        .setup(|app| {
            // --- Auto-start Dashboard Server ---
            ensure_dashboard_server();

            // --- System Tray ---
            let show_item = MenuItem::with_id(app, "show", "显示窗口", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_item, &quit_item])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            if window.is_visible().unwrap_or(false) {
                                let _ = window.hide();
                            } else {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                    }
                })
                .build(app)?;

            // --- File Watcher ---
            let projects_path = commands::projects_json_path();
            watcher::start_watching(app.handle().clone(), projects_path);

            Ok(())
        })
        .on_window_event(|window, event| {
            // Intercept close → hide to tray instead of quitting
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
