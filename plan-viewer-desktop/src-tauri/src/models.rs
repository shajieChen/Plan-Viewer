use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A project entry from projects.json
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectEntry {
    pub path: String,
}

/// Top-level projects.json structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectsConfig {
    pub projects: Vec<ProjectEntry>,
}

/// An artifact tracked in status.yaml
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Artifact {
    pub id: String,
    #[serde(rename = "type")]
    pub artifact_type: String,
    pub status: String,
    #[serde(default)]
    pub path: String,
    #[serde(default)]
    pub depends_on: Vec<serde_yaml::Value>,
    #[serde(default)]
    pub produces_handoffs: Vec<String>,
    #[serde(default)]
    pub consumes_handoffs: Vec<String>,
    #[serde(default)]
    pub last_checked: String,
    /// Derived at runtime, not from YAML
    #[serde(skip_deserializing, default)]
    pub group: String,
}

/// A change event from status.yaml
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangeEvent {
    #[serde(default)]
    pub id: String,
    #[serde(default)]
    pub time: String,
    #[serde(default)]
    pub source: String,
    #[serde(default)]
    pub event_type: String,
    #[serde(default)]
    pub summary: String,
    #[serde(default)]
    pub affected: Vec<String>,
}

/// Markdown preview for an artifact
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MarkdownPreview {
    pub title: String,
    pub excerpt: String,
}

/// Complete project data sent to the frontend
#[derive(Debug, Clone, Serialize)]
pub struct ProjectData {
    pub meta: serde_yaml::Value,
    pub artifacts: Vec<Artifact>,
    pub change_events: Vec<ChangeEvent>,
    pub markdown_previews: HashMap<String, MarkdownPreview>,
}

/// Dashboard data envelope (all projects)
#[derive(Debug, Clone, Serialize)]
pub struct DashboardData {
    pub projects: HashMap<String, ProjectData>,
}

/// Payload emitted when a project file changes
#[derive(Debug, Clone, Serialize)]
pub struct ProjectUpdatePayload {
    pub project_path: String,
    pub timestamp: String,
}
