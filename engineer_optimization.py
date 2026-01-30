#!/usr/bin/env python3
"""
Engineer Optimization Analysis - Finds optimal team size by analyzing diminishing returns

Analyzes Jira epics to determine the optimal team size before diminishing returns occur.
"""

import argparse
import json
import os
import sys
from typing import Dict, List

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

from issue_parser import (
    build_dependency_graph,
    calculate_critical_path,
    handle_cycles,
    parse_jira_issues,
)
from jira_client import JiraClient
from scheduler import TaskScheduler


def run_simulation(issues: Dict, graph: nx.DiGraph, num_engineers: int) -> Dict:
    """Run scheduling simulation with specified number of engineers"""

    if graph.number_of_nodes() == 0:
        return {"duration": 0, "utilization": [], "total_effort": 0}

    # Get topological order for scheduling
    topo_order = list(nx.topological_sort(graph))

    # Schedule tasks
    scheduler = TaskScheduler(num_engineers)

    for issue_key in topo_order:
        issue = issues[issue_key]
        # Find dependencies that are in the graph
        dependencies = [dep for dep in issue.blocked_by if dep in graph.nodes()]
        scheduler.schedule_task(
            issue_key, issue.story_points, dependencies  # Use story points as duration
        )

    # Calculate metrics
    project_duration = scheduler.get_project_duration()
    utilization = scheduler.get_engineer_utilization()
    total_effort = sum(issue.story_points for issue in issues.values())

    return {
        "duration": project_duration,
        "utilization": utilization,
        "total_effort": total_effort,
        "avg_utilization": np.mean(utilization) if utilization else 0,
        "max_utilization": max(utilization) if utilization else 0,
    }


def analyze_engineer_scaling(
    issues: Dict, graph: nx.DiGraph, max_engineers: int = 12
) -> List[Dict]:
    """Analyze project duration across different team sizes"""

    results = []

    for num_engineers in range(1, max_engineers + 1):
        print(f"Simulating with {num_engineers} engineers...")

        simulation = run_simulation(issues, graph, num_engineers)

        result = {
            "engineers": num_engineers,
            "duration_points": simulation["duration"],
            "total_effort": simulation["total_effort"],
            "avg_utilization": simulation["avg_utilization"],
            "max_utilization": simulation["max_utilization"],
            "efficiency": (
                simulation["total_effort"] / (num_engineers * simulation["duration"])
                if simulation["duration"] > 0
                else 0
            ),
        }

        results.append(result)

    return results


def find_optimal_team_size(results: List[Dict], critical_path_points: float) -> Dict:
    """Find the optimal team size based on diminishing returns analysis"""

    # Calculate time savings per additional engineer
    time_savings = []
    for i in range(1, len(results)):
        prev_duration = results[i - 1]["duration_points"]
        curr_duration = results[i]["duration_points"]
        savings = prev_duration - curr_duration
        time_savings.append(
            {
                "from_engineers": results[i - 1]["engineers"],
                "to_engineers": results[i]["engineers"],
                "time_saved": savings,
                "percent_improvement": (savings / prev_duration * 100) if prev_duration > 0 else 0,
            }
        )

    # Find the "knee" in the curve - where improvement drops below threshold
    improvement_threshold = 5.0  # Less than 5% improvement
    optimal_point = None

    for _, saving in enumerate(time_savings):
        if saving["percent_improvement"] < improvement_threshold:
            optimal_point = saving["from_engineers"]
            break

    # If no clear knee found, use the point where we're within 10% of critical path
    if optimal_point is None:
        target_duration = critical_path_points * 1.1  # 10% buffer above critical path
        for result in results:
            if result["duration_points"] <= target_duration:
                optimal_point = result["engineers"]
                break

    # Default to middle range if still no clear optimum
    if optimal_point is None:
        optimal_point = len(results) // 2

    return {
        "optimal_engineers": optimal_point,
        "time_savings": time_savings,
        "critical_path_points": critical_path_points,
    }


