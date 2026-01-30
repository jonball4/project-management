#!/usr/bin/env python3
"""
Task Scheduler - Common module for scheduling tasks across engineers
"""

from typing import Dict, List


class TaskScheduler:
    """Schedules tasks across multiple engineers with dependency constraints"""

    def __init__(self, num_engineers: int):
        self.num_engineers = num_engineers
        self.engineer_schedules: List[List[Dict]] = [[] for _ in range(num_engineers)]
        self.engineer_end_times: List[float] = [0.0] * num_engineers
        self.task_start_times: Dict[str, float] = {}
        self.task_end_times: Dict[str, float] = {}

    def schedule_task(self, task_name: str, duration_days: float, dependencies: List[str]) -> int:
        """Schedule a task and return the assigned engineer index"""
        # Validate inputs
        if duration_days < 0:
            raise ValueError(
                f"Duration must be non-negative, got {duration_days} for task {task_name}"
            )

        # Calculate earliest start time based on dependencies
        earliest_start = 0.0
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

        self.task_start_times[task_name] = float(start_time)
        self.task_end_times[task_name] = float(end_time)
        self.engineer_end_times[best_engineer] = float(end_time)

        self.engineer_schedules[best_engineer].append(
            {"task": task_name, "start": start_time, "end": end_time, "duration": duration_days}
        )

        return best_engineer

    def get_project_duration(self) -> float:
        """Get total project duration in days"""
        return max(self.engineer_end_times) if self.engineer_end_times else 0

    def get_engineer_utilization(self) -> List[float]:
        """Get utilization percentage for each engineer"""
        total_duration = self.get_project_duration()
        if total_duration == 0:
            return [0.0] * self.num_engineers

        return [
            (self.engineer_end_times[i] / total_duration) * 100 for i in range(self.num_engineers)
        ]
