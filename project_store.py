"""
Persistence management for projects.json.

Provides load_projects() and save_projects() for reading/writing
the project list configuration file.
"""

import json
from pathlib import Path

# projects.json lives in the same directory as this script
PROJECTS_FILE = Path(__file__).resolve().parent / "projects.json"


def load_projects() -> list:
    """Read projects from projects.json.

    If the file does not exist, creates it with an empty project list
    and returns [].

    Returns:
        A list of project dicts, e.g. [{"path": "Q:\\..."}]
    """
    if not PROJECTS_FILE.exists():
        save_projects([])
        return []

    with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("projects", [])


def save_projects(projects: list) -> None:
    """Write the project list to projects.json.

    All paths are resolved to absolute paths before saving.
    The file is written in UTF-8 with 2-space indentation.

    Args:
        projects: A list of project dicts, e.g. [{"path": "Q:\\..."}]
    """
    # Normalize paths to absolute
    normalized = []
    for entry in projects:
        path = str(Path(entry["path"]).resolve())
        normalized.append({"path": path})

    data = {"projects": normalized}

    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
