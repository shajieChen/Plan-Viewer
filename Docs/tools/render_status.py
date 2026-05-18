#!/usr/bin/env python3
"""Render status.yaml into human-readable views and AGENTS.md."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import yaml


def render_overview(status: dict) -> str:
    """Render overview_view.md."""
    meta = status.get("meta", {})
    artifacts = status.get("artifacts", [])
    research = status.get("research_findings", [])

    lines = [
        "# Project Overview",
        "",
        "<!-- ANCHOR: tldr -->",
        "## TL;DR",
        "",
        f"- Project: **{meta.get('project_name', 'Unknown')}**",
        f"- Last updated: {meta.get('last_updated', 'N/A')}",
        f"- Artifacts: {meta.get('total_artifacts', 0)}",
        f"- Research findings: {meta.get('total_research', 0)}",
        f"- Open blockers: {meta.get('total_blockers', 0)}",
        "",
        "<!-- ANCHOR: artifacts -->",
        "## Artifacts",
        "",
    ]

    if artifacts:
        lines.append("| ID | Type | Status | Path |")
        lines.append("|----|------|--------|------|")
        for art in artifacts:
            lines.append(f"| {art.get('id', '?')} | {art.get('type', '?')} | {art.get('status', '?')} | {art.get('path', '?')} |")
    else:
        lines.append("_No artifacts registered yet._")

    lines.extend(["", "<!-- ANCHOR: research -->", "## Research Findings", ""])

    if research:
        lines.append("| ID | Title | Status | Path |")
        lines.append("|----|-------|--------|------|")
        for rf in research:
            lines.append(f"| {rf.get('id', '?')} | {rf.get('title', '?')} | {rf.get('status', '?')} | {rf.get('path', '?')} |")
    else:
        lines.append("_No research findings registered yet._")

    return "\n".join(lines) + "\n"


def render_blocker_view(status: dict) -> str:
    """Render blocker_view.md."""
    blockers = status.get("blockers", [])
    lines = [
        "# Blockers",
        "",
        "<!-- ANCHOR: tldr -->",
        "## TL;DR",
        "",
        f"Open blockers: {len([b for b in blockers if b.get('status') == 'open'])}",
        "",
        "<!-- ANCHOR: blockers -->",
        "## Active Blockers",
        "",
    ]

    open_blockers = [b for b in blockers if b.get("status") == "open"]
    if open_blockers:
        lines.append("| ID | Title | Severity | Blocks |")
        lines.append("|----|-------|----------|--------|")
        for b in open_blockers:
            blocks_str = ", ".join(b.get("blocks", []))
            lines.append(f"| {b.get('id', '?')} | {b.get('title', '?')} | {b.get('severity', '?')} | {blocks_str} |")
    else:
        lines.append("_No open blockers._")

    return "\n".join(lines) + "\n"


def render_prompt_chain_view(status: dict) -> str:
    """Render prompt_chain_view.md."""
    artifacts = status.get("artifacts", [])
    lps = [a for a in artifacts if a.get("type") == "landing_prompt"]
    tps = [a for a in artifacts if a.get("type") == "test_prompt"]

    lines = [
        "# Prompt Chain",
        "",
        "<!-- ANCHOR: tldr -->",
        "## TL;DR",
        "",
        f"Landing Prompts: {len(lps)} | Test Prompts: {len(tps)}",
        "",
        "<!-- ANCHOR: landing-prompts -->",
        "## Landing Prompts",
        "",
    ]

    if lps:
        lines.append("| ID | Status | Depends On | Path |")
        lines.append("|----|--------|------------|------|")
        for lp in lps:
            deps = ", ".join(lp.get("depends_on", []))
            lines.append(f"| {lp.get('id', '?')} | {lp.get('status', '?')} | {deps} | {lp.get('path', '?')} |")
    else:
        lines.append("_No landing prompts registered._")

    lines.extend(["", "<!-- ANCHOR: test-prompts -->", "## Test Prompts", ""])

    if tps:
        lines.append("| ID | Status | Depends On | Path |")
        lines.append("|----|--------|------------|------|")
        for tp in tps:
            deps = ", ".join(tp.get("depends_on", []))
            lines.append(f"| {tp.get('id', '?')} | {tp.get('status', '?')} | {deps} | {tp.get('path', '?')} |")
    else:
        lines.append("_No test prompts registered._")

    return "\n".join(lines) + "\n"


def render_handoff_view(status: dict) -> str:
    """Render handoff_view.md."""
    handoffs = status.get("handoff_contexts", [])

    lines = [
        "# Handoff Contexts",
        "",
        "<!-- ANCHOR: tldr -->",
        "## TL;DR",
        "",
        f"Total handoff contexts: {len(handoffs)}",
        "",
        "<!-- ANCHOR: handoffs -->",
        "## Handoff Status",
        "",
    ]

    if handoffs:
        lines.append("| ID | Producer | Status | Version | Consumers |")
        lines.append("|----|----------|--------|---------|-----------|")
        for hc in handoffs:
            consumers = ", ".join(hc.get("consumed_by", []))
            lines.append(
                f"| {hc.get('id', '?')} | {hc.get('producer', '?')} | "
                f"{hc.get('status', '?')} | {hc.get('version', 0)} | {consumers} |"
            )
    else:
        lines.append("_No handoff contexts defined._")

    return "\n".join(lines) + "\n"


def render_change_log_view(status: dict) -> str:
    """Render change_log_view.md (last 20 events)."""
    events = status.get("change_events", [])
    recent = events[-20:] if len(events) > 20 else events

    lines = [
        "# Change Log",
        "",
        "<!-- ANCHOR: tldr -->",
        "## TL;DR",
        "",
        f"Total events: {len(events)} (showing last {len(recent)})",
        "",
        "<!-- ANCHOR: events -->",
        "## Recent Events",
        "",
    ]

    if recent:
        lines.append("| ID | Time | Type | Affected | Reason |")
        lines.append("|----|------|------|----------|--------|")
        for ev in reversed(recent):
            affected = ", ".join(ev.get("affected", []))
            reason = ev.get("reason", "")[:60]
            lines.append(
                f"| {ev.get('id', '?')} | {ev.get('time', '?')[:19]} | "
                f"{ev.get('event_type', '?')} | {affected} | {reason} |"
            )
    else:
        lines.append("_No change events recorded._")

    return "\n".join(lines) + "\n"


def render_agents_md(status: dict) -> str:
    """Render AGENTS.md — the one-page index for AI agents."""
    meta = status.get("meta", {})
    lines = [
        "# AGENTS.md — Project State Index",
        "",
        f"Project: **{meta.get('project_name', 'Unknown')}**  ",
        f"Last updated: {meta.get('last_updated', 'N/A')}",
        "",
        "## Quick Stats",
        "",
        f"- Artifacts: {meta.get('total_artifacts', 0)}",
        f"- Research: {meta.get('total_research', 0)}",
        f"- Open blockers: {meta.get('total_blockers', 0)}",
        "",
        "## Read X for Y",
        "",
        "| Need | Read |",
        "|------|------|",
        "| Full project overview | `views/overview_view.md` |",
        "| Blocker details | `views/blocker_view.md` |",
        "| Prompt execution chain | `views/prompt_chain_view.md` |",
        "| Handoff status | `views/handoff_view.md` |",
        "| Recent changes | `views/change_log_view.md` |",
        "| Authoritative state | `status/status.yaml` |",
        "",
        "## Artifact Summary",
        "",
    ]

    artifacts = status.get("artifacts", [])
    if artifacts:
        lines.append("| ID | Type | Status |")
        lines.append("|----|------|--------|")
        for art in artifacts:
            lines.append(f"| {art.get('id', '?')} | {art.get('type', '?')} | {art.get('status', '?')} |")
    else:
        lines.append("_No artifacts yet. Add Research → Decision → Plan → LandingPrompt → TestPrompt._")

    return "\n".join(lines) + "\n"


def build_dependency_graph(status: dict) -> str:
    """Build a text-based dependency graph from all artifacts.

    Format: each line shows one edge as 'A ← B' meaning B depends_on A.
    Grouped by topological layer.
    """
    # Collect all artifact IDs and their depends_on
    all_nodes = {}
    edges = []

    for art in status.get("artifacts", []):
        all_nodes[art["id"]] = art.get("type", "artifact")
        for dep in art.get("depends_on", []):
            edges.append((dep, art["id"]))

    for rf in status.get("research_findings", []):
        all_nodes[rf["id"]] = "research"

    for dec in status.get("decisions", []):
        all_nodes[dec["id"]] = "decision"
        for dep in dec.get("based_on", []):
            edges.append((dep, dec["id"]))

    if not edges:
        if all_nodes:
            return "\n".join(f"- {nid} ({ntype})" for nid, ntype in sorted(all_nodes.items()))
        return "_无依赖关系_"

    # Build adjacency for topological layering
    children = {n: [] for n in all_nodes}
    parents = {n: set() for n in all_nodes}
    for src, dst in edges:
        if src in children:
            children[src].append(dst)
        if dst in parents:
            parents[dst].add(src)

    # Kahn's algorithm for layers
    layers = []
    remaining = set(all_nodes.keys())
    while remaining:
        layer = [n for n in remaining if not parents[n] - (set(all_nodes.keys()) - remaining)]
        if not layer:
            # Cycle detected — dump remaining as-is
            layer = sorted(remaining)
            layers.append(layer)
            break
        layers.append(sorted(layer))
        remaining -= set(layer)

    # Format edges grouped by target
    lines = []
    edge_set = set(edges)
    for layer in layers:
        for node in layer:
            deps_of_node = [src for src, dst in edge_set if dst == node]
            if deps_of_node:
                deps_str = ", ".join(sorted(deps_of_node))
                lines.append(f"{deps_str} ← {node}")
            else:
                lines.append(f"{node} (root)")

    if len(edges) > 15:
        lines.append("")
        lines.append("_(完整依赖图见 status/status.yaml)_")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Render status views")
    parser.add_argument("--project", required=True, help="Project root path")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    status_file = project / "status" / "status.yaml"
    views_dir = project / "views"

    if not status_file.exists():
        print(f"ERROR: {status_file} not found.", file=sys.stderr)
        sys.exit(1)

    with open(status_file, "r", encoding="utf-8") as f:
        status = yaml.safe_load(f)

    views_dir.mkdir(parents=True, exist_ok=True)

    # Render all views
    views = {
        "overview_view.md": render_overview(status),
        "blocker_view.md": render_blocker_view(status),
        "prompt_chain_view.md": render_prompt_chain_view(status),
        "handoff_view.md": render_handoff_view(status),
        "change_log_view.md": render_change_log_view(status),
    }

    for filename, content in views.items():
        path = views_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Rendered: {path}")

    # Render AGENTS.md at project root
    agents_path = project / "AGENTS.md"
    with open(agents_path, "w", encoding="utf-8") as f:
        f.write(render_agents_md(status))
    print(f"  Rendered: {agents_path}")

    print(f"\nAll views regenerated ({len(views)} files + AGENTS.md).")


if __name__ == "__main__":
    main()
