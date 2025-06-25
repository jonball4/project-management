#!/usr/bin/env python3
"""
Effort Estimator - Estimates project timeline and generates parallel execution diagrams
"""

import argparse
import csv
import logging
import sys
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import networkx as nx
import subprocess
import os


def add_business_days(start_date: datetime, business_days: int) -> datetime:
    """Add business days to a date, skipping weekends"""
    current_date = start_date
    days_added = 0
    
    while days_added < business_days:
        current_date += timedelta(days=1)
        # Monday = 0, Sunday = 6
        if current_date.weekday() < 5:  # Monday through Friday
            days_added += 1
    
    return current_date


def business_days_between(start_date: datetime, end_date: datetime) -> int:
    """Calculate number of business days between two dates"""
    if start_date >= end_date:
        return 0
    
    current_date = start_date
    business_days = 0
    
    while current_date < end_date:
        if current_date.weekday() < 5:  # Monday through Friday
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days


def get_next_business_day(date: datetime) -> datetime:
    """Get the next business day (skip weekends)"""
    next_day = date
    while next_day.weekday() >= 5:  # Saturday or Sunday
        next_day += timedelta(days=1)
    return next_day


class TaskScheduler:
    """Schedules tasks across multiple engineers with dependency constraints"""
    
    def __init__(self, num_engineers: int):
        self.num_engineers = num_engineers
        self.engineer_schedules = [[] for _ in range(num_engineers)]
        self.engineer_end_times = [0] * num_engineers
        self.task_start_times = {}
        self.task_end_times = {}
        
    def schedule_task(self, task_name: str, duration_days: int, dependencies: List[str]) -> int:
        """Schedule a task and return the assigned engineer index"""
        # Calculate earliest start time based on dependencies
        earliest_start = 0
        for dep in dependencies:
            if dep in self.task_end_times:
                earliest_start = max(earliest_start, self.task_end_times[dep])
        
        # Find the engineer who can start earliest (considering their current workload)
        best_engineer = 0
        best_start_time = max(earliest_start, self.engineer_end_times[0])
        
        for i in range(1, self.num_engineers):
            candidate_start = max(earliest_start, self.engineer_end_times[i])
            if candidate_start < best_start_time:
                best_engineer = i
                best_start_time = candidate_start
        
        # Schedule the task
        start_time = best_start_time
        end_time = start_time + duration_days
        
        self.task_start_times[task_name] = start_time
        self.task_end_times[task_name] = end_time
        self.engineer_end_times[best_engineer] = end_time
        
        self.engineer_schedules[best_engineer].append({
            'task': task_name,
            'start': start_time,
            'end': end_time,
            'duration': duration_days
        })
        
        return best_engineer
    
    def get_project_duration(self) -> int:
        """Get total project duration in days"""
        return max(self.engineer_end_times) if self.engineer_end_times else 0
    
    def get_engineer_utilization(self) -> List[float]:
        """Get utilization percentage for each engineer"""
        total_duration = self.get_project_duration()
        if total_duration == 0:
            return [0.0] * self.num_engineers
        
        return [
            (self.engineer_end_times[i] / total_duration) * 100
            for i in range(self.num_engineers)
        ]


def points_to_days(points: Optional[int]) -> Optional[int]:
    """Convert story points to work days"""
    if points is None:
        return None
    
    mapping = {1: 1, 2: 2, 3: 3, 5: 5, 8: 8, 13: 13}
    return mapping.get(points)


def parse_csv(csv_file: str) -> List[Dict]:
    """Parse the CSV file and return task data"""
    tasks = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip the TOTAL row
            if row['Task'].strip().upper() == 'TOTAL':
                continue
                
            # Skip empty rows
            if not row['Task'].strip():
                continue
            
            # Parse dependencies (handle multi-line)
            dependencies = []
            if row['Dependencies'].strip():
                # Split by newlines - each line is a separate dependency
                dep_lines = row['Dependencies'].strip().split('\n')
                for line in dep_lines:
                    line = line.strip()
                    if line:
                        dependencies.append(line)
            
            # Parse story points
            points = None
            if row['Points'].strip() and row['Points'].strip().upper() != 'TBD':
                try:
                    points = int(row['Points'].strip())
                except ValueError:
                    logging.warning(f"Invalid points value for task '{row['Task']}': {row['Points']}")
            
            task_data = {
                'name': row['Task'].strip(),
                'description': row['Description'].strip(),
                'dependencies': dependencies,
                'points': points,
                'days': points_to_days(points)
            }
            tasks.append(task_data)
    
    return tasks


def build_dependency_graph(tasks: List[Dict]) -> nx.DiGraph:
    """Build a dependency graph from tasks"""
    graph = nx.DiGraph()
    task_names = {task['name'] for task in tasks}
    
    # Add all tasks as nodes
    for task in tasks:
        graph.add_node(task['name'], **task)
    
    # Validate dependencies - only exact matches allowed
    for task in tasks:
        for dep in task['dependencies']:
            if dep not in task_names:
                logging.error(f"Task '{task['name']}' has invalid dependency: '{dep}'")
                sys.exit(1)
    
    # Add dependency edges
    for task in tasks:
        for dep in task['dependencies']:
            # Add edge from dependency to task (dependency must be completed first)
            graph.add_edge(dep, task['name'])
    
    return graph


