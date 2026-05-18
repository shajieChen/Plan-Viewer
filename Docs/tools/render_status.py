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


def topological_sort_lps(artifacts: list) -> list:
    """Sort landing_prompt artifacts by depends_on topology.

    Only considers LP-to-LP dependencies. Non-LP dependencies are ignored
    for ordering purposes. Falls back to alphabetical on cycle detection.
    """
    lps = [a for a in artifacts if a.get("type") == "landing_prompt"]
    if not lps:
        return []

    lp_ids = {a["id"] for a in lps}
    # Build graph of LP-to-LP edges only
    in_degree = {a["id"]: 0 for a in lps}
    children = {a["id"]: [] for a in lps}

    for a in lps:
        for dep in a.get("depends_on", []):
            if dep in lp_ids:
                in_degree[a["id"]] += 1
                children[dep].append(a["id"])

    # Kahn's algorithm
    queue = sorted([nid for nid, deg in in_degree.items() if deg == 0])
    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for child in sorted(children[node]):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
        queue.sort()

    if len(result) != len(lps):
        # Cycle detected - fallback to alphabetical
        return sorted(lp_ids)

    return result


def render_project_readme(status: dict, project: Path) -> str:
    """Render the PST project root README.md.

    Contains: directory tree, artifact table, dependency graph,
    handoff contexts, blockers, and quick navigation links.
    """
    meta = status.get("meta", {})
    project_name = meta.get("project_name", "Unknown")
    last_updated = meta.get("last_updated", "N/A")

    lines = [
        f"# {project_name} \u2014 Project State Overview",
        "",
        "> Auto-generated by project-state-tracker. Do not hand-edit.",
        f"> Last updated: {last_updated}",
        "",
    ]

    # --- Directory tree ---
    lines.append("## \u76ee\u5f55\u7ed3\u6784")
    lines.append("")
    lines.append("```")

    dir_descriptions = {
        "research": "\u8c03\u7814\u4e8b\u5b9e\u4e0e\u8bc1\u636e",
        "decisions": "\u57fa\u4e8e\u8c03\u7814\u7684\u51b3\u7b56",
        "plan": "\u6267\u884c\u8ba1\u5212\u4e0e\u8bbe\u8ba1",
        "prompts/landing": "\u5b9e\u65bd Prompt",
        "prompts/test": "\u9a8c\u8bc1 Prompt",
        "status": "\u72b6\u6001\u5355\u4e00\u771f\u76f8\u6e90",
        "views": "\u53ea\u8bfb\u6d3e\u751f\u89c6\u56fe",
        "tools": "Python \u72b6\u6001\u7ba1\u7406\u811a\u672c",
    }

    for dir_rel, desc in dir_descriptions.items():
        dir_path = project / dir_rel
        if dir_path.exists():
            file_count = len([
                f for f in dir_path.iterdir()
                if f.is_file() and f.name != ".gitkeep"
            ])
            lines.append(f"{dir_rel + '/': <20} \u2014 {desc} ({file_count} files)")
        else:
            lines.append(f"{dir_rel + '/': <20} \u2014 {desc} (not created)")

    lines.append("```")
    lines.append("")

    # --- Artifact table ---
    lines.append("## Artifact \u72b6\u6001\u603b\u89c8")
    lines.append("")

    all_artifacts = []
    for art in status.get("artifacts", []):
        all_artifacts.append(art)
    for rf in status.get("research_findings", []):
        all_artifacts.append({"id": rf["id"], "type": "research",
                              "status": rf.get("status", "?"),
                              "path": rf.get("path", "?")})
    for dec in status.get("decisions", []):
        all_artifacts.append({"id": dec["id"], "type": "decision",
                              "status": dec.get("status", "?"),
                              "path": dec.get("path", "?")})

    if all_artifacts:
        lines.append("| ID | Type | Status | Path |")
        lines.append("|----|------|--------|------|")
        for art in sorted(all_artifacts, key=lambda a: a.get("id", "")):
            lines.append(
                f"| {art.get('id', '?')} | {art.get('type', '?')} "
                f"| {art.get('status', '?')} | {art.get('path', '?')} |"
            )
    else:
        lines.append("_\u65e0\u5df2\u6ce8\u518c artifact_")

    lines.append("")

    # --- Dependency graph ---
    lines.append("## \u4f9d\u8d56\u5173\u7cfb\u56fe")
    lines.append("")
    lines.append("```")
    lines.append(build_dependency_graph(status))
    lines.append("```")
    lines.append("")

    # --- Handoff contexts ---
    lines.append("## Handoff \u4e0a\u4e0b\u6587")
    lines.append("")
    handoffs = status.get("handoff_contexts", [])
    if handoffs:
        lines.append("| HC | Producer | Status | Version | Consumers |")
        lines.append("|----|----------|--------|---------|-----------|")
        for hc in handoffs:
            consumers = ", ".join(hc.get("consumed_by", []))
            lines.append(
                f"| {hc.get('id', '?')} | {hc.get('producer', '?')} | "
                f"{hc.get('status', '?')} | {hc.get('version', 0)} | {consumers} |"
            )
    else:
        lines.append("_\u65e0\u6d3b\u8dc3 handoff_")

    lines.append("")

    # --- Blockers ---
    lines.append("## Blockers")
    lines.append("")
    blockers = [b for b in status.get("blockers", []) if b.get("status") == "open"]
    if blockers:
        lines.append("| ID | Title | Severity | Blocks |")
        lines.append("|----|-------|----------|--------|")
        for b in blockers:
            blocks_str = ", ".join(b.get("blocks", []))
            lines.append(
                f"| {b.get('id', '?')} | {b.get('title', '?')} "
                f"| {b.get('severity', '?')} | {blocks_str} |"
            )
    else:
        lines.append("_\u65e0\u963b\u585e\u9879_")

    lines.append("")

    # --- Quick navigation ---
    lines.append("## \u5feb\u901f\u5bfc\u822a")
    lines.append("")
    lines.append("- \u5b8c\u6574\u72b6\u6001\u6570\u636e: `status/status.yaml`")
    lines.append("- \u53d8\u66f4\u65e5\u5fd7: `views/change_log_view.md`")
    lines.append("- Prompt \u6267\u884c\u94fe: `views/prompt_chain_view.md`")
    lines.append("- Handoff \u72b6\u6001: `views/handoff_view.md`")
    lines.append("- Agent \u7d22\u5f15: `AGENTS.md`")

    return "\n".join(lines) + "\n"


