use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::ffi::OsString;
use std::os::windows::ffi::OsStringExt;
use std::path::{Path, PathBuf};
use windows::Win32::Foundation::{BOOL, CloseHandle, HWND, LPARAM, MAX_PATH, TRUE};
use windows::Win32::Graphics::Dwm::{DWMWA_CLOAKED, DwmGetWindowAttribute};
use windows::Win32::System::Threading::{
    OpenProcess, PROCESS_NAME_WIN32, PROCESS_QUERY_LIMITED_INFORMATION,
    QueryFullProcessImageNameW,
};
use windows::Win32::UI::WindowsAndMessaging::{
    EnumWindows, FLASHWINFO, FLASHW_ALL, FLASHW_TIMERNOFG, FlashWindowEx, GetWindowTextLengthW,
    GetWindowTextW, GetWindowThreadProcessId, IsIconic, IsWindow, IsWindowVisible,
    SW_RESTORE, SetForegroundWindow, ShowWindow,
};

/// Information about a visible window/process for the selector.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessInfo {
    /// Process executable name, e.g. "devenv.exe"
    pub process_name: String,
    /// Process ID
    pub pid: u32,
    /// Window handle (HWND as isize for serialization)
    pub hwnd: isize,
    /// Window title, e.g. "MyProject - Visual Studio"
    pub window_title: String,
}

/// Result of a focus operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FocusResult {
    /// true if SetForegroundWindow succeeded
    pub success: bool,
    /// true if fell back to FlashWindowEx
    pub flashed: bool,
}

/// Helper: check if a window is cloaked via DwmGetWindowAttribute.
fn is_window_cloaked(hwnd: HWND) -> bool {
    let mut cloaked: u32 = 0;
    let result = unsafe {
        DwmGetWindowAttribute(
            hwnd,
            DWMWA_CLOAKED,
            &mut cloaked as *mut u32 as *mut _,
            std::mem::size_of::<u32>() as u32,
        )
    };
    result.is_ok() && cloaked != 0
}

/// Helper: get window title text. Returns empty string on failure.
fn get_window_title(hwnd: HWND) -> String {
    let len = unsafe { GetWindowTextLengthW(hwnd) };
    if len == 0 {
        return String::new();
    }
    let mut buf = vec![0u16; (len + 1) as usize];
    let copied = unsafe { GetWindowTextW(hwnd, &mut buf) };
    if copied == 0 {
        return String::new();
    }
    OsString::from_wide(&buf[..copied as usize])
        .to_string_lossy()
        .into_owned()
}

/// Helper: get the process executable name (stem only, no extension) from a PID.
/// Returns None if the process cannot be opened or queried.
fn get_process_name(pid: u32) -> Option<String> {
    unsafe {
        let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid).ok()?;
        let mut buf = [0u16; MAX_PATH as usize];
        let mut size = buf.len() as u32;
        let ok = QueryFullProcessImageNameW(
            handle,
            PROCESS_NAME_WIN32,
            windows::core::PWSTR(buf.as_mut_ptr()),
            &mut size,
        );
        let _ = CloseHandle(handle);
        if ok.is_err() {
            return None;
        }
        let path = OsString::from_wide(&buf[..size as usize])
            .to_string_lossy()
            .into_owned();
        // Extract just the file stem (name without extension)
        let file_name = std::path::Path::new(&path)
            .file_stem()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or(path);
        Some(file_name)
    }
}

/// Enumerate all visible top-level windows, returning one entry per window.
/// Filters out: windows without WS_VISIBLE, cloaked windows, empty titles,
/// and the Plan Viewer process itself.
pub fn enumerate_visible_windows() -> Result<Vec<ProcessInfo>, String> {
    let mut results: Vec<ProcessInfo> = Vec::new();

    unsafe extern "system" fn enum_callback(hwnd: HWND, lparam: LPARAM) -> BOOL {
        let results = &mut *(lparam.0 as *mut Vec<ProcessInfo>);

        // Check if window is visible
        if !IsWindowVisible(hwnd).as_bool() {
            return TRUE;
        }

        // Check if window is cloaked
        if is_window_cloaked(hwnd) {
            return TRUE;
        }

        // Get window title — skip empty titles
        let title = get_window_title(hwnd);
        if title.is_empty() {
            return TRUE;
        }

        // Get PID
        let mut pid: u32 = 0;
        GetWindowThreadProcessId(hwnd, Some(&mut pid));
        if pid == 0 {
            return TRUE;
        }

        // Get process name
        let process_name = match get_process_name(pid) {
            Some(name) => name,
            None => return TRUE,
        };

        // Filter out self (plan-viewer-desktop)
        if process_name == "plan-viewer-desktop" {
            return TRUE;
        }

        results.push(ProcessInfo {
            process_name,
            pid,
            hwnd: hwnd.0 as isize,
            window_title: title,
        });

        TRUE
    }

    let ret = unsafe {
        EnumWindows(
            Some(enum_callback),
            LPARAM(&mut results as *mut Vec<ProcessInfo> as isize),
        )
    };

    if let Err(e) = ret {
        return Err(format!("EnumWindows failed: {}", e));
    }

    Ok(results)
}