def generate_mermaid_gantt(scheduler: TaskScheduler, tasks_by_name: Dict[str, Dict], 
                          output_file: str = "timeline.mmd") -> str:
    """Generate a Mermaid Gantt chart using business days"""
    
    # Calculate start date (next business day from today)
    start_datetime = datetime.now()
    start_date = get_next_business_day(start_datetime).date()
    
    mermaid_content = [
        "gantt",
        f"    title Just-in-Time Settlement - {scheduler.num_engineers} Engineers (Business Days)",
        "    dateFormat YYYY-MM-DD",
        "    axisFormat %m/%d",
        ""
    ]
    
    # Color palette for engineers
    colors = ["#ff6b6b", "#4ecdc4", "#45b7d1", "#96ceb4", "#feca57", "#ff9ff3", "#54a0ff", "#5f27cd"]
    
    for engineer_idx in range(scheduler.num_engineers):
        schedule = scheduler.engineer_schedules[engineer_idx]
        if not schedule:
            continue
            
        color = colors[engineer_idx % len(colors)]
        mermaid_content.append(f"    section Engineer {engineer_idx + 1}")
        
        for task_info in schedule:
            task_name = task_info['task']
            task_data = tasks_by_name[task_name]
            start_business_day = task_info['start']
            duration_business_days = task_info['duration']
            
            # Calculate actual business dates
            task_start_datetime = add_business_days(datetime.combine(start_date, datetime.min.time()), start_business_day)
            task_start_date = task_start_datetime.date()
            
            # Calculate end date (business days)
            task_end_datetime = add_business_days(task_start_datetime, duration_business_days - 1)
            task_end_date = task_end_datetime.date()
            
            # Truncate long task names for display
            display_name = task_name[:30] + "..." if len(task_name) > 30 else task_name
            points_str = f" ({task_data['points']}pts)" if task_data['points'] else ""
            
            mermaid_content.append(
                f"    {display_name}{points_str}    :{task_start_date.strftime('%Y-%m-%d')}, {task_end_date.strftime('%Y-%m-%d')}"
            )
        
        mermaid_content.append("")
    
    # Add project completion milestone to show end date clearly
    project_duration = scheduler.get_project_duration()
    project_end_datetime = add_business_days(datetime.combine(start_date, datetime.min.time()), project_duration - 1)
    project_end_date = project_end_datetime.date()
    
    mermaid_content.extend([
        "    section Project Milestones",
        f"    Project Complete    :milestone, {project_end_date.strftime('%Y-%m-%d')}, 0d",
        ""
    ])
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write('\n'.join(mermaid_content))
    
    return output_file


def generate_summary_report(scheduler: TaskScheduler, tasks: List[Dict], 
                          graph: nx.DiGraph) -> str:
    """Generate a text summary report"""
    
    total_tasks = len(tasks)
    total_points = sum(task['points'] for task in tasks if task['points'])
    total_days = sum(task['days'] for task in tasks if task['days'])
    project_duration = scheduler.get_project_duration()
    utilization = scheduler.get_engineer_utilization()
    
    # Calculate critical path
    try:
        # Find tasks with no successors (end tasks)
        end_tasks = [node for node in graph.nodes() if graph.out_degree(node) == 0]
        critical_paths = []
        
        for end_task in end_tasks:
            # Find longest path to this end task
            paths = []
            for start_task in graph.nodes():
                if graph.in_degree(start_task) == 0:  # Start tasks
                    try:
                        path = nx.shortest_path(graph, start_task, end_task)
                        path_duration = sum(
                            graph.nodes[task].get('days', 0) or 0 
                            for task in path
                        )
                        paths.append((path, path_duration))
                    except nx.NetworkXNoPath:
                        continue
            
            if paths:
                critical_paths.extend(paths)
        
        # Find the longest critical path
        if critical_paths:
            critical_path, critical_duration = max(critical_paths, key=lambda x: x[1])
        else:
            critical_path, critical_duration = [], 0
            
    except Exception as e:
        logging.warning(f"Could not calculate critical path: {e}")
        critical_path, critical_duration = [], 0
    
    # Calculate calendar duration from business days
    start_datetime = datetime.now()
    start_date = get_next_business_day(start_datetime)
    end_datetime = add_business_days(start_date, project_duration)
    calendar_duration = (end_datetime.date() - start_date.date()).days + 1
    
    report = [
        "=" * 60,
        "PROJECT ESTIMATION SUMMARY (Business Days Only)",
        "=" * 60,
        "",
        f"Total Tasks: {total_tasks}",
        f"Total Story Points: {total_points}",
        f"Total Effort: {total_days} engineer-days (business days)",
        f"Project Duration: {project_duration} business days",
        f"Calendar Duration: {calendar_duration} calendar days (including weekends)",
        f"Engineers: {scheduler.num_engineers}",
        "",
        "ENGINEER UTILIZATION:",
        "-" * 20
    ]
    
    for i, util in enumerate(utilization):
        workload = scheduler.engineer_end_times[i]
        report.append(f"Engineer {i+1}: {util:.1f}% ({workload} days)")
    
    if critical_path:
        report.extend([
            "",
            "CRITICAL PATH:",
            "-" * 15,
            f"Duration: {critical_duration} days",
            "Tasks:"
        ])
        for i, task in enumerate(critical_path, 1):
            task_data = graph.nodes[task]
            points = task_data.get('points', 'TBD')
            days = task_data.get('days', 'TBD')
            report.append(f"  {i}. {task} ({points} pts, {days} days)")
    
    report.extend([
        "",
        "TASKS WITH TBD POINTS:",
        "-" * 22
    ])
    
    tbd_tasks = [task for task in tasks if task['points'] is None]
    if tbd_tasks:
        for task in tbd_tasks:
            report.append(f"  - {task['name']}")
    else:
        report.append("  None")
    
    return '\n'.join(report)