def generate_optimization_chart(results: List[Dict], analysis: Dict, output_file: str):
    """Generate a chart showing engineer count vs project duration"""

    engineers = [r["engineers"] for r in results]
    durations = [r["duration_points"] for r in results]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # Top chart: Duration vs Engineers
    ax1.plot(
        engineers,
        durations,
        "b-o",
        linewidth=2,
        markersize=6,
        label="Project Duration (Story Points)",
    )

    # Add critical path line
    critical_path = analysis["critical_path_points"]
    if critical_path > 0:
        ax1.axhline(
            y=critical_path,
            color="r",
            linestyle=":",
            linewidth=2,
            label=f"Critical Path ({critical_path:.1f} points)",
        )

    # Highlight optimal point
    optimal = analysis["optimal_engineers"]
    optimal_result = next(r for r in results if r["engineers"] == optimal)
    ax1.plot(
        optimal,
        optimal_result["duration_points"],
        "ro",
        markersize=10,
        label=f"Optimal ({optimal} engineers)",
    )

    ax1.set_xlabel("Number of Engineers")
    ax1.set_ylabel("Project Duration (Story Points)")
    ax1.set_title("Project Duration vs Team Size")
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_xticks(engineers)

    # Bottom chart: Efficiency metrics
    efficiencies = [r["efficiency"] * 100 for r in results]  # Convert to percentage
    avg_utilizations = [r["avg_utilization"] for r in results]

    ax2_twin = ax2.twinx()

    ax2.plot(
        engineers, efficiencies, "purple", marker="o", linewidth=2, label="Team Efficiency (%)"
    )
    ax2_twin.plot(
        engineers, avg_utilizations, "orange", marker="s", linewidth=2, label="Avg Utilization (%)"
    )

    ax2.set_xlabel("Number of Engineers")
    ax2.set_ylabel("Team Efficiency (%)", color="purple")
    ax2_twin.set_ylabel("Average Utilization (%)", color="orange")
    ax2.set_title("Team Efficiency and Utilization vs Team Size")
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(engineers)

    # Combine legends
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✅ Optimization chart saved to: {output_file}")


