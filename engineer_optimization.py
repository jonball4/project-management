#!/usr/bin/env python3
"""
Engineer Optimization Analysis - Finds optimal team size by analyzing diminishing returns
"""

import argparse
import csv
import logging
import sys
from typing import Dict, List
from datetime import datetime
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import json

# Import from effort_estimator
from effort_estimator import (
    TaskScheduler, parse_csv, build_dependency_graph, 
    add_business_days, get_next_business_day
)


def run_simulation(tasks: List[Dict], graph: nx.DiGraph, num_engineers: int) -> Dict:
    """Run scheduling simulation with specified number of engineers"""
    
    # Filter schedulable tasks
    schedulable_tasks = [task for task in tasks if task['days'] is not None]
    
    if not schedulable_tasks:
        return {'duration': 0, 'utilization': [], 'total_effort': 0}
    
    # Get topological order for scheduling
    topo_order = list(nx.topological_sort(graph))
    
    # Schedule tasks
    scheduler = TaskScheduler(num_engineers)
    tasks_by_name = {task['name']: task for task in tasks}
    
    for task_name in topo_order:
        task_data = tasks_by_name[task_name]
        if task_data['days'] is not None:  # Only schedule tasks with known duration
            dependencies = [dep for dep in task_data['dependencies'] 
                          if tasks_by_name[dep]['days'] is not None]
            scheduler.schedule_task(
                task_name, 
                task_data['days'], 
                dependencies
            )
    
    # Calculate metrics
    project_duration = scheduler.get_project_duration()
    utilization = scheduler.get_engineer_utilization()
    total_effort = sum(task['days'] for task in schedulable_tasks if task['days'])
    
    # Calculate calendar duration
    start_datetime = datetime.now()
    start_date = get_next_business_day(start_datetime)
    end_datetime = add_business_days(start_date, project_duration)
    calendar_duration = (end_datetime.date() - start_date.date()).days + 1
    
    return {
        'duration': project_duration,
        'calendar_duration': calendar_duration,
        'utilization': utilization,
        'total_effort': total_effort,
        'avg_utilization': np.mean(utilization) if utilization else 0,
        'max_utilization': max(utilization) if utilization else 0
    }


def analyze_engineer_scaling(tasks: List[Dict], graph: nx.DiGraph, 
                           max_engineers: int = 12) -> List[Dict]:
    """Analyze project duration across different team sizes"""
    
    results = []
    
    for num_engineers in range(1, max_engineers + 1):
        logging.info(f"Simulating with {num_engineers} engineers...")
        
        simulation = run_simulation(tasks, graph, num_engineers)
        
        result = {
            'engineers': num_engineers,
            'duration_days': simulation['duration'],
            'calendar_days': simulation['calendar_duration'],
            'total_effort': simulation['total_effort'],
            'avg_utilization': simulation['avg_utilization'],
            'max_utilization': simulation['max_utilization'],
            'efficiency': simulation['total_effort'] / (num_engineers * simulation['duration']) if simulation['duration'] > 0 else 0
        }
        
        results.append(result)
        
        logging.debug(f"  Duration: {result['duration_days']} days, "
                     f"Avg Util: {result['avg_utilization']:.1f}%, "
                     f"Efficiency: {result['efficiency']:.2f}")
    
    return results


def calculate_critical_path_duration(graph: nx.DiGraph) -> int:
    """Calculate the theoretical minimum duration (critical path)"""
    try:
        # Find tasks with no successors (end tasks)
        end_tasks = [node for node in graph.nodes() if graph.out_degree(node) == 0]
        max_path_duration = 0
        
        for end_task in end_tasks:
            # Find longest path to this end task
            for start_task in graph.nodes():
                if graph.in_degree(start_task) == 0:  # Start tasks
                    try:
                        path = nx.shortest_path(graph, start_task, end_task)
                        path_duration = sum(
                            graph.nodes[task].get('days', 0) or 0 
                            for task in path
                        )
                        max_path_duration = max(max_path_duration, path_duration)
                    except nx.NetworkXNoPath:
                        continue
        
        return max_path_duration
    except Exception as e:
        logging.warning(f"Could not calculate critical path: {e}")
        return 0