/// Filter out entries with process_name "plan-viewer-desktop" from a list of ProcessInfo.
/// This is the pure, testable version of the self-process filtering logic used in enum_callback.
pub fn filter_self_process(processes: Vec<ProcessInfo>) -> Vec<ProcessInfo> {
    processes
        .into_iter()
        .filter(|p| p.process_name != "plan-viewer-desktop")
        .collect()
}

/// Check if a process is still alive by attempting OpenProcess.
/// Returns `false` on any error (permission denied, invalid PID) as fail-safe.
pub fn is_process_alive(pid: u32) -> bool {
    use windows::Win32::System::Threading::GetExitCodeProcess;

    // STILL_ACTIVE is defined as 259 (STATUS_PENDING)
    const STILL_ACTIVE: u32 = 259;

    unsafe {
        // Attempt to open the process with minimal access
        let handle = match OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid) {
            Ok(h) => h,
            Err(_) => return false, // Permission denied or invalid PID
        };

        // Query the exit code
        let mut exit_code: u32 = 0;
        let result = GetExitCodeProcess(handle, &mut exit_code);
        let _ = CloseHandle(handle);

        match result {
            Ok(_) => exit_code == STILL_ACTIVE,
            Err(_) => false,
        }
    }
}

/// Tauri command: enumerate visible windows for the process selector.
/// Wraps `enumerate_visible_windows()` and maps errors to a descriptive string.
#[tauri::command]
pub fn enumerate_processes() -> Result<Vec<ProcessInfo>, String> {
    enumerate_visible_windows().map_err(|e| format!("枚举进程失败: {}", e))
}

/// Bring the specified window to the foreground.
/// If minimized, restores first. If SetForegroundWindow fails, flashes taskbar.
pub fn focus_window(hwnd: isize) -> Result<FocusResult, String> {
    let hwnd_win = HWND(hwnd as *mut _);

    // 1. Check if the window still exists
    if !unsafe { IsWindow(hwnd_win) }.as_bool() {
        return Err("process_terminated".to_string());
    }

    // 2. If minimized, restore first
    if unsafe { IsIconic(hwnd_win) }.as_bool() {
        let _ = unsafe { ShowWindow(hwnd_win, SW_RESTORE) };
    }

    // 3. Attempt to bring to foreground
    let success = unsafe { SetForegroundWindow(hwnd_win) }.as_bool();

    if success {
        Ok(FocusResult {
            success: true,
            flashed: false,
        })
    } else {
        // 4. Foreground denied — flash the taskbar entry as fallback
        let mut flash_info = FLASHWINFO {
            cbSize: std::mem::size_of::<FLASHWINFO>() as u32,
            hwnd: hwnd_win,
            dwFlags: FLASHW_ALL | FLASHW_TIMERNOFG,
            uCount: 3,
            dwTimeout: 0, // use default cursor blink rate
        };
        let _ = unsafe { FlashWindowEx(&mut flash_info) };

        Ok(FocusResult {
            success: false,
            flashed: true,
        })
    }
}

/// Tauri command: check liveness then focus the bound window.
/// Returns `Err("process_terminated")` if the process is no longer alive.
#[tauri::command]
pub fn focus_bound_window(pid: u32, hwnd: isize) -> Result<FocusResult, String> {
    if !is_process_alive(pid) {
        return Err("process_terminated".to_string());
    }
    focus_window(hwnd)
}

/// Tauri command: validate that a process is alive before confirming a bind.
/// Binding state is managed frontend-side; this only performs the liveness check.
#[tauri::command]
pub fn bind_process(pid: u32, hwnd: isize) -> Result<(), String> {
    if !is_process_alive(pid) {
        return Err("process_terminated".to_string());
    }
    // hwnd is accepted for future use but not validated here —
    // the frontend stores it as part of the binding state.
    let _ = hwnd;
    Ok(())
}