def render_mermaid_diagram(mermaid_file: str, output_file: str) -> bool:
    """Render Mermaid diagram to PNG using mermaid CLI"""
    try:
        # Check if mermaid CLI is available
        result = subprocess.run(['mmdc', '--version'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            logging.warning("Mermaid CLI (mmdc) not found. Install with: npm install -g @mermaid-js/mermaid-cli")
            return False
        
        # Render the diagram
        cmd = ['mmdc', '-i', mermaid_file, '-o', output_file, '-t', 'neutral', '-b', 'white']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info(f"Mermaid diagram rendered to: {output_file}")
            return True
        else:
            logging.error(f"Failed to render Mermaid diagram: {result.stderr}")
            return False
            
    except FileNotFoundError:
        logging.warning("Mermaid CLI (mmdc) not found. Install with: npm install -g @mermaid-js/mermaid-cli")
        return False


def main():
    parser = argparse.ArgumentParser(description='Estimate project effort and generate execution timeline')
    parser.add_argument('--csv', required=True, help='Path to CSV file')
    parser.add_argument('--engineers', type=int, default=4, help='Number of engineers (default: 4)')
    parser.add_argument('--output', default='timeline', help='Output file prefix (default: timeline)')
    parser.add_argument('--format', choices=['gantt', 'png', 'both'], default='both', 
                       help='Output format (default: both)')
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
        # Parse CSV
        logging.info(f"Parsing CSV file: {args.csv}")
        tasks = parse_csv(args.csv)
        logging.info(f"Found {len(tasks)} tasks")
        
        # Filter out tasks with no duration (TBD points)
        schedulable_tasks = [task for task in tasks if task['days'] is not None]
        tbd_tasks = [task for task in tasks if task['days'] is None]
        
        if tbd_tasks:
            logging.warning(f"Excluding {len(tbd_tasks)} tasks with TBD points from scheduling")
        
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
        
        # Get topological order for scheduling
        topo_order = list(nx.topological_sort(graph))
        
        # Schedule tasks
        logging.info(f"Scheduling {len(schedulable_tasks)} tasks across {args.engineers} engineers...")
        scheduler = TaskScheduler(args.engineers)
        tasks_by_name = {task['name']: task for task in tasks}
        
        for task_name in topo_order:
            task_data = tasks_by_name[task_name]
            if task_data['days'] is not None:  # Only schedule tasks with known duration
                dependencies = [dep for dep in task_data['dependencies'] 
                              if tasks_by_name[dep]['days'] is not None]
                engineer = scheduler.schedule_task(
                    task_name, 
                    task_data['days'], 
                    dependencies
                )
                logging.debug(f"Scheduled '{task_name}' to Engineer {engineer + 1}")
        
        # Generate outputs
        project_duration = scheduler.get_project_duration()
        logging.info(f"Project duration: {project_duration} days")
        
        # Generate summary report
        report = generate_summary_report(scheduler, tasks, graph)
        print(report)
        
        # Generate Mermaid diagram
        if args.format in ['gantt', 'both']:
            mermaid_file = f"{args.output}.mmd"
            generate_mermaid_gantt(scheduler, tasks_by_name, mermaid_file)
            logging.info(f"Mermaid diagram saved to: {mermaid_file}")
        
        # Render PNG if requested
        if args.format in ['png', 'both']:
            mermaid_file = f"{args.output}.mmd"
            png_file = f"{args.output}.png"
            
            if args.format == 'png' and not os.path.exists(mermaid_file):
                generate_mermaid_gantt(scheduler, tasks_by_name, mermaid_file)
            
            if render_mermaid_diagram(mermaid_file, png_file):
                logging.info(f"Timeline diagram saved to: {png_file}")
            else:
                logging.info(f"Mermaid source available in: {mermaid_file}")
        
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