def find_optimal_team_size(results: List[Dict], critical_path_duration: int) -> Dict:
    """Find the optimal team size based on diminishing returns analysis"""
    
    # Calculate time savings per additional engineer
    time_savings = []
    for i in range(1, len(results)):
        prev_duration = results[i-1]['duration_days']
        curr_duration = results[i]['duration_days']
        savings = prev_duration - curr_duration
        time_savings.append({
            'from_engineers': results[i-1]['engineers'],
            'to_engineers': results[i]['engineers'],
            'time_saved': savings,
            'percent_improvement': (savings / prev_duration * 100) if prev_duration > 0 else 0
        })
    
    # Find the "knee" in the curve - where improvement drops below threshold
    improvement_threshold = 5.0  # Less than 5% improvement
    optimal_point = None
    
    for i, saving in enumerate(time_savings):
        if saving['percent_improvement'] < improvement_threshold:
            optimal_point = saving['from_engineers']
            break
    
    # If no clear knee found, use the point where we're within 10% of critical path
    if optimal_point is None:
        target_duration = critical_path_duration * 1.1  # 10% buffer above critical path
        for result in results:
            if result['duration_days'] <= target_duration:
                optimal_point = result['engineers']
                break
    
    # Default to middle range if still no clear optimum
    if optimal_point is None:
        optimal_point = len(results) // 2
    
    return {
        'optimal_engineers': optimal_point,
        'time_savings': time_savings,
        'critical_path_duration': critical_path_duration
    }


def generate_optimization_chart(results: List[Dict], analysis: Dict, output_file: str):
    """Generate a chart showing engineer count vs project duration"""
    
    engineers = [r['engineers'] for r in results]
    durations = [r['duration_days'] for r in results]
    calendar_durations = [r['calendar_days'] for r in results]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Top chart: Duration vs Engineers
    ax1.plot(engineers, durations, 'b-o', linewidth=2, markersize=6, label='Business Days')
    ax1.plot(engineers, calendar_durations, 'g--s', linewidth=2, markersize=4, label='Calendar Days')
    
    # Add critical path line
    critical_path = analysis['critical_path_duration']
    if critical_path > 0:
        ax1.axhline(y=critical_path, color='r', linestyle=':', linewidth=2, 
                   label=f'Critical Path ({critical_path} days)')
    
    # Highlight optimal point
    optimal = analysis['optimal_engineers']
    optimal_result = next(r for r in results if r['engineers'] == optimal)
    ax1.plot(optimal, optimal_result['duration_days'], 'ro', markersize=10, 
            label=f'Optimal ({optimal} engineers)')
    
    ax1.set_xlabel('Number of Engineers')
    ax1.set_ylabel('Project Duration (Days)')
    ax1.set_title('Project Duration vs Team Size')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_xticks(engineers)
    
    # Bottom chart: Efficiency metrics
    efficiencies = [r['efficiency'] * 100 for r in results]  # Convert to percentage
    avg_utilizations = [r['avg_utilization'] for r in results]
    
    ax2_twin = ax2.twinx()
    
    line1 = ax2.plot(engineers, efficiencies, 'purple', marker='o', linewidth=2, 
                    label='Team Efficiency (%)')
    line2 = ax2_twin.plot(engineers, avg_utilizations, 'orange', marker='s', linewidth=2, 
                         label='Avg Utilization (%)')
    
    ax2.set_xlabel('Number of Engineers')
    ax2.set_ylabel('Team Efficiency (%)', color='purple')
    ax2_twin.set_ylabel('Average Utilization (%)', color='orange')
    ax2.set_title('Team Efficiency and Utilization vs Team Size')
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(engineers)
    
    # Combine legends
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    logging.info(f"Optimization chart saved to: {output_file}")


