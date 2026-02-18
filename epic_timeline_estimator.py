#!/usr/bin/env python3
"""
Epic Timeline Estimator with Monte Carlo Workday Estimation

Analyzes Jira epics to estimate completion timeline based on:
- Story points and dependencies (blockers)
- Team capacity (developers, points per sprint)
- Critical path through dependency graph
- Monte Carlo simulation for probabilistic estimates (p50/p85/p95)
- Brooks's Law coordination overhead factor for team efficiency

Usage:
    python epic_timeline_estimator.py PX-8350 \
        --developers 3.25 \
        --points-per-sprint 8 \
        --sprint-weeks 2 \
        --coordination-factor 0.15 \
        --variance 0.10 \
        --simulations 10000
"""

import argparse
import json
import random
import sys
from datetime import datetime, timedelta
from typing import Dict, List

from issue_parser import (
    build_dependency_graph,
    calculate_critical_path,
    handle_cycles,
    parse_jira_issues,
)
from jira_client import JiraClient


class EpicAnalyzer:
    """Analyzes epic dependencies and estimates timeline with Monte Carlo simulation"""

    def __init__(self, jira_client: JiraClient, story_points_field: str = "customfield_10115"):
        self.jira = jira_client
        self.story_points_field = story_points_field
        self.issues: Dict = {}
        self.epic_keys: List[str] = []  # Track which epics are being analyzed
        self.issues_by_epic: Dict[str, Dict] = {}  # Map epic_key -> issues dict

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

    def fetch_multi_epic_issues(self, epic_keys: List[str]) -> None:
        """Fetch all issues for multiple epics and merge them"""
        print(f"Fetching issues for {len(epic_keys)} epic(s): {', '.join(epic_keys)}...")

        self.epic_keys = epic_keys
        self.issues = {}
        self.issues_by_epic = {}

        for epic_key in epic_keys:
            print(f"\nFetching issues for epic {epic_key}...")

            # Search for all issues in the epic
            jql = f"parent = {epic_key}"
            fields = [
                "summary",
                "status",
                "issuetype",
                self.story_points_field,
                "issuelinks",
                "parent",
            ]

            raw_issues = self.jira.search_jql(jql, fields, max_results=500)
            print(f"Found {len(raw_issues)} issues")

            # Parse issues using common module, passing epic_key
            epic_issues = parse_jira_issues(raw_issues, self.story_points_field, epic_key=epic_key)

            # Store per-epic and merge into main issues dict
            self.issues_by_epic[epic_key] = epic_issues
            self.issues.update(epic_issues)

        print(f"\nTotal issues across all epics: {len(self.issues)}")

    def get_epic_issues(self, epic_key: str) -> Dict[str, object]:
        """Get all issues for a specific epic"""
        return self.issues_by_epic.get(epic_key, {})

    def _compute_team_efficiency(self, developers: float, coordination_factor: float) -> float:
        """
        Compute team efficiency factor based on team size (Brooks's Law).

        efficiency = 1 / (1 + coordination_factor * log2(team_size))

        This gives realistic efficiency degradation:
        - 1 person: 100%
        - 2 people: ~87% (with factor=0.15)
        - 4 people: ~77%
        - 8 people: ~68%

        Args:
            developers: Number of developers
            coordination_factor: Overhead factor (typically 0.15)

        Returns:
            Efficiency multiplier between 0 and 1
        """
        if developers <= 1:
            return 1.0

        import math

        log_factor = math.log2(developers)
        efficiency = 1 / (1 + coordination_factor * log_factor)
        return efficiency

    def _simulate_workdays_for_run(
        self,
        critical_path_points: float,
        total_points: float,
        developers: float,
        coordination_factor: float,
        variance: float = 0.10,
    ) -> float:
        """
        Simulate a single Monte Carlo run for workday estimation.

        For each iteration:
        1. Add stochastic variability to developer capacity (±variance%)
        2. Calculate work days considering both critical path and parallelization
        3. Apply team efficiency degradation

        Args:
            critical_path_points: Sum of story points on critical path
            total_points: Total remaining story points
            developers: Number of developers
            coordination_factor: Brooks's Law overhead factor
            variance: Standard deviation of developer capacity variance (default: 0.10 = ±10%)

        Returns:
            Estimated workdays for this simulation run
        """
        # Add stochastic variability to developer count
        effective_developers = developers * random.gauss(1.0, variance)
        effective_developers = max(0.5, effective_developers)  # Floor at 0.5

        # Calculate team efficiency with coordination overhead
        efficiency = self._compute_team_efficiency(effective_developers, coordination_factor)

        # Work days if work was perfectly parallelizable (total / developers)
        parallel_days = (
            total_points / effective_developers if effective_developers > 0 else float("inf")
        )

        # Work days constrained by critical path (can't parallelize sequential work)
        sequential_days = critical_path_points

        # Actual work days is the maximum of these two constraints
        workdays = max(parallel_days, sequential_days)

        # Apply team efficiency degradation (coordination overhead reduces capacity)
        workdays = workdays / efficiency

        return workdays

    def estimate_timeline(
        self,
        epic_key: str,
        developers: float,
        points_per_sprint_per_dev: float,
        sprint_weeks: int,
        coordination_factor: float = 0.15,
        simulations: int = 10000,
        variance: float = 0.10,
    ) -> Dict:
        """
        Estimate timeline using Monte Carlo simulation with Brooks's Law efficiency.

        Args:
            epic_key: The epic key being analyzed
            developers: Number of full-time equivalent developers
            points_per_sprint_per_dev: Story points each developer completes per sprint
            sprint_weeks: Length of sprint in weeks
            coordination_factor: Brooks's Law coordination overhead (default: 0.15)
            simulations: Number of Monte Carlo iterations (default: 10000)
            variance: Standard deviation of developer capacity variance (default: 0.10 = ±10%)

        Returns:
            Dict with estimates including p50/p85/p95 percentiles and calendar dates
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

        # Deterministic estimates (for comparison)
        print(f"\nRunning {simulations:,} Monte Carlo simulations...")
        min_sprints_parallel = (
            total_points / team_capacity_per_sprint if team_capacity_per_sprint > 0 else 0
        )
        min_sprints_sequential = (
            critical_path_points / team_capacity_per_sprint if team_capacity_per_sprint > 0 else 0
        )
        estimated_sprints_raw = max(min_sprints_parallel, min_sprints_sequential)

        # Monte Carlo simulation for workday-based estimation
        workday_results: List[float] = []
        for _ in range(simulations):
            workdays = self._simulate_workdays_for_run(
                critical_path_points,
                total_points,
                developers,
                coordination_factor,
                variance=variance,
            )
            workday_results.append(workdays)

        # Sort results for percentile calculation
        workday_results.sort()

        # Calculate percentiles
        p50_idx = int(len(workday_results) * 0.50)
        p85_idx = int(len(workday_results) * 0.85)
        p95_idx = int(len(workday_results) * 0.95)

        p50_workdays = workday_results[p50_idx]
        p85_workdays = workday_results[p85_idx]
        p95_workdays = workday_results[p95_idx]

        # Calculate team efficiency for display
        efficiency = self._compute_team_efficiency(developers, coordination_factor)

        # Convert workdays to calendar dates (5 work days per week)
        now = datetime.now()
        p50_weeks = p50_workdays / 5
        p85_weeks = p85_workdays / 5
        p95_weeks = p95_workdays / 5

        p50_end_date = now + timedelta(weeks=p50_weeks)
        p85_end_date = now + timedelta(weeks=p85_weeks)
        p95_end_date = now + timedelta(weeks=p95_weeks)

        # Minimum workdays (critical path only, ignores other parallelizable work)
        min_workdays_critical = critical_path_points

        return {
            "epic_key": epic_key,
            "developers": developers,
            "points_per_sprint_per_dev": points_per_sprint_per_dev,
            "sprint_weeks": sprint_weeks,
            "coordination_factor": coordination_factor,
            "variance": variance,
            "team_efficiency": round(efficiency, 4),
            "simulations": simulations,
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
            # Monte Carlo workday estimates (p50/p85/p95)
            "p50_workdays": round(p50_workdays, 1),
            "p85_workdays": round(p85_workdays, 1),
            "p95_workdays": round(p95_workdays, 1),
            "min_workdays_critical": min_workdays_critical,
            # Calendar projections
            "p50_weeks": round(p50_weeks, 1),
            "p85_weeks": round(p85_weeks, 1),
            "p95_weeks": round(p95_weeks, 1),
            "p50_end_date": p50_end_date.strftime("%Y-%m-%d"),
            "p85_end_date": p85_end_date.strftime("%Y-%m-%d"),
            "p95_end_date": p95_end_date.strftime("%Y-%m-%d"),
            "p50_days": int(p50_weeks * 7),
            "p85_days": int(p85_weeks * 7),
            "p95_days": int(p95_weeks * 7),
            "now": now.strftime("%Y-%m-%d"),
        }

    def print_summary(self, timeline: Dict) -> None:
        """Print a detailed summary of the analysis"""
        print("\n" + "=" * 90)
        print("EPIC TIMELINE ESTIMATION SUMMARY (Monte Carlo)")
        print("=" * 90)

        print("\n⚙️  Configuration:")
        print(f"  Epic: {timeline['epic_key']}")
        print(f"  Team Size: {timeline['developers']:.2f} FTE developers")
        print(f"  Velocity: {timeline['points_per_sprint_per_dev']:.1f} points/sprint/developer")
        print(f"  Sprint Length: {timeline['sprint_weeks']} weeks")
        print(f"  Team Capacity: {timeline['team_capacity_per_sprint']:.1f} points/sprint")
        print(f"  Team Efficiency (coordination): {timeline['team_efficiency']:.1%}")
        print(f"  Brooks's Law Factor: {timeline['coordination_factor']:.2f}")
        print(f"  Developer Capacity Variance: ±{timeline['variance']:.1%}")
        print(f"  Monte Carlo Simulations: {timeline['simulations']:,}")

        print("\n📊 Issue Statistics:")
        print(f"  Total Issues: {timeline['total_issues']}")
        print(f"  Completed: {timeline['completed_issues']}")
        print(f"  Remaining: {timeline['remaining_issues']}")
        if timeline["total_issues"] > 0:
            pct = timeline["completed_issues"] / timeline["total_issues"] * 100
            print(f"  Completion: {pct:.1f}%")

        print("\n📈 Story Points:")
        print(f"  Total Remaining: {timeline['total_points']:.1f} points")
        print(f"  Completed: {timeline['completed_points']:.1f} points")
        print(f"  Critical Path: {timeline['critical_path_points']:.1f} points")

        print("\n⏱️  Sprint-Based Estimates (Deterministic):")
        print(
            f"  Minimum (perfect parallelization): {timeline['min_sprints_parallel']:.2f} sprints"
        )
        print(
            f"  Minimum (critical path constraint): {timeline['min_sprints_sequential']:.2f} sprints"
        )
        print(f"  Estimated (raw): {timeline['estimated_sprints_raw']:.2f} sprints")

        print("\n🎲 Monte Carlo Workday Estimates (1 point = 1 day):")
        print(f"  Minimum (critical path only): {timeline['min_workdays_critical']:.1f} days")
        print(f"  p50 (50th percentile): {timeline['p50_workdays']:.1f} days")
        print(f"  p85 (85th percentile): {timeline['p85_workdays']:.1f} days")
        print(f"  p95 (95th percentile): {timeline['p95_workdays']:.1f} days")

        print("\n📅 Projected Completion Dates (from today: {})".format(timeline["now"]))
        print(
            f"  p50 (50% confidence): {timeline['p50_weeks']:.1f} weeks → {timeline['p50_end_date']} ({timeline['p50_days']} days)"
        )
        print(
            f"  p85 (85% confidence): {timeline['p85_weeks']:.1f} weeks → {timeline['p85_end_date']} ({timeline['p85_days']} days)"
        )
        print(
            f"  p95 (95% confidence): {timeline['p95_weeks']:.1f} weeks → {timeline['p95_end_date']} ({timeline['p95_days']} days)"
        )

        print(f"\n🔴 Critical Path ({len(timeline['critical_path_issues'])} issues):")
        for i, key in enumerate(timeline["critical_path_issues"], 1):
            issue = self.issues[key]
            print(f"  {i}. {key}: {issue.summary} ({issue.story_points} pts)")

        print("\n" + "=" * 90)

    def export_dag(self, filename: str = "epic_dag.dot") -> None:
        """Export dependency graph in DOT format and generate PNG using graphviz library"""
        from dag_exporter import export_dag

        export_dag(self.issues, filename)


def main():
    parser = argparse.ArgumentParser(
        description="Estimate epic timeline with Monte Carlo workday simulation"
    )
    parser.add_argument(
        "epic_keys",
        nargs="+",  # Accept one or more epic keys
        help="Epic key(s) to analyze (e.g., PX-8350 or PX-8350 PX-8351)",
    )
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
        "--coordination-factor",
        type=float,
        default=0.15,
        help="Brooks's Law coordination overhead factor (default: 0.15, gives 2p=87%%, 4p=77%%, 8p=68%%)",
    )
    parser.add_argument(
        "--variance",
        type=float,
        default=0.10,
        help="Standard deviation of developer capacity variance (default: 0.10 = ±10%%)",
    )
    parser.add_argument(
        "--simulations",
        type=int,
        default=10000,
        help="Number of Monte Carlo simulations (default: 10000)",
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
        if len(args.epic_keys) == 1:
            # Single epic - use original method for backward compatibility
            analyzer.fetch_epic_issues(args.epic_keys[0])
        else:
            # Multiple epics - use new multi-epic method
            analyzer.fetch_multi_epic_issues(args.epic_keys)

        if not analyzer.issues:
            print(f"❌ No issues found for epic(s) {', '.join(args.epic_keys)}")
            sys.exit(1)

        # Calculate timeline
        timeline = analyzer.estimate_timeline(
            epic_key=args.epic_keys[0],
            developers=args.developers,
            points_per_sprint_per_dev=args.points_per_sprint,
            sprint_weeks=args.sprint_weeks,
            coordination_factor=args.coordination_factor,
            variance=args.variance,
            simulations=args.simulations,
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
