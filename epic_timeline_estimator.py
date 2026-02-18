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
import math
import random
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union

import networkx as nx

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

        log_factor = math.log2(developers)
        efficiency = 1 / (1 + coordination_factor * log_factor)
        return efficiency

    def _get_available_issues(
        self, issue_state: Dict[str, Dict], started_issues: Set[str]
    ) -> List[str]:
        """
        Get list of issues that can be started (all dependencies complete, not yet started).

        Args:
            issue_state: Dictionary mapping issue_key to state info
            started_issues: Set of issues that have been started

        Returns:
            List of issue keys that can be started now
        """
        available = []
        for issue_key in issue_state.keys():
            if issue_key in started_issues:
                continue
            issue = self.issues[issue_key]
            # Check if all blockers are complete
            all_deps_done = all(
                issue_state.get(blocker_key, {}).get("is_complete", False)
                for blocker_key in issue.blocked_by
            )
            if all_deps_done:
                available.append(issue_key)
        return available

    def _topological_sort_issues(self) -> List[str]:
        """
        Get topological sort of issues for assignment priority.

        Returns:
            List of issue keys in dependency order
        """
        G = build_dependency_graph(self.issues, include_completed=False)
        try:
            return list(nx.topological_sort(G))
        except nx.NetworkXError:
            return list(self.issues.keys())

    def _simulate_workdays_for_run(
        self,
        developers: float,
        points_per_sprint_per_dev: float,
        variance: float = 0.10,
    ) -> Dict[str, Any]:
        """
        Run one discrete event simulation iteration.

        Steps:
        1. Apply variance factor to each work item's story points
        2. Initialize engineers with daily capacity
        3. Iterate workday-by-workday, assigning and completing work
        4. Track epic and overall project completion days

        Args:
            developers: Number of developers
            points_per_sprint_per_dev: Story points per sprint per developer
            variance: Standard deviation of work item variance (default: 0.10 = ±10%)

        Returns:
            Dict with:
            - completion_day: int workdays to complete entire project
            - epic_completion_days: dict[epic_key -> int workday or None]
        """
        # Step 1: Apply variance to all work items
        issue_state = {}
        for issue_key, issue in self.issues.items():
            if issue.is_complete:
                issue_state[issue_key] = {
                    "adjusted_points": 0.0,
                    "remaining_work": 0.0,
                    "completed_day": 0,
                    "epic_key": issue.epic_key,
                    "is_complete": True,
                }
            else:
                variance_factor = random.gauss(1.0, variance)
                variance_factor = max(0.1, variance_factor)  # Floor at 0.1
                adjusted_points = issue.story_points * variance_factor
                issue_state[issue_key] = {
                    "adjusted_points": adjusted_points,
                    "remaining_work": adjusted_points,
                    "completed_day": None,
                    "epic_key": issue.epic_key,
                    "is_complete": False,
                }

        # Step 2: Initialize engineers
        capacity_per_day = points_per_sprint_per_dev / 5.0
        engineers = [
            {"current_issue": None, "remaining_capacity": capacity_per_day}
            for _ in range(int(math.ceil(developers)))
        ]

        # Step 3: Get topological sort for assignment priority
        topo_order = self._topological_sort_issues()

        # Step 4: Workday loop
        workday = 0
        max_workdays = 365 * 2  # Safety limit
        started_issues: Set[str] = set()

        epic_completion_days: Dict[str, Optional[int]] = {epic: None for epic in self.epic_keys}

        while workday < max_workdays:
            workday += 1

            # Assign work to idle engineers
            for engineer in engineers:
                if (
                    engineer["current_issue"] is None
                    or engineer["remaining_capacity"] >= capacity_per_day
                ):
                    # Engineer is ready for new work
                    available = self._get_available_issues(issue_state, started_issues)

                    if available:
                        # Pick next issue from topo order
                        next_issue = None
                        for issue_key in topo_order:
                            if issue_key in available and issue_key not in started_issues:
                                next_issue = issue_key
                                break

                        if next_issue:
                            engineer["current_issue"] = next_issue
                            engineer["remaining_capacity"] = capacity_per_day
                            started_issues.add(next_issue)

            # Do work: reduce remaining_work by engineer capacity
            for engineer in engineers:
                if engineer["current_issue"]:
                    issue_key = engineer["current_issue"]
                    work_done = min(
                        engineer["remaining_capacity"],
                        issue_state[issue_key]["remaining_work"],
                    )
                    issue_state[issue_key]["remaining_work"] -= work_done
                    engineer["remaining_capacity"] -= work_done

                    # Check if issue is complete
                    if issue_state[issue_key]["remaining_work"] <= 0.001:
                        issue_state[issue_key]["is_complete"] = True
                        issue_state[issue_key]["completed_day"] = workday
                        engineer["current_issue"] = None
                        engineer["remaining_capacity"] = capacity_per_day

            # Check for epic completion
            for epic_key in self.epic_keys:
                if epic_completion_days[epic_key] is None:
                    epic_issues = self.get_epic_issues(epic_key)
                    if epic_issues:
                        # Check if all non-completed issues in this epic are done
                        all_epic_done = all(
                            issue_state[key].get("is_complete", False)
                            for key in epic_issues.keys()
                            if not self.issues[key].is_complete
                        )
                        if all_epic_done and any(
                            not self.issues[key].is_complete for key in epic_issues.keys()
                        ):
                            epic_completion_days[epic_key] = workday

            # Check for overall completion
            if all(state["is_complete"] for state in issue_state.values()):
                break

        return {
            "completion_day": workday,
            "epic_completion_days": epic_completion_days,
        }

    def estimate_timeline(
        self,
        epic_keys: Union[List[str], str, None] = None,
        developers: Optional[float] = None,
        points_per_sprint_per_dev: Optional[float] = None,
        sprint_weeks: Optional[int] = None,
        coordination_factor: float = 0.15,
        simulations: int = 10000,
        variance: float = 0.10,
    ) -> Dict:
        """
        Estimate timeline using discrete event Monte Carlo simulation.

        Args:
            epic_keys: List of epic keys being analyzed (for backward compatibility, also accepts single epic_key)
            developers: Number of full-time equivalent developers
            points_per_sprint_per_dev: Story points each developer completes per sprint
            sprint_weeks: Length of sprint in weeks
            coordination_factor: Brooks's Law coordination overhead (default: 0.15, unused in new simulator but kept for compatibility)
            simulations: Number of Monte Carlo iterations (default: 10000)
            variance: Standard deviation of work item variance (default: 0.10 = ±10%)

        Returns:
            Dict with estimates including p50/p85/p95 percentiles and calendar dates
        """
        # Handle backward compatibility - if epic_keys is a string, convert to list
        if isinstance(epic_keys, str):
            epic_keys = [epic_keys]
        assert epic_keys is not None, "epic_keys must be provided"
        assert developers is not None, "developers must be provided"
        assert points_per_sprint_per_dev is not None, "points_per_sprint_per_dev must be provided"
        assert sprint_weeks is not None, "sprint_weeks must be provided"
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

        # Initialize tracking for simulations
        workday_results: List[float] = []
        epic_workday_results: Dict[str, List[float]] = {epic: [] for epic in epic_keys}

        print(f"\nRunning {simulations:,} discrete event Monte Carlo simulations...")
        for _ in range(simulations):
            result = self._simulate_workdays_for_run(
                developers=developers,
                points_per_sprint_per_dev=points_per_sprint_per_dev,
                variance=variance,
            )
            workday_results.append(result["completion_day"])

            for epic_key in epic_keys:
                completion_day = result["epic_completion_days"].get(epic_key)
                if completion_day is not None:
                    epic_workday_results[epic_key].append(completion_day)

        # Sort results for percentile calculation
        workday_results.sort()
        for epic in epic_workday_results:
            epic_workday_results[epic].sort()

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
            "epic_key": epic_keys[0],
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
            epic_keys=args.epic_keys,
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