def generate_optimization_report(results: List[Dict], analysis: Dict, epic_key: str = None) -> str:
    """Generate a detailed optimization report"""

    optimal = analysis["optimal_engineers"]
    optimal_result = next(r for r in results if r["engineers"] == optimal)
    critical_path = analysis["critical_path_points"]

    report = ["=" * 70, "ENGINEER OPTIMIZATION ANALYSIS", "=" * 70, ""]

    if epic_key:
        report.append(f"Epic: {epic_key}")
        report.append("")

    report.extend(
        [
            f"📊 OPTIMAL TEAM SIZE: {optimal} Engineers",
            f"   • Project Duration: {optimal_result['duration_points']:.1f} story points",
            f"   • Team Efficiency: {optimal_result['efficiency']:.1%}",
            f"   • Average Utilization: {optimal_result['avg_utilization']:.1f}%",
            "",
            f"🎯 CRITICAL PATH LIMIT: {critical_path:.1f} story points",
            "   • Theoretical minimum with unlimited engineers",
            f"   • Optimal team is {optimal_result['duration_points'] - critical_path:.1f} points above minimum",
            "",
            "📋 FULL ANALYSIS:",
            "-" * 70,
            f"{'Engineers':<10} {'Duration':<12} {'Efficiency':<12} {'Avg Util':<10} {'Savings':<10}",
        ]
    )

    for i, result in enumerate(results):
        savings = ""
        if i > 0:
            time_saved = results[i - 1]["duration_points"] - result["duration_points"]
            savings = f"{time_saved:.1f}pts"

        marker = " ⭐" if result["engineers"] == optimal else ""

        efficiency_str = f"{result['efficiency']:.1%}"
        utilization_str = f"{result['avg_utilization']:.1f}%"

        report.append(
            f"{result['engineers']:<10} "
            f"{result['duration_points']:<12.1f} "
            f"{efficiency_str:<12} "
            f"{utilization_str:<10} "
            f"{savings:<10}"
            f"{marker}"
        )

    report.extend(["", "🔍 DIMINISHING RETURNS ANALYSIS:", "-" * 35])

    for saving in analysis["time_savings"]:
        if saving["time_saved"] > 0:
            report.append(
                f"   {saving['from_engineers']} → {saving['to_engineers']} engineers: "
                f"{saving['time_saved']:.1f} points saved ({saving['percent_improvement']:.1f}% improvement)"
            )
        else:
            report.append(
                f"   {saving['from_engineers']} → {saving['to_engineers']} engineers: "
                f"No improvement (critical path reached)"
            )

    report.extend(
        [
            "",
            "💡 RECOMMENDATIONS:",
            "-" * 20,
            f"• Use {optimal} engineers for optimal cost/time balance",
            f"• Adding more than {optimal} engineers shows diminishing returns",
            f"• Cannot go below {critical_path:.1f} points due to task dependencies",
            "",
        ]
    )

    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze optimal team size for Jira epic or CSV project"
    )
    parser.add_argument(
        "epic_key", nargs="?", help="Epic key (e.g., PX-8350) - if not provided, uses --csv"
    )
    parser.add_argument("--csv", help="Path to CSV file (alternative to epic_key)")
    parser.add_argument(
        "--max-engineers", type=int, default=12, help="Maximum engineers to test (default: 12)"
    )
    parser.add_argument(
        "--output",
        default="engineer-optimization",
        help="Output file prefix (default: engineer-optimization)",
    )
    parser.add_argument(
        "--story-points-field",
        default="customfield_10115",
        help="Jira custom field ID for story points (default: customfield_10115)",
    )
    parser.add_argument(
        "--export-dag", action="store_true", help="Export dependency graph as DOT/PNG"
    )

    args = parser.parse_args()

    # Validate input
    if not args.epic_key and not args.csv:
        parser.error("Either epic_key or --csv must be provided")

    # Create output directory
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # Prepend output directory to output path
    output_prefix = os.path.join(output_dir, args.output)

    try:
        if args.epic_key:
            # Jira mode
            print(f"Fetching issues for epic {args.epic_key}...")
            jira = JiraClient()

            # Search for all issues in the epic
            jql = f"parent = {args.epic_key}"
            fields = [
                "summary",
                "status",
                "issuetype",
                args.story_points_field,
                "issuelinks",
                "parent",
            ]

            raw_issues = jira.search_jql(jql, fields, max_results=500)
            print(f"Found {len(raw_issues)} issues")

            if not raw_issues:
                print(f"❌ No issues found for epic {args.epic_key}")
                sys.exit(1)

            # Parse issues
            issues = parse_jira_issues(raw_issues, args.story_points_field)

            # Filter to incomplete issues only
            incomplete_issues = {k: v for k, v in issues.items() if not v.is_complete}
            print(f"Analyzing {len(incomplete_issues)} incomplete issues")

            if not incomplete_issues:
                print(f"✅ All issues in epic {args.epic_key} are complete!")
                sys.exit(0)

            # Export DAG if requested
            if args.export_dag:
                from dag_exporter import export_dag

                export_dag(issues, f"{args.epic_key.lower()}_optimization_dag.dot")

            issues_to_analyze = incomplete_issues
            epic_key = args.epic_key

        else:
            # CSV mode not supported - use Jira epics
            print("❌ CSV mode is not supported")
            print("   Please provide a Jira epic key as the first argument")
            print("   Example: python3 engineer_optimization.py PX-8350")
            sys.exit(1)

        # Build dependency graph
        print("\nBuilding dependency graph...")
        graph = build_dependency_graph(issues_to_analyze, include_completed=False)
        graph = handle_cycles(graph)

        if graph.number_of_nodes() == 0:
            print("❌ No tasks to analyze")
            sys.exit(1)

        # Calculate critical path
        print("\nCalculating critical path...")
        critical_path_points, critical_path_keys = calculate_critical_path(graph)
        print(f"Critical path: {critical_path_points:.1f} story points")

        # Run scaling analysis
        print(f"\nRunning simulations with 1-{args.max_engineers} engineers...")
        results = analyze_engineer_scaling(issues_to_analyze, graph, args.max_engineers)

        # Find optimal team size
        analysis = find_optimal_team_size(results, critical_path_points)

        # Generate report
        report = generate_optimization_report(results, analysis, epic_key)
        print("\n" + report)

        # Save results to JSON
        output_data = {
            "epic_key": epic_key if args.epic_key else None,
            "results": results,
            "analysis": analysis,
            "metadata": {
                "total_issues": len(issues_to_analyze),
                "critical_path_points": critical_path_points,
                "critical_path_issues": critical_path_keys,
            },
        }

        json_file = f"{output_prefix}.json"
        with open(json_file, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"✅ Detailed results saved to: {json_file}")

        # Generate chart
        chart_file = f"{output_prefix}.png"
        generate_optimization_chart(results, analysis, chart_file)

        print("\n✅ Engineer optimization analysis complete!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