def generate_optimization_report(results: List[Dict], analysis: Dict) -> str:
    """Generate a detailed optimization report"""
    
    optimal = analysis['optimal_engineers']
    optimal_result = next(r for r in results if r['engineers'] == optimal)
    critical_path = analysis['critical_path_duration']
    
    # Find current scenario (4 engineers) for comparison
    current_result = next((r for r in results if r['engineers'] == 4), None)
    
    report = [
        "=" * 70,
        "ENGINEER OPTIMIZATION ANALYSIS",
        "=" * 70,
        "",
        f"📊 OPTIMAL TEAM SIZE: {optimal} Engineers",
        f"   • Project Duration: {optimal_result['duration_days']} business days",
        f"   • Calendar Duration: {optimal_result['calendar_days']} calendar days",
        f"   • Team Efficiency: {optimal_result['efficiency']:.1%}",
        f"   • Average Utilization: {optimal_result['avg_utilization']:.1f}%",
        "",
        f"🎯 CRITICAL PATH LIMIT: {critical_path} business days",
        f"   • Theoretical minimum with unlimited engineers",
        f"   • Optimal team is {optimal_result['duration_days'] - critical_path} days above minimum",
        ""
    ]
    
    if current_result:
        time_saved = current_result['duration_days'] - optimal_result['duration_days']
        calendar_saved = current_result['calendar_days'] - optimal_result['calendar_days']
        
        if optimal != 4:
            report.extend([
                f"📈 COMPARISON TO CURRENT (4 Engineers):",
                f"   • Time Savings: {time_saved} business days ({calendar_saved} calendar days)",
                f"   • Efficiency Gain: {optimal_result['efficiency'] - current_result['efficiency']:.1%}",
                f"   • Team Size Change: {optimal - 4:+d} engineers",
                ""
            ])
        else:
            report.extend([
                f"✅ CURRENT TEAM SIZE (4 Engineers) IS OPTIMAL!",
                f"   • Already at the sweet spot for this project",
                ""
            ])
    
    report.extend([
        "📋 FULL ANALYSIS:",
        "-" * 50,
        f"{'Engineers':<10} {'Duration':<10} {'Calendar':<10} {'Efficiency':<12} {'Avg Util':<10} {'Savings':<10}"
    ])
    
    for i, result in enumerate(results):
        savings = ""
        if i > 0:
            time_saved = results[i-1]['duration_days'] - result['duration_days']
            savings = f"{time_saved}d"
        
        marker = " ⭐" if result['engineers'] == optimal else ""
        marker += " 📍" if result['engineers'] == 4 else ""
        
        efficiency_str = f"{result['efficiency']:.1%}"
        utilization_str = f"{result['avg_utilization']:.1f}%"
        
        report.append(
            f"{result['engineers']:<10} "
            f"{result['duration_days']:<10} "
            f"{result['calendar_days']:<10} "
            f"{efficiency_str:<12} "
            f"{utilization_str:<10} "
            f"{savings:<10}"
            f"{marker}"
        )
    
    report.extend([
        "",
        "🔍 DIMINISHING RETURNS ANALYSIS:",
        "-" * 35
    ])
    
    for saving in analysis['time_savings']:
        if saving['time_saved'] > 0:
            report.append(
                f"   {saving['from_engineers']} → {saving['to_engineers']} engineers: "
                f"{saving['time_saved']} days saved ({saving['percent_improvement']:.1f}% improvement)"
            )
        else:
            report.append(
                f"   {saving['from_engineers']} → {saving['to_engineers']} engineers: "
                f"No improvement (critical path reached)"
            )
    
    report.extend([
        "",
        "💡 RECOMMENDATIONS:",
        "-" * 20,
        f"• Use {optimal} engineers for optimal cost/time balance",
        f"• Adding more than {optimal} engineers shows diminishing returns",
        f"• Cannot go below {critical_path} days due to task dependencies",
        ""
    ])
    
    return '\n'.join(report)


def main():
    parser = argparse.ArgumentParser(description='Analyze optimal team size for project')
    parser.add_argument('--csv', required=True, help='Path to CSV file')
    parser.add_argument('--max-engineers', type=int, default=12, help='Maximum engineers to test (default: 12)')
    parser.add_argument('--output', default='engineer-optimization', help='Output file prefix')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    
    # Prepend output directory to output path
    args.output = os.path.join(output_dir, args.output)
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Parse CSV and build dependency graph
        logging.info(f"Parsing CSV file: {args.csv}")
        tasks = parse_csv(args.csv)
        logging.info(f"Found {len(tasks)} tasks")
        
        # Filter out tasks with no duration (TBD points)
        schedulable_tasks = [task for task in tasks if task['days'] is not None]
        tbd_tasks = [task for task in tasks if task['days'] is None]
        
        if tbd_tasks:
            logging.warning(f"Excluding {len(tbd_tasks)} tasks with TBD points from analysis")
        
        if not schedulable_tasks:
            logging.error("No tasks with valid story points found")
            sys.exit(1)
        
        # Build dependency graph
        logging.info("Building dependency graph...")
        graph = build_dependency_graph(tasks)
        
        # Validate no cycles
        if not nx.is_directed_acyclic_graph(graph):
            cycles = list(nx.simple_cycles(graph))
            logging.error(f"Circular dependencies detected: {cycles}")
            sys.exit(1)
        
        # Calculate critical path
        critical_path_duration = calculate_critical_path_duration(graph)
        logging.info(f"Critical path duration: {critical_path_duration} days")
        
        # Run scaling analysis
        logging.info(f"Running simulations with 1-{args.max_engineers} engineers...")
        results = analyze_engineer_scaling(tasks, graph, args.max_engineers)
        
        # Find optimal team size
        analysis = find_optimal_team_size(results, critical_path_duration)
        
        # Generate report
        report = generate_optimization_report(results, analysis)
        print(report)
        
        # Save results to JSON
        output_data = {
            'results': results,
            'analysis': analysis,
            'metadata': {
                'total_tasks': len(tasks),
                'schedulable_tasks': len(schedulable_tasks),
                'tbd_tasks': len(tbd_tasks),
                'critical_path_duration': critical_path_duration
            }
        }
        
        json_file = f"{args.output}.json"
        with open(json_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        logging.info(f"Detailed results saved to: {json_file}")
        
        # Generate chart
        chart_file = f"{args.output}.png"
        generate_optimization_chart(results, analysis, chart_file)
        
        logging.info("Engineer optimization analysis complete!")
        
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
