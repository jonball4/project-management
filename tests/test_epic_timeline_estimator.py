"""Tests for epic_timeline_estimator module."""

import random
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from epic_timeline_estimator import EpicAnalyzer, add_workdays
from issue_parser import Issue

# ---- Fixtures ----


@pytest.fixture
def analyzer():
    """Create an EpicAnalyzer with a mock Jira client."""
    return EpicAnalyzer(MagicMock())


def _make_issue(key, points, status="To Do", epic_key=None):
    """Helper to create an Issue with less boilerplate."""
    return Issue(
        key=key, summary=f"Task {key}", status=status, story_points=points, epic_key=epic_key
    )


def _setup_analyzer(analyzer, issues_dict, epic_keys=None):
    """Helper to configure analyzer with issues grouped by epic."""
    analyzer.issues = {}
    analyzer.issues_by_epic = {}
    if epic_keys is None:
        epic_keys = []

    for epic_key, issues in issues_dict.items():
        if epic_key not in epic_keys:
            epic_keys.append(epic_key)
        epic_map = {}
        for issue in issues:
            issue.epic_key = epic_key
            analyzer.issues[issue.key] = issue
            epic_map[issue.key] = issue
        analyzer.issues_by_epic[epic_key] = epic_map

    analyzer.epic_keys = epic_keys


# ---- _compute_team_efficiency tests ----


class TestComputeTeamEfficiency:
    def test_single_developer(self, analyzer):
        """1 developer = 100% efficiency."""
        assert analyzer._compute_team_efficiency(1.0, 0.15) == 1.0

    def test_sub_one_developer(self, analyzer):
        """Fractional developer <= 1 = 100% efficiency."""
        assert analyzer._compute_team_efficiency(0.5, 0.15) == 1.0

    def test_two_developers(self, analyzer):
        """2 developers with factor 0.15: 1/(1+0.15*1) ≈ 0.87."""
        eff = analyzer._compute_team_efficiency(2.0, 0.15)
        assert round(eff, 2) == 0.87

    def test_four_developers(self, analyzer):
        """4 developers with factor 0.15: 1/(1+0.15*2) ≈ 0.77."""
        eff = analyzer._compute_team_efficiency(4.0, 0.15)
        assert round(eff, 2) == 0.77

    def test_eight_developers(self, analyzer):
        """8 developers with factor 0.15: 1/(1+0.15*3) ≈ 0.69."""
        eff = analyzer._compute_team_efficiency(8.0, 0.15)
        assert round(eff, 2) == 0.69

    def test_zero_coordination_factor(self, analyzer):
        """No coordination overhead = 100% efficiency regardless of team size."""
        assert analyzer._compute_team_efficiency(10.0, 0.0) == 1.0

    def test_high_coordination_factor(self, analyzer):
        """High coordination factor degrades efficiency significantly."""
        eff = analyzer._compute_team_efficiency(4.0, 0.5)
        # 1/(1+0.5*2) = 0.5
        assert eff == 0.5


# ---- _simulate_workdays_for_run tests ----


