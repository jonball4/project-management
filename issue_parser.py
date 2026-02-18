#!/usr/bin/env python3
"""
Issue Parser - Common module for parsing Jira issues and building dependency graphs
"""

from typing import Dict, List, Set, Tuple

import networkx as nx


class Issue:
    """Represents a Jira issue with dependencies"""

    def __init__(
        self, key: str, summary: str, status: str, story_points: float = 0, epic_key: str = None
    ):
        self.key = key
        self.summary = summary
        self.status = status
        self.story_points = story_points
        self.epic_key = epic_key  # Track which epic this issue belongs to
        self.blocks: Set[str] = set()  # Issues this blocks
        self.blocked_by: Set[str] = set()  # Issues blocking this
        self.critical_path_length = 0
        self.earliest_start = 0
        self.is_complete = status.lower() in ["done", "closed", "duplicate", "won't fix"]

    def __repr__(self):
        epic_info = f", epic={self.epic_key}" if self.epic_key else ""
        return f"Issue({self.key}, {self.story_points}pts, status={self.status}{epic_info})"


def parse_jira_issues(
    raw_issues: List[Dict], story_points_field: str = "customfield_10115", epic_key: str = None
) -> Dict[str, Issue]:
    """
    Parse raw Jira issues into Issue objects with dependencies

    Args:
        raw_issues: List of raw issue dictionaries from Jira API
        story_points_field: Custom field ID for story points

    Returns:
        Dictionary mapping issue keys to Issue objects
    """
    issues = {}

    # First pass: Create Issue objects
    for raw in raw_issues:
        # Validate required fields
        if "key" not in raw or "fields" not in raw:
            print(f"⚠️  Skipping malformed issue: {raw.get('key', 'unknown')}")
            continue

        key = raw["key"]
        fields = raw["fields"]

        # Extract story points with fallback
        story_points = fields.get(story_points_field, 0)
        if story_points is None:
            story_points = 0

        # Handle missing fields gracefully
        summary = fields.get("summary", "No summary")
        status_obj = fields.get("status")
        status = status_obj["name"] if status_obj and "name" in status_obj else "Unknown"

        issue = Issue(
            key=key,
            summary=summary,
            status=status,
            story_points=float(story_points),
            epic_key=epic_key,
        )

        issues[key] = issue

    # Second pass: Parse dependencies
    for raw in raw_issues:
        # Skip if issue wasn't parsed in first pass
        if "key" not in raw or raw["key"] not in issues:
            continue

        key = raw["key"]
        issue = issues[key]

        for link in raw.get("fields", {}).get("issuelinks", []):
            link_type = link["type"]["name"].lower()

            # Handle different link types
            if "outwardIssue" in link:
                linked_key = link["outwardIssue"]["key"]
                outward = link["type"]["outward"].lower()

                if "block" in outward or "depend" in link_type:
                    # This issue blocks the linked issue
                    if linked_key in issues:
                        issue.blocks.add(linked_key)
                        issues[linked_key].blocked_by.add(key)

            if "inwardIssue" in link:
                linked_key = link["inwardIssue"]["key"]
                inward = link["type"]["inward"].lower()

                if "block" in inward or "depend" in link_type:
                    # The linked issue blocks this issue
                    if linked_key in issues:
                        issue.blocked_by.add(linked_key)
                        issues[linked_key].blocks.add(key)

    return issues


def build_dependency_graph(issues: Dict[str, Issue], include_completed: bool = False) -> nx.DiGraph:
    """
    Build a NetworkX directed graph from issues

    Args:
        issues: Dictionary of Issue objects
        include_completed: Whether to include completed issues in the graph

    Returns:
        NetworkX DiGraph with story points as node and edge weights
    """
    G = nx.DiGraph()

    # Add nodes
    for key, issue in issues.items():
        if include_completed or not issue.is_complete:
            G.add_node(key, story_points=issue.story_points, issue=issue)

    # Add edges for dependencies
    for key, issue in issues.items():
        if include_completed or not issue.is_complete:
            for blocked_key in issue.blocks:
                if blocked_key in issues:
                    blocked_issue = issues[blocked_key]
                    if include_completed or not blocked_issue.is_complete:
                        # Edge weight is the story points of the source node
                        G.add_edge(key, blocked_key, weight=issue.story_points)

    return G


def handle_cycles(G: nx.DiGraph) -> nx.DiGraph:
    """
    Detect and handle circular dependencies in the graph

    Args:
        G: NetworkX DiGraph

    Returns:
        DAG with cycles removed
    """
    if not nx.is_directed_acyclic_graph(G):
        cycles = list(nx.simple_cycles(G))
        print(f"⚠️  Warning: Found {len(cycles)} circular dependencies!")
        for cycle in cycles[:3]:  # Show first 3
            print(f"   Cycle: {' -> '.join(cycle)}")

        # Preserve all nodes
        nodes_to_preserve = list(G.nodes(data=True))

        # Remove one edge per cycle (the first edge in each cycle)
        edges_to_remove = set()
        for cycle in cycles:
            if len(cycle) > 1:
                edges_to_remove.add((cycle[0], cycle[1]))
                print(f"   Removing edge: {cycle[0]} -> {cycle[1]}")

        # Rebuild graph without problematic edges
        G = nx.DiGraph(
            [(u, v, d) for u, v, d in G.edges(data=True) if (u, v) not in edges_to_remove]
        )

        # Ensure all nodes are preserved
        for node, data in nodes_to_preserve:
            if node not in G:
                G.add_node(node, **data)

    return G


def calculate_critical_path(G: nx.DiGraph) -> Tuple[float, List[str]]:
    """
    Calculate critical path using NetworkX DAG algorithms

    Args:
        G: NetworkX DiGraph (must be a DAG)

    Returns:
        Tuple of (critical_path_length, critical_path_issues)
    """
    if G.number_of_nodes() == 0:
        return 0.0, []

    try:
        # Find the longest path (critical path) using NetworkX
        critical_path = nx.dag_longest_path(G, weight="weight")

        # Calculate total story points along the critical path
        # Include the last node's story points (not counted as an edge weight)
        critical_path_length = nx.dag_longest_path_length(G, weight="weight")
        if critical_path:
            last_node_data = G.nodes[critical_path[-1]]
            last_node_points = last_node_data.get("story_points", 0)
            critical_path_length += last_node_points

        return critical_path_length, critical_path

    except nx.NetworkXError as e:
        print(f"⚠️  Error calculating critical path: {e}")
        return 0.0, []