def render_landing_readme(status: dict, project: Path) -> str:
    """Render prompts/landing/README.md with ELP-compatible front-matter.

    Returns full content (front-matter + body). The caller uses
    write_with_frontmatter_preservation() to handle existing files.
    """
    meta = status.get("meta", {})
    project_name = meta.get("project_name", "Unknown")
    last_updated = meta.get("last_updated", "N/A")
    source_root = meta.get("source_root", "<未配置>")
    scope = meta.get("scope", [source_root] if source_root != "<未配置>" else [])
    pst_root = meta.get("pst_root", str(project))
    coding_standards = meta.get("coding_standards")

    # --- Generate front-matter ---
    fm_lines = [
        "---",
        f'source_root: "{source_root}"',
        "scope:",
    ]
    for s in scope:
        fm_lines.append(f'  - "{s}"')
    fm_lines.append(f'pst_root: "{pst_root}"')
    fm_lines.append("---")

    frontmatter = "\n".join(fm_lines)

    # --- Generate body ---
    body_lines = [
        f"# {project_name} LandingPrompt",
        "",
        "> Auto-generated body by project-state-tracker. Front-matter preserved if pre-existing.",
        f"> Last updated: {last_updated}",
        "",
    ]

    # LP sequence
    body_lines.append("## LP 序列")
    body_lines.append("")
    artifacts = status.get("artifacts", [])
    lp_order = topological_sort_lps(artifacts)
    if lp_order:
        body_lines.append(" -> ".join(lp_order))
    else:
        body_lines.append("_尚无已注册的 Landing Prompt_")
    body_lines.append("")

    # Coding Standards (only if configured)
    if coding_standards:
        body_lines.append("## Coding Standards")
        body_lines.append("")
        body_lines.append(coding_standards)
        body_lines.append("")

    # LP status table
    body_lines.append("## 当前 LP 状态")
    body_lines.append("")
    lps = [a for a in artifacts if a.get("type") == "landing_prompt"]
    if lps:
        body_lines.append("| ID | Status | Depends On | Produces HC |")
        body_lines.append("|----|--------|------------|-------------|")
        for lp in sorted(lps, key=lambda a: a.get("id", "")):
            deps = ", ".join(lp.get("depends_on", []))
            hcs = ", ".join(lp.get("produces_handoffs", []))
            body_lines.append(f"| {lp['id']} | {lp.get('status', '?')} | {deps} | {hcs} |")
    else:
        body_lines.append("_尚无已注册的 Landing Prompt_")
    body_lines.append("")

    # Handoff summary
    body_lines.append("## Handoff 上下文摘要")
    body_lines.append("")
    handoffs = status.get("handoff_contexts", [])
    if handoffs:
        body_lines.append("| HC | Facts | Constraints | Consumed By |")
        body_lines.append("|----|-------|-------------|-------------|")
        for hc in handoffs:
            facts_str = "; ".join(hc.get("facts", []))
            constraints_str = "; ".join(hc.get("constraints", []))
            consumed_str = ", ".join(hc.get("consumed_by", []))
            body_lines.append(
                f"| {hc.get('id', '?')} | {facts_str} | {constraints_str} | {consumed_str} |"
            )
    else:
        body_lines.append("_无活跃 handoff_")

    body = "\n".join(body_lines) + "\n"

    return frontmatter + "\n\n" + body


def write_with_frontmatter_preservation(path: Path, new_content: str) -> None:
    """Write README, preserving existing YAML front-matter if present.

    new_content may include its own front-matter (generated from meta).
    If the file already exists with user-written front-matter, the existing
    front-matter is preserved and only the body from new_content is used.

    If the file doesn't exist or has no front-matter, writes new_content as-is.
    """
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing.startswith("---"):
            # Find the closing '---' in existing file
            second_marker = existing.find("---", 3)
            if second_marker != -1:
                frontmatter = existing[: second_marker + 3]
                # Extract body from new_content (skip its front-matter if present)
                new_body = new_content
                if new_content.startswith("---"):
                    new_second = new_content.find("---", 3)
                    if new_second != -1:
                        new_body = new_content[new_second + 3:].lstrip("\n")
                final = frontmatter + "\n\n" + new_body
                path.write_text(final, encoding="utf-8")
                return

    # No existing file or no front-matter — write as-is
    path.write_text(new_content, encoding="utf-8")


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

    # Render project root README.md
    readme_content = render_project_readme(status, project)
    readme_path = project / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"  Rendered: {readme_path}")

    # Render prompts/landing/README.md (with front-matter preservation)
    landing_dir = project / "prompts" / "landing"
    landing_dir.mkdir(parents=True, exist_ok=True)
    landing_readme_path = landing_dir / "README.md"
    landing_full_content = render_landing_readme(status, project)
    write_with_frontmatter_preservation(landing_readme_path, landing_full_content)
    print(f"  Rendered: {landing_readme_path}")

    print(f"\nAll views regenerated ({len(views)} files + AGENTS.md + 2 READMEs).")


if __name__ == "__main__":
    main()
