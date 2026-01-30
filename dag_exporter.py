#!/usr/bin/env python3
"""
DAG Exporter - Common module for exporting dependency graphs
"""

from typing import Dict

from issue_parser import Issue


def export_dag(issues: Dict[str, Issue], filename: str = "epic_dag.dot") -> None:
    """Export dependency graph in DOT format and generate PNG using graphviz library"""
    try:
        from graphviz import Digraph
    except ImportError:
        print("⚠️  graphviz library not installed. Install with: pip install graphviz")
        print("   Exporting DOT file only...")
        _export_dot_only(issues, filename)
        return

    print(f"\nExporting DAG to {filename}...")

    # Create graph using graphviz library
    dot = Digraph(comment="Epic Dependencies")
    dot.attr(rankdir="LR")
    dot.attr("node", shape="box")

    # Add nodes with color coding by status
    for key, issue in issues.items():
        color = "lightgreen" if issue.is_complete else "lightblue"
        label = f"{key}\n{issue.story_points} pts\n{issue.status}"
        dot.node(key, label=label, style="filled", fillcolor=color)

    # Add edges
    for key, issue in issues.items():
        for blocked_key in issue.blocks:
            if blocked_key in issues:
                dot.edge(key, blocked_key)

    # Save DOT file
    dot_path = filename.replace(".dot", "")
    dot.save(filename)
    print(f"✅ Exported DOT file to {filename}")

    # Generate PNG
    try:
        dot.render(dot_path, format="png", cleanup=False)
        print(f"✅ Generated image: {dot_path}.png")
    except Exception as e:
        print(f"⚠️  Failed to generate PNG: {e}")
        print("   Make sure Graphviz is installed: brew install graphviz")


def _export_dot_only(issues: Dict[str, Issue], filename: str) -> None:
    """Fallback: Export only DOT file without graphviz library"""
    with open(filename, "w") as f:
        f.write("digraph EpicDependencies {\n")
        f.write("  rankdir=LR;\n")
        f.write("  node [shape=box];\n\n")

        # Color code by status
        for key, issue in issues.items():
            color = "lightgreen" if issue.is_complete else "lightblue"
            label = f"{key}\\n{issue.story_points} pts\\n{issue.status}"
            f.write(f'  "{key}" [label="{label}", style=filled, fillcolor={color}];\n')

        f.write("\n")

        # Add edges
        for key, issue in issues.items():
            for blocked_key in issue.blocks:
                if blocked_key in issues:
                    f.write(f'  "{key}" -> "{blocked_key}";\n')

        f.write("}\n")

    print(f"✅ Exported DOT file to {filename}")
