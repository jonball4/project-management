"""Tests for issue_parser module."""

from typing import Dict, List

import networkx as nx

from issue_parser import Issue, build_dependency_graph, handle_cycles, parse_jira_issues


def test_issue_creation():
    """Test Issue object creation."""
    issue = Issue(key="TEST-1", summary="Test issue", status="In Progress", story_points=5.0)
    assert issue.key == "TEST-1"
    assert issue.summary == "Test issue"
    assert issue.status == "In Progress"
    assert issue.story_points == 5.0
    assert not issue.is_complete


def test_issue_completion_status():
    """Test issue completion detection."""
    done_issue = Issue("TEST-1", "Done task", "Done", 3.0)
    assert done_issue.is_complete

    closed_issue = Issue("TEST-2", "Closed task", "Closed", 3.0)
    assert closed_issue.is_complete

    in_progress_issue = Issue("TEST-3", "Active task", "In Progress", 3.0)
    assert not in_progress_issue.is_complete


def test_parse_jira_issues_basic():
    """Test parsing basic Jira issues."""
    raw_issues = [
        {
            "key": "TEST-1",
            "fields": {
                "summary": "First task",
                "status": {"name": "To Do"},
                "customfield_10115": 5,
            },
        },
        {
            "key": "TEST-2",
            "fields": {
                "summary": "Second task",
                "status": {"name": "Done"},
                "customfield_10115": 3,
            },
        },
    ]

    issues = parse_jira_issues(raw_issues)

    assert len(issues) == 2
    assert "TEST-1" in issues
    assert "TEST-2" in issues
    assert issues["TEST-1"].story_points == 5.0
    assert issues["TEST-2"].story_points == 3.0


def test_parse_jira_issues_missing_story_points():
    """Test parsing issues with missing story points."""
    raw_issues = [
        {
            "key": "TEST-1",
            "fields": {
                "summary": "Task without points",
                "status": {"name": "To Do"},
                "customfield_10115": None,
            },
        }
    ]

    issues = parse_jira_issues(raw_issues)
    assert issues["TEST-1"].story_points == 0.0


def test_parse_jira_issues_malformed(capsys):
    """Test parsing malformed Jira issues."""
    raw_issues: List[Dict] = [
        {
            "key": "TEST-1",
            "fields": {
                "summary": "Valid task",
                "status": {"name": "To Do"},
                "customfield_10115": 5,
            },
        },
        {
            "key": "TEST-2",
            # Missing 'fields'
        },
        {
            # Missing 'key'
            "fields": {"summary": "No key", "status": {"name": "To Do"}}
        },
    ]

    issues = parse_jira_issues(raw_issues)

    # Should only parse the valid issue
    assert len(issues) == 1
    assert "TEST-1" in issues

    # Check warning was printed
    captured = capsys.readouterr()
    assert "Skipping malformed issue" in captured.out


def test_build_dependency_graph():
    """Test building dependency graph."""
    issue1 = Issue("TEST-1", "First", "To Do", 5.0)
    issue2 = Issue("TEST-2", "Second", "To Do", 3.0)
    issue3 = Issue("TEST-3", "Third", "Done", 2.0)

    # Set up dependencies
    issue1.blocks.add("TEST-2")
    issue2.blocked_by.add("TEST-1")

    issues = {"TEST-1": issue1, "TEST-2": issue2, "TEST-3": issue3}

    # Build graph excluding completed
    graph = build_dependency_graph(issues, include_completed=False)

    assert graph.number_of_nodes() == 2  # TEST-3 excluded (completed)
    assert graph.has_edge("TEST-1", "TEST-2")
    assert graph.nodes["TEST-1"]["story_points"] == 5.0


def test_handle_cycles():
    """Test cycle detection and handling."""
    # Create a graph with a cycle
    G = nx.DiGraph()
    G.add_node("A", story_points=5)
    G.add_node("B", story_points=3)
    G.add_node("C", story_points=2)

    # Create cycle: A -> B -> C -> A
    G.add_edge("A", "B", weight=5)
    G.add_edge("B", "C", weight=3)
    G.add_edge("C", "A", weight=2)

    # Should not be a DAG
    assert not nx.is_directed_acyclic_graph(G)

    # Handle cycles
    G_fixed = handle_cycles(G)

    # Should now be a DAG
    assert nx.is_directed_acyclic_graph(G_fixed)

    # All nodes should be preserved
    assert G_fixed.number_of_nodes() == 3
    assert "A" in G_fixed.nodes()
    assert "B" in G_fixed.nodes()
    assert "C" in G_fixed.nodes()


def test_handle_cycles_no_cycles():
    """Test handle_cycles with a valid DAG."""
    G = nx.DiGraph()
    G.add_node("A", story_points=5)
    G.add_node("B", story_points=3)
    G.add_edge("A", "B", weight=5)

    # Already a DAG
    assert nx.is_directed_acyclic_graph(G)

    # Should return unchanged
    G_result = handle_cycles(G)
    assert nx.is_directed_acyclic_graph(G_result)
    assert G_result.number_of_nodes() == 2
    assert G_result.number_of_edges() == 1
