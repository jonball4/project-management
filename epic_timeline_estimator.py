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


def add_workdays(start: datetime, workdays: float) -> datetime:
    """Advance a date by N workdays, skipping weekends (Sat/Sun)."""
    whole_days = int(workdays)
    current = start
    added = 0
    while added < whole_days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            added += 1
    return current


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

    def get_epic_issues(self, epic_key: str) -> Dict:
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

    def _simulate_workdays_for_run(
        self,
        developers: float,
        points_per_sprint_per_dev: float,
        sprint_weeks: int,
        coordination_factor: float = 0.15,
        variance: float = 0.10,
    ) -> Dict[str, Any]:
        """
        Run one discrete event Monte Carlo simulation iteration.

        Per simulation run:
        1. Apply variance to each work item's story points (fixed for the run)
        2. Compute effective daily capacity per engineer (Brooks's Law applied)
        3. Iterate workday-by-workday:
           - Idle engineers claim the next available ticket (DAG-respecting)
           - Each engineer works on their ticket, reducing remaining work
           - Completed tickets free the engineer for new work
        4. Track when each epic and the overall project complete

        Args:
            developers: Number of developers (fractional OK, ceiled for headcount)
            points_per_sprint_per_dev: Story points each developer completes per sprint
            sprint_weeks: Length of sprint in weeks
            coordination_factor: Brooks's Law overhead factor (default: 0.15)
            variance: Std dev of per-item variance (default: 0.10 = +/-10%)

        Returns:
            Dict with completion_day and epic_completion_days
        """
        # Build the set of issues to simulate (only incomplete ones)
        remaining_keys = [k for k, v in self.issues.items() if not v.is_complete]
        if not remaining_keys:
            return {
                "completion_day": 0,
                "epic_completion_days": {e: 0 for e in self.epic_keys},
            }

        # Apply variance to each work item (fixed for this simulation run)
        remaining_work: Dict[str, float] = {}
        for key in remaining_keys:
            base_pts = self.issues[key].story_points
            factor = max(0.1, random.gauss(1.0, variance))
            remaining_work[key] = base_pts * factor

        # Track completed issues in simulation (start with already-complete ones)
        completed_in_sim: Set[str] = {k for k, v in self.issues.items() if v.is_complete}

        # Compute effective daily capacity per engineer
        workdays_per_sprint = sprint_weeks * 5
        capacity_per_day = points_per_sprint_per_dev / workdays_per_sprint
        efficiency = self._compute_team_efficiency(developers, coordination_factor)
        effective_capacity = capacity_per_day * efficiency

        # Initialize engineers - each tracks their current ticket
        num_engineers = int(math.ceil(developers))
        # current_issue is None when idle, or an issue key when working
        engineer_issue: List[Optional[str]] = [None] * num_engineers

        # Build dependency graph (incomplete issues only)
        G = build_dependency_graph(self.issues, include_completed=False)
        G = handle_cycles(G)

        # Pre-compute downstream descendant count for priority scheduling.
        # Tickets that transitively unblock the most work are picked first.
        remaining_set = set(remaining_keys)
        descendant_count: Dict[str, int] = {}
        for key in remaining_set:
            if key in G:
                descendant_count[key] = len(nx.descendants(G, key))
            else:
                descendant_count[key] = 0

        # Workday loop
        max_workdays = 365 * 2
        epic_completion_days: Dict[str, Optional[int]] = {e: None for e in self.epic_keys}

        for workday in range(1, max_workdays + 1):
            # Phase 1: Assign tickets to idle engineers
            # Collect currently claimed tickets
            claimed = {k for k in engineer_issue if k is not None}

            for eng_idx in range(num_engineers):
                if engineer_issue[eng_idx] is not None:
                    continue  # Engineer is busy

                # Find all available (unblocked, unclaimed) tickets
                available = []
                for key in remaining_set - completed_in_sim - claimed:
                    deps = self.issues[key].blocked_by
                    if deps.issubset(completed_in_sim):
                        available.append(key)

                if not available:
                    continue

                # Pick the ticket that unblocks the most downstream work
                best = max(available, key=lambda k: descendant_count[k])
                engineer_issue[eng_idx] = best
                claimed.add(best)

            # Phase 2: Each engineer works on their ticket
            for eng_idx in range(num_engineers):
                issue_key = engineer_issue[eng_idx]
                if issue_key is None:
                    continue

                # Apply daily capacity to remaining work
                work_done = min(effective_capacity, remaining_work[issue_key])
                remaining_work[issue_key] -= work_done

                # Check if ticket is complete
                if remaining_work[issue_key] <= 0.001:
                    completed_in_sim.add(issue_key)
                    engineer_issue[eng_idx] = None  # Engineer is now idle

            # Phase 3: Check epic completion
            for epic_key in self.epic_keys:
                if epic_completion_days[epic_key] is not None:
                    continue
                epic_issues = self.get_epic_issues(epic_key)
                if epic_issues:
                    epic_remaining = [k for k in epic_issues if k not in completed_in_sim]
                    if not epic_remaining:
                        epic_completion_days[epic_key] = workday

            # Phase 4: Check overall completion
            if all(k in completed_in_sim for k in remaining_keys):
                return {
                    "completion_day": workday,
                    "epic_completion_days": epic_completion_days,
                }

        # Safety limit reached
        return {
            "completion_day": max_workdays,
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
                sprint_weeks=sprint_weeks,
                coordination_factor=coordination_factor,
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

        # Convert workdays to calendar dates (skipping weekends)
        now = datetime.now()
        p50_weeks = p50_workdays / 5
        p85_weeks = p85_workdays / 5
        p95_weeks = p95_workdays / 5

        p50_end_date = add_workdays(now, p50_workdays)
        p85_end_date = add_workdays(now, p85_workdays)
        p95_end_date = add_workdays(now, p95_workdays)

        # Minimum workdays (critical path only, ignores other parallelizable work)
        min_workdays_critical = critical_path_points

        # Compute per-epic summaries for multi-epic analysis
        epic_summaries = {}
        for epic_key in epic_keys:
            epic_issues = self.get_epic_issues(epic_key)
            if epic_issues:
                epic_points = sum(i.story_points for i in epic_issues.values() if not i.is_complete)

                # Get p50/p85/p95 for this epic from the simulation results
                epic_p50_workdays = (
                    epic_workday_results[epic_key][int(len(epic_workday_results[epic_key]) * 0.50)]
                    if epic_workday_results[epic_key]
                    else 0
                )
                epic_p85_workdays = (
                    epic_workday_results[epic_key][int(len(epic_workday_results[epic_key]) * 0.85)]
                    if epic_workday_results[epic_key]
                    else 0
                )
                epic_p95_workdays = (
                    epic_workday_results[epic_key][int(len(epic_workday_results[epic_key]) * 0.95)]
                    if epic_workday_results[epic_key]
                    else 0
                )

                epic_p50_weeks = epic_p50_workdays / 5
                epic_p85_weeks = epic_p85_workdays / 5
                epic_p95_weeks = epic_p95_workdays / 5

                epic_p50_end_date = add_workdays(now, epic_p50_workdays)
                epic_p85_end_date = add_workdays(now, epic_p85_workdays)
                epic_p95_end_date = add_workdays(now, epic_p95_workdays)

                epic_summaries[epic_key] = {
                    "total_points": epic_points,
                    "p50_weeks": round(epic_p50_weeks, 1),
                    "p85_weeks": round(epic_p85_weeks, 1),
                    "p95_weeks": round(epic_p95_weeks, 1),
                    "p50_end_date": epic_p50_end_date.strftime("%Y-%m-%d"),
                    "p85_end_date": epic_p85_end_date.strftime("%Y-%m-%d"),
                    "p95_end_date": epic_p95_end_date.strftime("%Y-%m-%d"),
                    "p50_days": (epic_p50_end_date - now).days,
                    "p85_days": (epic_p85_end_date - now).days,
                    "p95_days": (epic_p95_end_date - now).days,
                }

        return {
            "epic_key": epic_keys[0],
            "epics": epic_keys,
            "epic_summaries": epic_summaries,
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
            "p50_days": (p50_end_date - now).days,
            "p85_days": (p85_end_date - now).days,
            "p95_days": (p95_end_date - now).days,
            "now": now.strftime("%Y-%m-%d"),
        }

    def _print_epic_summary(self, epic_key: str, epic_summary: Dict) -> None:
        """Print summary for a single epic"""
        print(f"\n📌 Epic: {epic_key}")
        print(f"  Total Points: {epic_summary['total_points']:.1f}")
        print(
            f"  p50 (50% confidence): {epic_summary['p50_weeks']:.1f} weeks → {epic_summary['p50_end_date']} ({epic_summary['p50_days']} days)"
        )
        print(
            f"  p85 (85% confidence): {epic_summary['p85_weeks']:.1f} weeks → {epic_summary['p85_end_date']} ({epic_summary['p85_days']} days)"
        )
        print(
            f"  p95 (95% confidence): {epic_summary['p95_weeks']:.1f} weeks → {epic_summary['p95_end_date']} ({epic_summary['p95_days']} days)"
        )

    def print_summary(self, timeline: Dict) -> None:
        """Print a detailed summary of the analysis"""
        is_multi_epic = len(timeline.get("epics", [])) > 1

        title = (
            "MULTI-EPIC TIMELINE ESTIMATION SUMMARY"
            if is_multi_epic
            else "EPIC TIMELINE ESTIMATION SUMMARY"
        )
        title += " (Monte Carlo)"

        print("\n" + "=" * 90)
        print(title)
        print("=" * 90)

        print("\n⚙️  Configuration:")
        epics_display = (
            ", ".join(timeline["epics"])
            if timeline.get("epics")
            else timeline.get("epic_key", "Unknown")
        )
        print(f"  Epics: {epics_display}")
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

        print("\n🎲 Monte Carlo Workday Estimates (1 point ≈ 1 day):")
        print(f"  p50 (50th percentile): {timeline['p50_workdays']:.1f} days")
        print(f"  p85 (85th percentile): {timeline['p85_workdays']:.1f} days")
        print(f"  p95 (95th percentile): {timeline['p95_workdays']:.1f} days")

        print(
            "\n📅 Overall Project Projected Completion Dates (from today: {})".format(
                timeline["now"]
            )
        )
        print(
            f"  p50 (50% confidence): {timeline['p50_weeks']:.1f} weeks → {timeline['p50_end_date']} ({timeline['p50_days']} days)"
        )
        print(
            f"  p85 (85% confidence): {timeline['p85_weeks']:.1f} weeks → {timeline['p85_end_date']} ({timeline['p85_days']} days)"
        )
        print(
            f"  p95 (95% confidence): {timeline['p95_weeks']:.1f} weeks → {timeline['p95_end_date']} ({timeline['p95_days']} days)"
        )

        # Print per-epic summaries if multi-epic
        if timeline.get("epic_summaries"):
            print("\n" + "-" * 90)
            print("📌 Per-Epic Completion Dates:")
            print("-" * 90)
            for epic_key, epic_summary in timeline["epic_summaries"].items():
                self._print_epic_summary(epic_key, epic_summary)

        print(f"\n🔴 Critical Path ({len(timeline['critical_path_issues'])} issues):")
        for i, key in enumerate(timeline["critical_path_issues"], 1):
            issue = self.issues[key]
            epic_info = f" [{issue.epic_key}]" if issue.epic_key else ""
            print(f"  {i}. {key}: {issue.summary} ({issue.story_points} pts){epic_info}")

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
