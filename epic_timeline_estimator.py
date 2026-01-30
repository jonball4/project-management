#!/usr/bin/env python3
"""
Epic Timeline Estimator with Critical Path Analysis

Analyzes Jira epics to estimate completion timeline based on:
- Story points and dependencies (blockers)
- Team capacity (developers, points per sprint)
- Critical path through dependency graph

Usage:
    python epic_timeline_estimator.py PX-8350 --developers 3.25 --points-per-sprint 8 --sprint-weeks 2
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Dict

from issue_parser import (
    build_dependency_graph,
    calculate_critical_path,
    handle_cycles,
    parse_jira_issues,
)
from jira_client import JiraClient


class EpicAnalyzer:
    """Analyzes epic dependencies and estimates timeline"""

    def __init__(
        self, jira_client: JiraClient, story_points_field: str = "customfield_10115"
    ):
        self.jira = jira_client
        self.story_points_field = story_points_field
        self.issues: Dict = {}

    def fetch_epic_issues(self, epic_key: str) -> None:
        """Fetch all issues for an epic"""
        print(f"Fetching issues for epic {epic_key}...")

        # Search for all issues in the epic (using parent hierarchy)
        jql = f"parent = {epic_key}"
        fields = ["summary", "status", "issuetype", self.story_points_field, "issuelinks", "parent"]

        raw_issues = self.jira.search_jql(jql, fields, max_results=500)
        print(f"Found {len(raw_issues)} issues")

        # Parse issues using common module
        self.issues = parse_jira_issues(raw_issues, self.story_points_field)

    def estimate_timeline(
        self,
        epic_key: str,
        developers: float,
        points_per_sprint_per_dev: float,
        sprint_weeks: int,
        buffer_percent: float = 20.0,
    ) -> Dict:
        """
        Estimate timeline considering parallelization and team capacity

        Args:
            epic_key: The epic key being analyzed
            developers: Number of full-time equivalent developers
            points_per_sprint_per_dev: Story points each developer completes per sprint
            sprint_weeks: Length of sprint in weeks
            buffer_percent: Buffer percentage for overhead/uncertainty
        """
        print("\nEstimating timeline...")

        # Calculate totals
        total_points = sum(i.story_points for i in self.issues.values() if not i.is_complete)
        completed_points = sum(i.story_points for i in self.issues.values() if i.is_complete)

        # Team capacity per sprint
        team_capacity_per_sprint = developers * points_per_sprint_per_dev

        # Build graph and calculate critical path using common modules
        print("\nCalculating critical path...")
        G = build_dependency_graph(self.issues, include_completed=False)
        G = handle_cycles(G)
        critical_path_points, critical_path_keys = calculate_critical_path(G)

        # Theoretical minimum sprints (perfect parallelization)
        min_sprints_parallel = (
            total_points / team_capacity_per_sprint if team_capacity_per_sprint > 0 else 0
        )

        # Critical path constraint (no parallelization possible on critical path)
        min_sprints_sequential = (
            critical_path_points / team_capacity_per_sprint if team_capacity_per_sprint > 0 else 0
        )

        # Actual estimate is the maximum of these two constraints
        estimated_sprints_raw = max(min_sprints_parallel, min_sprints_sequential)

        # Add buffer
        estimated_sprints_with_buffer = estimated_sprints_raw * (1 + buffer_percent / 100)

        # Convert to weeks and calendar time
        estimated_weeks = estimated_sprints_with_buffer * sprint_weeks
        estimated_end_date = datetime.now() + timedelta(weeks=estimated_weeks)

        # Work-days calculation (assuming 1 day per story point)
        work_days_parallel = total_points / developers if developers > 0 else 0
        work_days_sequential = critical_path_points  # Critical path can't be parallelized
        work_days_estimate = max(work_days_parallel, work_days_sequential)
        work_days_with_buffer = work_days_estimate * (1 + buffer_percent / 100)

        # Convert work days to calendar time (assuming 5 work days per week)
        work_weeks = work_days_with_buffer / 5
        work_calendar_end = datetime.now() + timedelta(weeks=work_weeks)

        return {
            "epic_key": epic_key,
            "developers": developers,
            "points_per_sprint_per_dev": points_per_sprint_per_dev,
            "sprint_weeks": sprint_weeks,
            "total_issues": len(self.issues),
            "completed_issues": sum(1 for i in self.issues.values() if i.is_complete),
            "remaining_issues": sum(1 for i in self.issues.values() if not i.is_complete),
            "total_points": total_points,
            "completed_points": completed_points,
            "critical_path_points": critical_path_points,
            "critical_path_issues": critical_path_keys,
            "team_capacity_per_sprint": team_capacity_per_sprint,
            "min_sprints_parallel": min_sprints_parallel,
            "min_sprints_sequential": min_sprints_sequential,
            "estimated_sprints_raw": estimated_sprints_raw,
            "buffer_percent": buffer_percent,
            "estimated_sprints_with_buffer": estimated_sprints_with_buffer,
            "estimated_weeks": estimated_weeks,
            "estimated_end_date": estimated_end_date.strftime("%Y-%m-%d"),
            "days_until_completion": int(estimated_weeks * 7),
            "work_days_parallel": work_days_parallel,
            "work_days_sequential": work_days_sequential,
            "work_days_estimate": work_days_estimate,
            "work_days_with_buffer": work_days_with_buffer,
            "work_weeks": work_weeks,
            "work_calendar_end": work_calendar_end.strftime("%Y-%m-%d"),
        }

    def print_summary(self, timeline: Dict) -> None:
        """Print a detailed summary of the analysis"""
        print("\n" + "=" * 80)
        print("EPIC TIMELINE ESTIMATION SUMMARY")
        print("=" * 80)

        print("\n⚙️  Configuration:")
        print(f"  Epic: {timeline['epic_key']}")
        print(f"  Team Size: {timeline['developers']:.2f} FTE developers")
        print(f"  Velocity: {timeline['points_per_sprint_per_dev']:.1f} points/sprint/developer")
        print(f"  Sprint Length: {timeline['sprint_weeks']} weeks")
        print(f"  Team Capacity: {timeline['team_capacity_per_sprint']:.1f} points/sprint")
        print(f"  Overhead Buffer: {timeline['buffer_percent']:.0f}%")

        print("\n📊 Issue Statistics:")
        print(f"  Total Issues: {timeline['total_issues']}")
        print(f"  Completed: {timeline['completed_issues']}")
        print(f"  Remaining: {timeline['remaining_issues']}")
        print(f"  Completion: {timeline['completed_issues'] / timeline['total_issues'] * 100:.1f}%")

        print("\n📈 Story Points:")
        print(f"  Total Remaining: {timeline['total_points']:.1f} points")
        print(f"  Completed: {timeline['completed_points']:.1f} points")
        print(f"  Critical Path: {timeline['critical_path_points']:.1f} points")

        print("\n⏱️  Sprint-Based Estimates:")
        print(
            f"  Minimum (perfect parallelization): {timeline['min_sprints_parallel']:.2f} sprints"
        )
        print(
            f"  Minimum (critical path constraint): {timeline['min_sprints_sequential']:.2f} sprints"
        )
        print(f"  Estimated (raw): {timeline['estimated_sprints_raw']:.2f} sprints")
        print(
            f"  Estimated (with {timeline['buffer_percent']:.0f}% buffer): {timeline['estimated_sprints_with_buffer']:.2f} sprints"
        )
        print(
            f"  Calendar Time: {timeline['estimated_weeks']:.1f} weeks ({timeline['days_until_completion']} days)"
        )
        print(f"  Target Completion: {timeline['estimated_end_date']}")

        print("\n📆 Work-Days Estimate (1 point = 1 day):")
        print(f"  Minimum (parallel): {timeline['work_days_parallel']:.1f} work days")
        print(f"  Minimum (sequential): {timeline['work_days_sequential']:.1f} work days")
        print(f"  Estimated (raw): {timeline['work_days_estimate']:.1f} work days")
        print(
            f"  Estimated (with {timeline['buffer_percent']:.0f}% buffer): {timeline['work_days_with_buffer']:.1f} work days"
        )
        print(f"  Calendar Time: {timeline['work_weeks']:.1f} weeks")
        print(f"  Target Completion: {timeline['work_calendar_end']}")

        print(f"\n🔴 Critical Path ({len(timeline['critical_path_issues'])} issues):")
        for i, key in enumerate(timeline["critical_path_issues"], 1):
            issue = self.issues[key]
            print(f"  {i}. {key}: {issue.summary} ({issue.story_points} pts)")

        print("\n" + "=" * 80)

    def export_dag(self, filename: str = "epic_dag.dot") -> None:
        """Export dependency graph in DOT format and generate PNG using graphviz library"""
        from dag_exporter import export_dag

        export_dag(self.issues, filename)


def main():
    parser = argparse.ArgumentParser(
        description="Estimate epic timeline with critical path analysis"
    )
    parser.add_argument("epic_key", help="Epic key (e.g., PX-8350)")
    parser.add_argument(
        "--developers", type=float, default=3.25, help="Number of FTE developers (default: 3.25)"
    )
    parser.add_argument(
        "--points-per-sprint",
        type=float,
        default=8,
        help="Story points per sprint per developer (default: 8)",
    )
    parser.add_argument(
        "--sprint-weeks", type=int, default=2, help="Sprint length in weeks (default: 2)"
    )
    parser.add_argument(
        "--buffer", type=float, default=20.0, help="Buffer percentage for overhead (default: 20)"
    )
    parser.add_argument(
        "--export-dag", action="store_true", help="Export dependency graph as DOT file"
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    try:
        # Initialize client and analyzer
        jira = JiraClient()
        analyzer = EpicAnalyzer(jira)

        # Fetch and analyze
        analyzer.fetch_epic_issues(args.epic_key)

        if not analyzer.issues:
            print(f"❌ No issues found for epic {args.epic_key}")
            sys.exit(1)

        # Calculate timeline
        timeline = analyzer.estimate_timeline(
            epic_key=args.epic_key,
            developers=args.developers,
            points_per_sprint_per_dev=args.points_per_sprint,
            sprint_weeks=args.sprint_weeks,
            buffer_percent=args.buffer,
        )

        # Output results
        if args.json:
            print(json.dumps(timeline, indent=2))
        else:
            analyzer.print_summary(timeline)

        # Export DAG if requested
        if args.export_dag:
            analyzer.export_dag()

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