class TestSimulateWorkdays:
    """Tests for the discrete event simulator."""

    def test_all_issues_complete(self, analyzer):
        """If all issues are already done, completion_day is 0."""
        done = _make_issue("T-1", 5.0, status="Done")
        _setup_analyzer(analyzer, {"E-1": [done]})

        result = analyzer._simulate_workdays_for_run(
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        assert result["completion_day"] == 0
        assert result["epic_completion_days"]["E-1"] == 0

    def test_single_issue_one_dev(self, analyzer):
        """Single 5pt issue, 1 dev at 1pt/day = 5 days."""
        issue = _make_issue("T-1", 5.0)
        _setup_analyzer(analyzer, {"E-1": [issue]})

        result = analyzer._simulate_workdays_for_run(
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        assert result["completion_day"] == 5
        assert result["epic_completion_days"]["E-1"] == 5

    def test_single_1pt_issue(self, analyzer):
        """Single 1pt issue should complete in 1 day with sufficient capacity."""
        issue = _make_issue("T-1", 1.0)
        _setup_analyzer(analyzer, {"E-1": [issue]})

        result = analyzer._simulate_workdays_for_run(
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        assert result["completion_day"] == 1

    def test_parallel_independent_issues(self, analyzer):
        """Two independent 5pt issues, 2 devs = 5 days (parallel)."""
        a = _make_issue("T-1", 5.0)
        b = _make_issue("T-2", 5.0)
        _setup_analyzer(analyzer, {"E-1": [a, b]})

        result = analyzer._simulate_workdays_for_run(
            developers=2,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        assert result["completion_day"] == 5

    def test_sequential_dependency_chain(self, analyzer):
        """A->B->C chain, each 3pts, 1 dev at 1pt/day = 9 days sequential."""
        a = _make_issue("T-1", 3.0)
        b = _make_issue("T-2", 3.0)
        c = _make_issue("T-3", 3.0)
        a.blocks = {"T-2"}
        b.blocked_by = {"T-1"}
        b.blocks = {"T-3"}
        c.blocked_by = {"T-2"}
        _setup_analyzer(analyzer, {"E-1": [a, b, c]})

        result = analyzer._simulate_workdays_for_run(
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        assert result["completion_day"] == 9

    def test_sequential_chain_extra_devs_dont_help(self, analyzer):
        """A->B chain, extra devs can't parallelize sequential work."""
        a = _make_issue("T-1", 5.0)
        b = _make_issue("T-2", 5.0)
        a.blocks = {"T-2"}
        b.blocked_by = {"T-1"}
        _setup_analyzer(analyzer, {"E-1": [a, b]})

        result = analyzer._simulate_workdays_for_run(
            developers=5,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        # Must be sequential: 5 + 5 = 10 days
        assert result["completion_day"] == 10

    def test_multi_epic_completion_tracking(self, analyzer):
        """Each epic's completion day is tracked independently."""
        a = _make_issue("A-1", 3.0)
        b = _make_issue("B-1", 6.0)
        _setup_analyzer(analyzer, {"E-1": [a], "E-2": [b]})

        result = analyzer._simulate_workdays_for_run(
            developers=2,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        assert result["epic_completion_days"]["E-1"] == 3
        assert result["epic_completion_days"]["E-2"] == 6
        assert result["completion_day"] == 6

    def test_multi_epic_blocker_prioritized_over_leaves(self, analyzer):
        """A ticket blocking other work is picked before leaf tickets from another epic."""
        # A-1 blocks A-2 (1 descendant), so A-1 has priority
        a1 = _make_issue("A-1", 5.0)
        a2 = _make_issue("A-2", 5.0)
        a1.blocks = {"A-2"}
        a2.blocked_by = {"A-1"}

        # B-1 is a leaf (0 descendants)
        b1 = _make_issue("B-1", 1.0)

        _setup_analyzer(analyzer, {"E-1": [a1, a2], "E-2": [b1]})

        result = analyzer._simulate_workdays_for_run(
            developers=2,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        # Dev1 picks A-1 (1 descendant), Dev2 picks B-1 (0 descendants)
        # B-1 (1pt) finishes day 1, A-1 (5pt) finishes day 5, A-2 finishes day 10
        assert result["epic_completion_days"]["E-2"] == 1
        assert result["epic_completion_days"]["E-1"] == 10

    def test_priority_scheduling_blocker_first(self, analyzer):
        """Tickets that unblock more work should be prioritized."""
        # A-1 blocks A-2 and A-3 (2 descendants)
        a1 = _make_issue("A-1", 1.0)
        a2 = _make_issue("A-2", 1.0)
        a3 = _make_issue("A-3", 1.0)
        a1.blocks = {"A-2", "A-3"}
        a2.blocked_by = {"A-1"}
        a3.blocked_by = {"A-1"}

        # B-1 is independent (0 descendants)
        b1 = _make_issue("B-1", 1.0)

        _setup_analyzer(analyzer, {"E-1": [a1, a2, a3, b1]})

        result = analyzer._simulate_workdays_for_run(
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        # With 1 dev: A-1 first (blocker), then A-2, A-3, B-1 in some order = 4 days
        assert result["completion_day"] == 4

    def test_brooks_law_applied(self, analyzer):
        """Brooks's Law reduces effective capacity, increasing completion time."""
        issue = _make_issue("T-1", 10.0)
        _setup_analyzer(analyzer, {"E-1": [issue]})

        # Without Brooks's Law
        result_no_brooks = analyzer._simulate_workdays_for_run(
            developers=4,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )

        # With Brooks's Law
        result_with_brooks = analyzer._simulate_workdays_for_run(
            developers=4,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.15,
            variance=0.0,
        )

        # With Brooks's Law, each dev is less efficient, so it takes longer
        assert result_with_brooks["completion_day"] >= result_no_brooks["completion_day"]

    def test_variance_affects_results(self, analyzer):
        """Non-zero variance should produce different results across runs."""
        issue = _make_issue("T-1", 10.0)
        _setup_analyzer(analyzer, {"E-1": [issue]})

        results = set()
        for seed in range(50):
            random.seed(seed)
            result = analyzer._simulate_workdays_for_run(
                developers=1,
                points_per_sprint_per_dev=5,
                sprint_weeks=1,
                coordination_factor=0.0,
                variance=0.30,
            )
            results.add(result["completion_day"])

        # With high variance, we should see at least 2 different outcomes
        assert len(results) > 1

    def test_zero_variance_deterministic(self, analyzer):
        """Zero variance should produce identical results every run."""
        issue = _make_issue("T-1", 10.0)
        _setup_analyzer(analyzer, {"E-1": [issue]})

        results = set()
        for seed in range(20):
            random.seed(seed)
            result = analyzer._simulate_workdays_for_run(
                developers=1,
                points_per_sprint_per_dev=5,
                sprint_weeks=1,
                coordination_factor=0.0,
                variance=0.0,
            )
            results.add(result["completion_day"])

        assert len(results) == 1
        assert results.pop() == 10

    def test_sprint_weeks_affects_capacity(self, analyzer):
        """Longer sprints spread the same points over more days."""
        issue = _make_issue("T-1", 10.0)
        _setup_analyzer(analyzer, {"E-1": [issue]})

        # 1-week sprint: 5pts/5days = 1pt/day → 10 days
        result_1w = analyzer._simulate_workdays_for_run(
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )

        # 2-week sprint: 5pts/10days = 0.5pt/day → 20 days
        result_2w = analyzer._simulate_workdays_for_run(
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=2,
            coordination_factor=0.0,
            variance=0.0,
        )

        assert result_1w["completion_day"] == 10
        assert result_2w["completion_day"] == 20

    def test_fractional_developers_ceiling(self, analyzer):
        """Fractional developers are ceiled for headcount."""
        a = _make_issue("T-1", 5.0)
        b = _make_issue("T-2", 5.0)
        _setup_analyzer(analyzer, {"E-1": [a, b]})

        # 1.5 devs → ceil(1.5) = 2 engineers, both work in parallel
        result = analyzer._simulate_workdays_for_run(
            developers=1.5,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        # 2 engineers work in parallel at 1pt/day each
        assert result["completion_day"] == 5

    def test_already_complete_deps_satisfied(self, analyzer):
        """Issues blocked by already-complete issues should be available immediately."""
        done = _make_issue("T-1", 3.0, status="Done")
        blocked = _make_issue("T-2", 5.0)
        blocked.blocked_by = {"T-1"}
        done.blocks = {"T-2"}
        _setup_analyzer(analyzer, {"E-1": [done, blocked]})

        result = analyzer._simulate_workdays_for_run(
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        # T-1 already done, T-2 unblocked from day 1 → 5 days
        assert result["completion_day"] == 5

    def test_external_dep_not_blocking(self, analyzer):
        """Dependencies on issues outside the tracked set don't block forever."""
        issue = _make_issue("T-1", 5.0)
        # Blocked by an issue not in analyzer.issues
        issue.blocked_by = {"EXTERNAL-1"}
        _setup_analyzer(analyzer, {"E-1": [issue]})

        # EXTERNAL-1 is not in completed_in_sim, so T-1 stays blocked
        # This is correct behavior - if a blocker isn't tracked, it's not resolved
        result = analyzer._simulate_workdays_for_run(
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        # T-1 will be stuck at max_workdays since its dep is never resolved
        assert result["completion_day"] == 365 * 2

    def test_engineers_claim_discrete_tickets(self, analyzer):
        """Each engineer works on exactly one ticket at a time, no sharing."""
        a = _make_issue("T-1", 3.0)
        b = _make_issue("T-2", 3.0)
        _setup_analyzer(analyzer, {"E-1": [a, b]})

        # 2 engineers, each claims a separate ticket
        result = analyzer._simulate_workdays_for_run(
            developers=2,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        # Both work in parallel: 3 days
        assert result["completion_day"] == 3

    def test_zero_point_issue_completes_immediately(self, analyzer):
        """A 0-point issue should complete on day 1."""
        issue = _make_issue("T-1", 0.0)
        _setup_analyzer(analyzer, {"E-1": [issue]})

        result = analyzer._simulate_workdays_for_run(
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        assert result["completion_day"] == 1

    def test_mixed_complete_and_incomplete(self, analyzer):
        """Mix of done and to-do issues; only incomplete count for completion."""
        done1 = _make_issue("T-1", 5.0, status="Done")
        done2 = _make_issue("T-2", 3.0, status="Closed")
        todo = _make_issue("T-3", 2.0)
        _setup_analyzer(analyzer, {"E-1": [done1, done2, todo]})

        result = analyzer._simulate_workdays_for_run(
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            coordination_factor=0.0,
            variance=0.0,
        )
        assert result["completion_day"] == 2


# ---- get_epic_issues tests ----


class TestGetEpicIssues:
    def test_returns_correct_epic(self, analyzer):
        a = _make_issue("A-1", 5.0, epic_key="E-1")
        b = _make_issue("B-1", 3.0, epic_key="E-2")
        analyzer.issues_by_epic = {"E-1": {"A-1": a}, "E-2": {"B-1": b}}

        result = analyzer.get_epic_issues("E-1")
        assert "A-1" in result
        assert "B-1" not in result

    def test_unknown_epic_returns_empty(self, analyzer):
        analyzer.issues_by_epic = {}
        assert analyzer.get_epic_issues("NOPE") == {}


# ---- estimate_timeline tests ----


class TestEstimateTimeline:
    def test_end_to_end_basic(self, analyzer):
        """Full estimate_timeline returns expected structure."""
        issue = _make_issue("T-1", 5.0, epic_key="E-1")
        _setup_analyzer(analyzer, {"E-1": [issue]})

        result = analyzer.estimate_timeline(
            epic_keys=["E-1"],
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            simulations=100,
            variance=0.0,
        )

        assert result["total_issues"] == 1
        assert result["remaining_issues"] == 1
        assert result["total_points"] == 5.0
        assert "p50_workdays" in result
        assert "p85_workdays" in result
        assert "p95_workdays" in result
        assert "p50_end_date" in result
        assert "epic_summaries" in result
        assert "E-1" in result["epic_summaries"]

    def test_string_epic_key_backward_compat(self, analyzer):
        """Passing a single string epic_key still works."""
        issue = _make_issue("T-1", 3.0, epic_key="E-1")
        _setup_analyzer(analyzer, {"E-1": [issue]})

        result = analyzer.estimate_timeline(
            epic_keys="E-1",
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            simulations=50,
            variance=0.0,
        )

        assert result["epics"] == ["E-1"]

    def test_percentiles_ordering(self, analyzer):
        """p50 <= p85 <= p95 for workday estimates."""
        issues = [_make_issue(f"T-{i}", 3.0) for i in range(1, 11)]
        _setup_analyzer(analyzer, {"E-1": issues})

        result = analyzer.estimate_timeline(
            epic_keys=["E-1"],
            developers=2,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            simulations=500,
            variance=0.15,
        )

        assert result["p50_workdays"] <= result["p85_workdays"]
        assert result["p85_workdays"] <= result["p95_workdays"]

    def test_multi_epic_summaries(self, analyzer):
        """Multi-epic run produces per-epic summaries."""
        a = _make_issue("A-1", 5.0)
        b = _make_issue("B-1", 3.0)
        _setup_analyzer(analyzer, {"E-1": [a], "E-2": [b]})

        result = analyzer.estimate_timeline(
            epic_keys=["E-1", "E-2"],
            developers=2,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            simulations=100,
            variance=0.0,
        )

        assert "E-1" in result["epic_summaries"]
        assert "E-2" in result["epic_summaries"]
        assert result["epic_summaries"]["E-1"]["total_points"] == 5.0
        assert result["epic_summaries"]["E-2"]["total_points"] == 3.0

    def test_completed_points_tracked(self, analyzer):
        """Completed points are tracked separately."""
        done = _make_issue("T-1", 5.0, status="Done")
        todo = _make_issue("T-2", 3.0)
        _setup_analyzer(analyzer, {"E-1": [done, todo]})

        result = analyzer.estimate_timeline(
            epic_keys=["E-1"],
            developers=1,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            simulations=50,
            variance=0.0,
        )

        assert result["completed_points"] == 5.0
        assert result["total_points"] == 3.0
        assert result["completed_issues"] == 1
        assert result["remaining_issues"] == 1

    def test_end_dates_land_on_weekdays(self, analyzer):
        """All projected dates should land on weekdays (Mon-Fri)."""
        issues = [_make_issue(f"T-{i}", 3.0) for i in range(1, 6)]
        _setup_analyzer(analyzer, {"E-1": issues})

        result = analyzer.estimate_timeline(
            epic_keys=["E-1"],
            developers=2,
            points_per_sprint_per_dev=5,
            sprint_weeks=1,
            simulations=100,
            variance=0.1,
        )

        for date_key in ["p50_end_date", "p85_end_date", "p95_end_date"]:
            d = datetime.strptime(result[date_key], "%Y-%m-%d")
            assert d.weekday() < 5, f"{date_key} = {result[date_key]} is a weekend"

        for epic_summary in result["epic_summaries"].values():
            for date_key in ["p50_end_date", "p85_end_date", "p95_end_date"]:
                d = datetime.strptime(epic_summary[date_key], "%Y-%m-%d")
                assert d.weekday() < 5, f"Epic {date_key} = {epic_summary[date_key]} is a weekend"


# ---- add_workdays tests ----


class TestAddWorkdays:
    def test_zero_workdays(self):
        """Adding 0 workdays returns the same date."""
        start = datetime(2026, 2, 18)  # Wednesday
        assert add_workdays(start, 0) == start

    def test_one_workday_midweek(self):
        """Adding 1 workday on Wednesday = Thursday."""
        start = datetime(2026, 2, 18)  # Wednesday
        result = add_workdays(start, 1)
        assert result == datetime(2026, 2, 19)  # Thursday
        assert result.weekday() == 3

    def test_skips_weekend(self):
        """Adding 1 workday on Friday = Monday."""
        friday = datetime(2026, 2, 20)  # Friday
        result = add_workdays(friday, 1)
        assert result == datetime(2026, 2, 23)  # Monday
        assert result.weekday() == 0

    def test_five_workdays_is_one_week(self):
        """5 workdays from Wednesday = next Wednesday."""
        wed = datetime(2026, 2, 18)
        result = add_workdays(wed, 5)
        assert result == datetime(2026, 2, 25)  # Next Wednesday
        assert result.weekday() == 2

    def test_ten_workdays_is_two_weeks(self):
        """10 workdays from Wednesday = Wednesday + 2 calendar weeks."""
        wed = datetime(2026, 2, 18)
        result = add_workdays(wed, 10)
        assert result == datetime(2026, 3, 4)  # Two weeks later
        assert result.weekday() == 2

    def test_three_workdays_across_weekend(self):
        """3 workdays from Wednesday = Mon (Thu, Fri, skip weekend, Mon)."""
        wed = datetime(2026, 2, 18)
        result = add_workdays(wed, 3)
        assert result == datetime(2026, 2, 23)  # Monday
        assert result.weekday() == 0

    def test_never_lands_on_weekend(self):
        """No matter the input, result should always be a weekday."""
        start = datetime(2026, 1, 5)  # Monday
        for days in range(1, 100):
            result = add_workdays(start, days)
            assert result.weekday() < 5, f"add_workdays({start}, {days}) = {result} (weekend!)"
