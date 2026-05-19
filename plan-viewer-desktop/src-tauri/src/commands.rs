use std::path::{Path, PathBuf};

use crate::models::{DashboardData, ProjectEntry, UpdateStatusResponse, VALID_STATUSES};
use crate::project_reader;

/// Resolve the path to projects.json.
/// Searches from the executable directory upward until found.
pub fn projects_json_path() -> PathBuf {
    let exe_dir = std::env::current_exe()
        .unwrap_or_default()
        .parent()
        .unwrap_or_else(|| std::path::Path::new("."))
        .to_path_buf();

    let mut dir = exe_dir.clone();
    loop {
        let candidate = dir.join("projects.json");
        if candidate.exists() {
            return candidate;
        }
        if !dir.pop() {
            break;
        }
    }

    // Fallback: next to executable
    exe_dir.join("projects.json")
}

#[tauri::command]
pub fn get_projects() -> Result<Vec<ProjectEntry>, String> {
    let path = projects_json_path();
    project_reader::load_projects(&path)
}

#[tauri::command]
pub fn get_dashboard_data() -> Result<DashboardData, String> {
    let path = projects_json_path();
    project_reader::read_all_projects(&path)
}

#[tauri::command]
pub fn set_always_on_top(window: tauri::Window, enabled: bool) -> Result<(), String> {
    window
        .set_always_on_top(enabled)
        .map_err(|e| format!("Failed to set always on top: {}", e))
}

// Note: set_opacity is not available in Tauri v2 Window API.
// Opacity is handled purely via CSS on the frontend.

#[tauri::command]
pub fn read_window_sizes(app: tauri::AppHandle) -> Result<String, String> {
    use tauri::Manager;

    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to get app data dir: {}", e))?;

    let file_path = data_dir.join("window-sizes.json");

    match std::fs::read_to_string(&file_path) {
        Ok(content) => Ok(content),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok("{}".to_string()),
        Err(e) => Err(format!("Failed to read window-sizes.json: {}", e)),
    }
}

#[tauri::command]
pub fn write_window_sizes(app: tauri::AppHandle, data: String) -> Result<(), String> {
    use tauri::Manager;

    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to get app data dir: {}", e))?;

    // Ensure the data directory exists
    std::fs::create_dir_all(&data_dir)
        .map_err(|e| format!("Failed to create app data dir: {}", e))?;

    let file_path = data_dir.join("window-sizes.json");
    let tmp_path = data_dir.join("window-sizes.json.tmp");

    // Write to temporary file first
    std::fs::write(&tmp_path, &data)
        .map_err(|e| format!("Failed to write temp file: {}", e))?;

    // Atomic rename
    std::fs::rename(&tmp_path, &file_path)
        .map_err(|e| format!("Failed to rename temp file: {}", e))?;

    Ok(())
}

/// Resolve a project name to its filesystem path by matching against
/// `meta.project_name` in each project's status.yaml, or falling back
/// to the directory name.
fn resolve_project_path(project_name: &str) -> Result<PathBuf, String> {
    let projects_path = projects_json_path();
    let entries = project_reader::load_projects(&projects_path)?;

    for entry in &entries {
        let project_path = Path::new(&entry.path);
        let status_file = project_path.join("status").join("status.yaml");
        if !status_file.exists() {
            continue;
        }
        let content = match std::fs::read_to_string(&status_file) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let data: serde_yaml::Value = match serde_yaml::from_str(&content) {
            Ok(d) => d,
            Err(_) => continue,
        };
        let meta_name = data
            .get("meta")
            .and_then(|m| m.get("project_name"))
            .and_then(|v| v.as_str())
            .unwrap_or("");

        let dir_name = project_path
            .file_name()
            .unwrap_or_default()
            .to_str()
            .unwrap_or("");

        if meta_name == project_name || dir_name == project_name {
            return Ok(project_path.to_path_buf());
        }
    }

    Err(format!("Project not found: '{}'", project_name))
}

