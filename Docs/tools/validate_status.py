#!/usr/bin/env python3
"""Validate status.yaml against schema.yaml structural constraints."""

import argparse
import sys
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser(description="Validate status.yaml")
    parser.add_argument("--project", required=True, help="Project root path")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    status_file = project / "status" / "status.yaml"
    schema_file = project / "status" / "schema.yaml"

    if not status_file.exists():
        print(f"ERROR: {status_file} not found.", file=sys.stderr)
        sys.exit(1)

    if not schema_file.exists():
        print(f"ERROR: {schema_file} not found.", file=sys.stderr)
        sys.exit(1)

    with open(status_file, "r", encoding="utf-8") as f:
        status = yaml.safe_load(f)

    with open(schema_file, "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)

    errors = []

    # Check required top-level keys
    required_keys = schema.get("required_top_level_keys", [])
    for key in required_keys:
        if key not in status:
            errors.append(f"Missing required top-level key: '{key}'")

    # Check meta required fields
    meta = status.get("meta", {})
    if meta:
        for field in schema.get("meta_required_fields", []):
            if field not in meta:
                errors.append(f"Missing meta field: '{field}'")

    # Check artifact statuses are valid
    valid_statuses = set(schema.get("artifact_statuses", []))
    for artifact in status.get("artifacts", []):
        art_status = artifact.get("status", "")
        if art_status and art_status not in valid_statuses:
            errors.append(
                f"Artifact '{artifact.get('id', '?')}' has invalid status: '{art_status}'. "
                f"Valid: {sorted(valid_statuses)}"
            )
        # Check required fields
        for field in schema.get("artifact_required_fields", []):
            if field not in artifact:
                errors.append(f"Artifact '{artifact.get('id', '?')}' missing field: '{field}'")

    # Check research findings
    for rf in status.get("research_findings", []):
        for field in schema.get("research_finding_required_fields", []):
            if field not in rf:
                errors.append(f"Research finding '{rf.get('id', '?')}' missing field: '{field}'")

    # Check blockers
    for b in status.get("blockers", []):
        for field in schema.get("blocker_required_fields", []):
            if field not in b:
                errors.append(f"Blocker '{b.get('id', '?')}' missing field: '{field}'")

    # Check handoff contexts
    for hc in status.get("handoff_contexts", []):
        for field in schema.get("handoff_context_required_fields", []):
            if field not in hc:
                errors.append(f"HandoffContext '{hc.get('id', '?')}' missing field: '{field}'")

    if errors:
        print("VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print("Validation passed. status.yaml is structurally correct.")
        sys.exit(0)


if __name__ == "__main__":
    main()