/// Tauri command: read all persisted project→process bindings from disk.
#[tauri::command]
pub fn read_process_bindings(app_handle: tauri::AppHandle) -> HashMap<String, ProcessBinding> {
    let path = bindings_file_path(&app_handle);
    read_all_bindings(&path)
}

// ─── Per-Project Process Binding Persistence ───────────────────────────────

/// A persisted process binding for a single project.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessBinding {
    pub pid: u32,
    pub hwnd: isize,
    pub process_name: String,
    pub window_title: String,
}

/// Return the path to `process_bindings.json` inside the Tauri app data directory.
pub fn bindings_file_path(app_handle: &tauri::AppHandle) -> PathBuf {
    use tauri::Manager;
    let data_dir = app_handle
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| PathBuf::from("."));
    data_dir.join("process_bindings.json")
}

/// Read all project→ProcessBinding entries from the given JSON file path.
/// Returns an empty HashMap if the file does not exist or cannot be parsed.
pub fn read_all_bindings(path: &Path) -> HashMap<String, ProcessBinding> {
    let content = match std::fs::read_to_string(path) {
        Ok(c) => c,
        Err(_) => return HashMap::new(),
    };
    serde_json::from_str(&content).unwrap_or_default()
}

/// Write all project→ProcessBinding entries to the given JSON file path.
/// Creates parent directories if needed. Uses pretty-printed UTF-8 JSON.
pub fn write_all_bindings(path: &Path, map: &HashMap<String, ProcessBinding>) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create directory: {}", e))?;
    }
    let json = serde_json::to_string_pretty(map)
        .map_err(|e| format!("Failed to serialize bindings: {}", e))?;
    std::fs::write(path, json.as_bytes())
        .map_err(|e| format!("Failed to write bindings file: {}", e))?;
    Ok(())
}

// ─── Per-Project Process Binding Tauri Commands ────────────────────────────

/// Tauri command: write (upsert) a single project's process binding.
/// Reads existing bindings, inserts/updates the key, then writes back.
#[tauri::command]
pub fn write_process_binding(
    app_handle: tauri::AppHandle,
    project_name: String,
    binding: ProcessBinding,
) -> Result<(), String> {
    let path = bindings_file_path(&app_handle);
    let mut map = read_all_bindings(&path);
    map.insert(project_name, binding);
    write_all_bindings(&path, &map)
}