/// Testable helper: update an artifact's status directly in a given status.yaml file.
/// This function encapsulates the core validation and file-mutation logic without
/// requiring Tauri app state or project resolution from projects.json.
pub fn update_status_in_file(
    status_file: &Path,
    artifact_id: &str,
    new_status: &str,
) -> Result<UpdateStatusResponse, String> {
    // Validate new_status against allowed values
    if !VALID_STATUSES.contains(&new_status) {
        return Err(format!(
            "Invalid status '{}'. Valid values: {}",
            new_status,
            VALID_STATUSES.join(", ")
        ));
    }

    // Read status.yaml
    let content = std::fs::read_to_string(status_file)
        .map_err(|e| format!("Failed to read status.yaml: {}", e))?;

    // Parse as serde_yaml::Value
    let mut data: serde_yaml::Value = serde_yaml::from_str(&content)
        .map_err(|e| format!("Failed to parse status.yaml: {}", e))?;

    // Find artifact by id in the artifacts sequence
    let artifacts = data
        .get_mut("artifacts")
        .and_then(|v| v.as_sequence_mut())
        .ok_or_else(|| format!("Artifact not found: '{}' in file", artifact_id))?;

    let artifact = artifacts
        .iter_mut()
        .find(|a| {
            a.get("id")
                .and_then(|v| v.as_str())
                .map(|s| s == artifact_id)
                .unwrap_or(false)
        })
        .ok_or_else(|| format!("Artifact not found: '{}' in file", artifact_id))?;

    // Update the artifact's status field
    if let Some(mapping) = artifact.as_mapping_mut() {
        mapping.insert(
            serde_yaml::Value::String("status".to_string()),
            serde_yaml::Value::String(new_status.to_string()),
        );
    }

    // Update meta.last_updated to current UTC ISO 8601
    let now = chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string();
    if let Some(meta) = data.get_mut("meta").and_then(|m| m.as_mapping_mut()) {
        meta.insert(
            serde_yaml::Value::String("last_updated".to_string()),
            serde_yaml::Value::String(now),
        );
    }

    // Serialize back to YAML
    let yaml_output = serde_yaml::to_string(&data)
        .map_err(|e| format!("Failed to write status.yaml: {}", e))?;

    // Write to .tmp file then atomic rename
    let tmp_path = status_file.with_extension("yaml.tmp");
    std::fs::write(&tmp_path, &yaml_output)
        .map_err(|e| format!("Failed to write status.yaml: {}", e))?;

    std::fs::rename(&tmp_path, status_file)
        .map_err(|e| {
            let _ = std::fs::remove_file(&tmp_path);
            format!("Failed to write status.yaml: {}", e)
        })?;

    Ok(UpdateStatusResponse {
        artifact_id: artifact_id.to_string(),
        new_status: new_status.to_string(),
    })
}

