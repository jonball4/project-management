"""Tests for scheduler module."""

import pytest

from scheduler import TaskScheduler


def test_scheduler_initialization():
    """Test scheduler initialization."""
    scheduler = TaskScheduler(num_engineers=3)
    assert scheduler.num_engineers == 3
    assert len(scheduler.engineer_schedules) == 3
    assert len(scheduler.engineer_end_times) == 3
    assert all(end_time == 0 for end_time in scheduler.engineer_end_times)


def test_schedule_single_task():
    """Test scheduling a single task."""
    scheduler = TaskScheduler(num_engineers=2)
    engineer = scheduler.schedule_task("Task1", duration_days=5.0, dependencies=[])

    assert engineer in [0, 1]
    assert scheduler.get_project_duration() == 5.0
    assert "Task1" in scheduler.task_start_times
    assert scheduler.task_start_times["Task1"] == 0
    assert scheduler.task_end_times["Task1"] == 5.0


def test_schedule_dependent_tasks():
    """Test scheduling tasks with dependencies."""
    scheduler = TaskScheduler(num_engineers=2)

    # Schedule first task
    scheduler.schedule_task("Task1", duration_days=3.0, dependencies=[])

    # Schedule dependent task
    scheduler.schedule_task("Task2", duration_days=2.0, dependencies=["Task1"])

    # Task2 should start after Task1 ends
    assert scheduler.task_start_times["Task2"] == 3.0
    assert scheduler.task_end_times["Task2"] == 5.0
    assert scheduler.get_project_duration() == 5.0


def test_schedule_parallel_tasks():
    """Test scheduling parallel tasks."""
    scheduler = TaskScheduler(num_engineers=2)

    # Schedule two independent tasks
    eng1 = scheduler.schedule_task("Task1", duration_days=5.0, dependencies=[])
    eng2 = scheduler.schedule_task("Task2", duration_days=3.0, dependencies=[])

    # Should be assigned to different engineers
    assert eng1 != eng2

    # Project duration should be the max of the two
    assert scheduler.get_project_duration() == 5.0


def test_schedule_negative_duration():
    """Test that negative duration raises ValueError."""
    scheduler = TaskScheduler(num_engineers=2)

    with pytest.raises(ValueError, match="Duration must be non-negative"):
        scheduler.schedule_task("Task1", duration_days=-5.0, dependencies=[])


def test_get_engineer_utilization():
    """Test engineer utilization calculation."""
    scheduler = TaskScheduler(num_engineers=2)

    # Engineer 0 gets 10 days of work
    scheduler.schedule_task("Task1", duration_days=10.0, dependencies=[])

    # Engineer 1 gets 5 days of work
    scheduler.schedule_task("Task2", duration_days=5.0, dependencies=[])

    utilization = scheduler.get_engineer_utilization()

    # Project duration is 10 days
    # Engineer 0: 10/10 = 100%
    # Engineer 1: 5/10 = 50%
    assert utilization[0] == 100.0
    assert utilization[1] == 50.0


def test_empty_scheduler():
    """Test scheduler with no tasks."""
    scheduler = TaskScheduler(num_engineers=2)

    assert scheduler.get_project_duration() == 0
    utilization = scheduler.get_engineer_utilization()
    assert all(util == 0.0 for util in utilization)


def test_complex_dependency_chain():
    """Test scheduling a complex dependency chain."""
    scheduler = TaskScheduler(num_engineers=3)

    # Task1 (5 days)
    scheduler.schedule_task("Task1", duration_days=5.0, dependencies=[])

    # Task2 depends on Task1 (3 days)
    scheduler.schedule_task("Task2", duration_days=3.0, dependencies=["Task1"])

    # Task3 depends on Task2 (2 days)
    scheduler.schedule_task("Task3", duration_days=2.0, dependencies=["Task2"])

    # Task4 depends on Task1 (parallel with Task2/Task3)
    scheduler.schedule_task("Task4", duration_days=4.0, dependencies=["Task1"])

    # Total duration should be the critical path: Task1 -> Task2 -> Task3 = 10 days
    assert scheduler.get_project_duration() == 10.0

    # Verify start times
    assert scheduler.task_start_times["Task1"] == 0
    assert scheduler.task_start_times["Task2"] == 5.0
    assert scheduler.task_start_times["Task3"] == 8.0
    assert scheduler.task_start_times["Task4"] == 5.0  # Parallel with Task2