/// Tauri command: remove a single project's process binding.
/// Key not found is treated as silent success (no error).
#[tauri::command]
pub fn remove_process_binding(
    app_handle: tauri::AppHandle,
    project_name: String,
) -> Result<(), String> {
    let path = bindings_file_path(&app_handle);
    let mut map = read_all_bindings(&path);
    map.remove(&project_name);
    write_all_bindings(&path, &map)
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    /// Strategy to generate a random ProcessInfo with an arbitrary process name.
    fn arb_process_info() -> impl Strategy<Value = ProcessInfo> {
        (
            "[a-z][a-z0-9\\-]{0,20}".prop_map(|s| s),
            1u32..100_000,
            1isize..1_000_000,
            "[ -~]{0,50}".prop_map(|s| s),
        )
            .prop_map(|(process_name, pid, hwnd, window_title)| ProcessInfo {
                process_name,
                pid,
                hwnd,
                window_title,
            })
    }

    /// Strategy to generate a ProcessInfo that is specifically named "plan-viewer-desktop".
    fn self_process_info() -> impl Strategy<Value = ProcessInfo> {
        (1u32..100_000, 1isize..1_000_000, "[ -~]{0,50}".prop_map(|s| s)).prop_map(
            |(pid, hwnd, window_title)| ProcessInfo {
                process_name: "plan-viewer-desktop".to_string(),
                pid,
                hwnd,
                window_title,
            },
        )
    }

    /// Strategy to generate a Vec<ProcessInfo> with 0–20 entries, some of which
    /// may be named "plan-viewer-desktop".
    fn arb_process_list() -> impl Strategy<Value = Vec<ProcessInfo>> {
        prop::collection::vec(
            prop_oneof![
                3 => arb_process_info(),
                1 => self_process_info(),
            ],
            0..=20,
        )
    }

    proptest! {
        /// Feature: process-focus-button, Property 2: Self-process filtering
        ///
        /// **Validates: Requirements 2.3**
        ///
        /// For any list of ProcessInfo entries (0–20), some named "plan-viewer-desktop":
        /// - The filtered output contains NO entries with process_name "plan-viewer-desktop"
        /// - All non-self entries from the input are preserved in the output
        #[test]
        fn prop_self_process_filtering(input in arb_process_list()) {
            let non_self_input: Vec<_> = input.iter()
                .filter(|p| p.process_name != "plan-viewer-desktop")
                .cloned()
                .collect();

            let result = filter_self_process(input);

            // Assert: no "plan-viewer-desktop" entries in output
            for entry in &result {
                prop_assert_ne!(&entry.process_name, "plan-viewer-desktop",
                    "Output should not contain plan-viewer-desktop entries");
            }

            // Assert: all non-self entries are preserved (same count and same data)
            prop_assert_eq!(result.len(), non_self_input.len(),
                "All non-self entries should be preserved");

            for (got, expected) in result.iter().zip(non_self_input.iter()) {
                prop_assert_eq!(&got.process_name, &expected.process_name);
                prop_assert_eq!(got.pid, expected.pid);
                prop_assert_eq!(got.hwnd, expected.hwnd);
                prop_assert_eq!(&got.window_title, &expected.window_title);
            }
        }
    }

    // ─── Unit Tests: Binding Persistence ───────────────────────────────────

    /// Helper to create a ProcessBinding for tests.
    fn make_binding(pid: u32, hwnd: isize, name: &str, title: &str) -> ProcessBinding {
        ProcessBinding {
            pid,
            hwnd,
            process_name: name.to_string(),
            window_title: title.to_string(),
        }
    }

    #[test]
    fn test_read_nonexistent_file_returns_empty() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("nonexistent.json");
        let result = read_all_bindings(&path);
        assert!(result.is_empty());
    }

    #[test]
    fn test_write_then_read_round_trip() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("bindings.json");

        let mut map = HashMap::new();
        map.insert("ProjectA".to_string(), make_binding(1234, 5678, "devenv", "MyProject - VS"));
        map.insert("ProjectB".to_string(), make_binding(9999, 1111, "code", "workspace - VSCode"));

        write_all_bindings(&path, &map).unwrap();
        let loaded = read_all_bindings(&path);

        assert_eq!(loaded.len(), 2);

        let a = loaded.get("ProjectA").unwrap();
        assert_eq!(a.pid, 1234);
        assert_eq!(a.hwnd, 5678);
        assert_eq!(a.process_name, "devenv");
        assert_eq!(a.window_title, "MyProject - VS");

        let b = loaded.get("ProjectB").unwrap();
        assert_eq!(b.pid, 9999);
        assert_eq!(b.hwnd, 1111);
        assert_eq!(b.process_name, "code");
        assert_eq!(b.window_title, "workspace - VSCode");
    }

    #[test]
    fn test_remove_existing_key() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("bindings.json");

        let mut map = HashMap::new();
        map.insert("ProjectA".to_string(), make_binding(1234, 5678, "devenv", "VS"));
        map.insert("ProjectB".to_string(), make_binding(9999, 1111, "code", "VSCode"));
        write_all_bindings(&path, &map).unwrap();

        // Remove ProjectA
        let mut map = read_all_bindings(&path);
        map.remove("ProjectA");
        write_all_bindings(&path, &map).unwrap();

        let loaded = read_all_bindings(&path);
        assert_eq!(loaded.len(), 1);
        assert!(loaded.get("ProjectA").is_none());
        assert!(loaded.get("ProjectB").is_some());
    }

    #[test]
    fn test_remove_nonexistent_key_no_error() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("bindings.json");

        let mut map = HashMap::new();
        map.insert("ProjectA".to_string(), make_binding(1234, 5678, "devenv", "VS"));
        write_all_bindings(&path, &map).unwrap();

        // Remove a key that doesn't exist — should not error
        let mut map = read_all_bindings(&path);
        map.remove("NonExistent");
        let result = write_all_bindings(&path, &map);
        assert!(result.is_ok());

        // Original key still present
        let loaded = read_all_bindings(&path);
        assert_eq!(loaded.len(), 1);
        assert!(loaded.get("ProjectA").is_some());
    }

    #[test]
    fn test_corrupt_file_returns_empty() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("bindings.json");

        // Write invalid JSON
        std::fs::write(&path, b"{ not valid json !!!").unwrap();

        let result = read_all_bindings(&path);
        assert!(result.is_empty());
    }
}