#[tauri::command]
pub fn update_artifact_status(
    project_name: String,
    artifact_id: String,
    new_status: String,
) -> Result<UpdateStatusResponse, String> {
    // Validate non-empty parameters
    if project_name.is_empty() {
        return Err("Missing required parameter: project_name".to_string());
    }
    if artifact_id.is_empty() {
        return Err("Missing required parameter: artifact_id".to_string());
    }
    if new_status.is_empty() {
        return Err("Missing required parameter: new_status".to_string());
    }

    // Resolve project path
    let project_path = resolve_project_path(&project_name)?;
    let status_file = project_path.join("status").join("status.yaml");

    update_status_in_file(&status_file, &artifact_id, &new_status)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::VALID_STATUSES;
    use proptest::prelude::*;
    use std::fs;
    use tempfile::TempDir;

    /// Create a temporary status.yaml with the given number of artifacts.
    /// Returns (TempDir, path to status.yaml, list of artifact IDs).
    fn create_test_status_yaml(artifact_count: usize) -> (TempDir, PathBuf, Vec<String>) {
        let tmp_dir = TempDir::new().unwrap();
        let status_file = tmp_dir.path().join("status.yaml");

        let mut artifact_ids = Vec::new();
        let mut artifacts_yaml = String::new();

        for i in 0..artifact_count {
            let id = format!("artifact-{}", i);
            artifact_ids.push(id.clone());
            artifacts_yaml.push_str(&format!(
                "  - id: \"{}\"\n    type: \"research\"\n    status: \"draft\"\n    path: \"docs/{}.md\"\n",
                id, id
            ));
        }

        let yaml_content = format!(
            "meta:\n  project_name: \"test-project\"\n  last_updated: \"2025-01-01T00:00:00Z\"\nartifacts:\n{}",
            artifacts_yaml
        );

        fs::write(&status_file, &yaml_content).unwrap();

        (tmp_dir, status_file, artifact_ids)
    }

    // Feature: status-change-interaction, Property 1: Status update round-trip
    // **Validates: Requirements 1.1, 1.2**
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]
        #[test]
        fn status_update_round_trip(
            status_idx in 0..9usize,
            artifact_idx in 0..5usize,
        ) {
            let artifact_count = 5;
            let (_tmp_dir, status_file, artifact_ids) = create_test_status_yaml(artifact_count);

            let chosen_status = VALID_STATUSES[status_idx];
            let chosen_artifact = &artifact_ids[artifact_idx];

            // Act: call update logic
            let result = update_status_in_file(&status_file, chosen_artifact, chosen_status);

            // Assert: result is Ok with correct fields
            let response = result.unwrap();
            prop_assert_eq!(&response.artifact_id, chosen_artifact);
            prop_assert_eq!(&response.new_status, chosen_status);

            // Assert: re-read file, verify status matches
            let content = fs::read_to_string(&status_file).unwrap();
            let data: serde_yaml::Value = serde_yaml::from_str(&content).unwrap();

            let artifacts = data.get("artifacts").unwrap().as_sequence().unwrap();
            let artifact = artifacts.iter().find(|a| {
                a.get("id").and_then(|v| v.as_str()) == Some(chosen_artifact.as_str())
            }).unwrap();

            let file_status = artifact.get("status").unwrap().as_str().unwrap();
            prop_assert_eq!(file_status, chosen_status);

            // Assert: meta.last_updated is valid ISO 8601 UTC timestamp
            let last_updated = data.get("meta").unwrap()
                .get("last_updated").unwrap()
                .as_str().unwrap();

            // Verify it matches YYYY-MM-DDTHH:MM:SSZ format
            let parsed = chrono::NaiveDateTime::parse_from_str(last_updated, "%Y-%m-%dT%H:%M:%SZ");
            prop_assert!(parsed.is_ok(), "meta.last_updated '{}' is not valid ISO 8601 UTC", last_updated);
        }
    }

    // Feature: status-change-interaction, Property 2: Invalid status rejection
    // **Validates: Requirements 1.3**
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]
        #[test]
        fn invalid_status_rejected(
            bad_status in "[a-z]{1,20}".prop_filter("not a valid status", |s| !VALID_STATUSES.contains(&s.as_str())),
        ) {
            // Setup: create temp status.yaml with known content
            let (_tmp_dir, status_file, artifact_ids) = create_test_status_yaml(3);

            // Record file bytes before the call
            let bytes_before = fs::read(&status_file).unwrap();

            // Act: call update with bad_status
            let result = update_status_in_file(&status_file, &artifact_ids[0], &bad_status);

            // Assert: error returned containing "Invalid status"
            prop_assert!(result.is_err(), "Expected error for invalid status '{}', got Ok", bad_status);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Invalid status"),
                "Error message '{}' should contain 'Invalid status'", err_msg
            );

            // Assert: file is byte-for-byte identical to before
            let bytes_after = fs::read(&status_file).unwrap();
            prop_assert_eq!(bytes_before, bytes_after, "File was modified despite invalid status '{}'", bad_status);
        }
    }

    // Feature: status-change-interaction, Property 3: Non-existent entity rejection
    // **Validates: Requirements 1.4, 1.5**
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]
        #[test]
        fn nonexistent_artifact_rejected(
            random_id in "[a-zA-Z0-9_-]{1,30}",
        ) {
            // Known artifact IDs in our test file
            let known_ids: Vec<String> = (0..3).map(|i| format!("artifact-{}", i)).collect();

            // Filter out any generated ID that happens to match a known one
            prop_assume!(!known_ids.contains(&random_id));

            let (_tmp_dir, status_file, _artifact_ids) = create_test_status_yaml(3);

            // Capture file content before the call
            let content_before = fs::read_to_string(&status_file).unwrap();

            // Act: call update with non-existent artifact ID
            let result = update_status_in_file(&status_file, &random_id, "approved");

            // Assert: error returned containing "Artifact not found"
            prop_assert!(result.is_err(), "Expected error for non-existent artifact '{}'", random_id);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Artifact not found"),
                "Error message '{}' should contain 'Artifact not found'", err_msg
            );

            // Assert: file is byte-for-byte unchanged
            let content_after = fs::read_to_string(&status_file).unwrap();
            prop_assert_eq!(content_before, content_after, "File should not be modified for non-existent artifact");
        }
    }

    // Feature: status-change-interaction, Property 4: Empty parameter validation
    // **Validates: Requirements 1.7**
    //
    // For any combination where at least one parameter is empty, verify:
    // - error identifying the empty parameter(s)
    // - no file modification

    /// Strategy: generate non-empty strings for the "filled" parameters
    fn non_empty_param() -> impl Strategy<Value = String> {
        "[a-zA-Z0-9_-]{1,20}"
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]

        /// Property 4: When project_name is empty, error is returned identifying it.
        #[test]
        fn empty_project_name_rejected(
            artifact_id in non_empty_param(),
            new_status in non_empty_param(),
        ) {
            let (_tmp_dir, status_file, _) = create_test_status_yaml(3);
            let original_content = fs::read(&status_file).unwrap();

            let result = update_artifact_status(
                String::new(),
                artifact_id,
                new_status,
            );

            // Must be an error
            prop_assert!(result.is_err(), "Expected error for empty project_name, got: {:?}", result);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Missing required parameter"),
                "Error should mention 'Missing required parameter', got: {}",
                err_msg
            );
            prop_assert!(
                err_msg.contains("project_name"),
                "Error should identify 'project_name' as the empty parameter, got: {}",
                err_msg
            );

            // File must be unchanged
            let after_content = fs::read(&status_file).unwrap();
            prop_assert_eq!(original_content, after_content, "File should not be modified");
        }

        /// Property 4: When artifact_id is empty, error is returned identifying it.
        #[test]
        fn empty_artifact_id_rejected(
            project_name in non_empty_param(),
            new_status in non_empty_param(),
        ) {
            let (_tmp_dir, status_file, _) = create_test_status_yaml(3);
            let original_content = fs::read(&status_file).unwrap();

            let result = update_artifact_status(
                project_name,
                String::new(),
                new_status,
            );

            prop_assert!(result.is_err(), "Expected error for empty artifact_id, got: {:?}", result);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Missing required parameter"),
                "Error should mention 'Missing required parameter', got: {}",
                err_msg
            );
            prop_assert!(
                err_msg.contains("artifact_id"),
                "Error should identify 'artifact_id' as the empty parameter, got: {}",
                err_msg
            );

            // File must be unchanged
            let after_content = fs::read(&status_file).unwrap();
            prop_assert_eq!(original_content, after_content, "File should not be modified");
        }

        /// Property 4: When new_status is empty, error is returned identifying it.
        #[test]
        fn empty_new_status_rejected(
            project_name in non_empty_param(),
            artifact_id in non_empty_param(),
        ) {
            let (_tmp_dir, status_file, _) = create_test_status_yaml(3);
            let original_content = fs::read(&status_file).unwrap();

            let result = update_artifact_status(
                project_name,
                artifact_id,
                String::new(),
            );

            prop_assert!(result.is_err(), "Expected error for empty new_status, got: {:?}", result);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Missing required parameter"),
                "Error should mention 'Missing required parameter', got: {}",
                err_msg
            );
            prop_assert!(
                err_msg.contains("new_status"),
                "Error should identify 'new_status' as the empty parameter, got: {}",
                err_msg
            );

            // File must be unchanged
            let after_content = fs::read(&status_file).unwrap();
            prop_assert_eq!(original_content, after_content, "File should not be modified");
        }

        /// Property 4: Random combination where at least one param is empty.
        /// Uses a bitmask (1-7) to randomly make at least one parameter empty.
        #[test]
        fn random_empty_combination_rejected(
            base_project in non_empty_param(),
            base_artifact in non_empty_param(),
            base_status in non_empty_param(),
            // Bitmask 1-7: at least one bit set means that param is empty
            empty_mask in 1u8..8u8,
        ) {
            let project_name = if empty_mask & 1 != 0 { String::new() } else { base_project };
            let artifact_id = if empty_mask & 2 != 0 { String::new() } else { base_artifact };
            let new_status = if empty_mask & 4 != 0 { String::new() } else { base_status };

            let (_tmp_dir, status_file, _) = create_test_status_yaml(3);
            let original_content = fs::read(&status_file).unwrap();

            let result = update_artifact_status(
                project_name,
                artifact_id,
                new_status,
            );

            prop_assert!(result.is_err(), "Expected error when at least one param is empty, got: {:?}", result);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Missing required parameter"),
                "Error should mention 'Missing required parameter', got: {}",
                err_msg
            );

            // File must be unchanged
            let after_content = fs::read(&status_file).unwrap();
            prop_assert_eq!(original_content, after_content, "File should not be modified");
        }
    }
}
