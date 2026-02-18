# Multi-Epic Timeline Estimator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task.

**Goal:** Extend epic_timeline_estimator.py to handle multiple epics
simultaneously, tracking individual epic completion dates alongside overall
project completion.

**Architecture:** Add epic-awareness to the Issue class, implement multi-epic
fetching in EpicAnalyzer, track per-epic completion through simulation runs, and
output separate timelines for each epic plus overall project.

**Tech Stack:** Python 3, NetworkX (existing), Monte Carlo simulation (existing)

______________________________________________________________________

## Task 1: Add epic_key tracking to Issue class

**Files:**

- Modify: `issue_parser.py:11-26`
- Modify: `tests/test_issue_parser.py`

**Step 1: Update Issue class to include epic_key**

The Issue class needs an optional `epic_key` field to track which epic each
issue belongs to.

```python
class Issue:
    """Represents a Jira issue with dependencies"""

    def __init__(
        self,
        key: str,
        summary: str,
        status: str,
        story_points: float = 0,
        epic_key: str = None,
    ):
        self.key = key
        self.summary = summary
        self.status = status
        self.story_points = story_points
        self.epic_key = epic_key  # Track which epic this issue belongs to
        self.blocks: Set[str] = set()  # Issues this blocks
        self.blocked_by: Set[str] = set()  # Issues blocking this
        self.critical_path_length = 0
        self.earliest_start = 0
        self.is_complete = status.lower() in [
            "done",
            "closed",
            "duplicate",
            "won't fix",
        ]

    def __repr__(self):
        epic_info = f", epic={self.epic_key}" if self.epic_key else ""
        return f"Issue({self.key}, {self.story_points}pts, status={self.status}{epic_info})"
```

**Step 2: Update parse_jira_issues to accept and use epic_key parameter**

```python
def parse_jira_issues(
    raw_issues: List[Dict],
    story_points_field: str = "customfield_10115",
    epic_key: str = None,
) -> Dict[str, Issue]:
    """
    Parse raw Jira issues into Issue objects with dependencies

    Args:
        raw_issues: List of raw issue dictionaries from Jira API
        story_points_field: Custom field ID for story points
        epic_key: Optional epic key to tag all parsed issues with

    Returns:
        Dictionary mapping issue keys to Issue objects
    """
    issues = {}

    # First pass: Create Issue objects
    for raw in raw_issues:
        # Validate required fields
        if "key" not in raw or "fields" not in raw:
            print(f"⚠️  Skipping malformed issue: {raw.get('key', 'unknown')}")
            continue

        key = raw["key"]
        fields = raw["fields"]

        # Extract story points with fallback
        story_points = fields.get(story_points_field, 0)
        if story_points is None:
            story_points = 0

        # Handle missing fields gracefully
        summary = fields.get("summary", "No summary")
        status_obj = fields.get("status")
        status = (
            status_obj["name"] if status_obj and "name" in status_obj else "Unknown"
        )

        issue = Issue(
            key=key,
            summary=summary,
            status=status,
            story_points=float(story_points),
            epic_key=epic_key,
        )

        issues[key] = issue

    # Second pass: Parse dependencies (unchanged)
    for raw in raw_issues:
        # Skip if issue wasn't parsed in first pass
        if "key" not in raw or raw["key"] not in issues:
            continue

        key = raw["key"]
        issue = issues[key]

        for link in raw.get("fields", {}).get("issuelinks", []):
            link_type = link["type"]["name"].lower()

            # Handle different link types
            if "outwardIssue" in link:
                linked_key = link["outwardIssue"]["key"]
                outward = link["type"]["outward"].lower()

                if "block" in outward or "depend" in link_type:
                    # This issue blocks the linked issue
                    if linked_key in issues:
                        issue.blocks.add(linked_key)
                        issues[linked_key].blocked_by.add(key)

            if "inwardIssue" in link:
                linked_key = link["inwardIssue"]["key"]
                inward = link["type"]["inward"].lower()

                if "block" in inward or "depend" in link_type:
                    # The linked issue blocks this issue
                    if linked_key in issues:
                        issue.blocked_by.add(linked_key)
                        issues[linked_key].blocks.add(key)

    return issues
```

**Step 3: Write tests for epic_key tracking**

Add to `tests/test_issue_parser.py`:

```python
def test_issue_with_epic_key():
    """Test Issue object with epic_key."""
    issue = Issue(
        key="TEST-1",
        summary="Test issue",
        status="In Progress",
        story_points=5.0,
        epic_key="EPIC-1",
    )
    assert issue.key == "TEST-1"
    assert issue.epic_key == "EPIC-1"
    assert "epic=EPIC-1" in repr(issue)


def test_issue_without_epic_key():
    """Test Issue object without epic_key defaults to None."""
    issue = Issue(
        key="TEST-1", summary="Test issue", status="In Progress", story_points=5.0
    )
    assert issue.epic_key is None
    assert "epic=" not in repr(issue)


def test_parse_jira_issues_with_epic_key():
    """Test parsing Jira issues with epic_key."""
    raw_issues = [
        {
            "key": "TEST-1",
            "fields": {
                "summary": "First task",
                "status": {"name": "To Do"},
                "customfield_10115": 5,
            },
        },
        {
            "key": "TEST-2",
            "fields": {
                "summary": "Second task",
                "status": {"name": "To Do"},
                "customfield_10115": 3,
            },
        },
    ]

    issues = parse_jira_issues(raw_issues, epic_key="EPIC-1")

    assert issues["TEST-1"].epic_key == "EPIC-1"
    assert issues["TEST-2"].epic_key == "EPIC-1"
```

**Step 4: Run tests**

```bash
pytest tests/test_issue_parser.py::test_issue_with_epic_key -v
pytest tests/test_issue_parser.py::test_issue_without_epic_key -v
pytest tests/test_issue_parser.py::test_parse_jira_issues_with_epic_key -v
pytest tests/test_issue_parser.py -v
```

Expected: All new and existing tests pass.

**Step 5: Commit**

```bash
git add issue_parser.py tests/test_issue_parser.py
git commit -m "feat: add epic_key tracking to Issue class"
```

______________________________________________________________________

## Task 2: Add multi-epic fetching to EpicAnalyzer

**Files:**

- Modify: `epic_timeline_estimator.py:38-59`
- Modify: `tests/` (create test_epic_timeline_estimator.py if needed)

**Step 1: Add metadata fields to EpicAnalyzer.__init__**

```python
def __init__(
    self, jira_client: JiraClient, story_points_field: str = "customfield_10115"
):
    self.jira = jira_client
    self.story_points_field = story_points_field
    self.issues: Dict = {}
    self.epic_keys: List[str] = []  # Track which epics are being analyzed
    self.issues_by_epic: Dict[str, Dict] = {}  # Map epic_key -> issues dict
```

**Step 2: Keep existing fetch_epic_issues unchanged, add new
fetch_multi_epic_issues method**

```python
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
        epic_issues = parse_jira_issues(
            raw_issues, self.story_points_field, epic_key=epic_key
        )

        # Store per-epic and merge into main issues dict
        self.issues_by_epic[epic_key] = epic_issues
        self.issues.update(epic_issues)

    print(f"\nTotal issues across all epics: {len(self.issues)}")
```

**Step 3: Add method to get issues for a specific epic**

```python
def get_epic_issues(self, epic_key: str) -> Dict[str, Issue]:
    """Get all issues for a specific epic"""
    return self.issues_by_epic.get(epic_key, {})
```

**Step 4: Update main() to support multiple epic arguments**

Modify the argument parser:

```python
parser.add_argument(
    "epic_keys",
    nargs="+",  # Accept one or more epic keys
    help="Epic key(s) to analyze (e.g., PX-8350 or PX-8350 PX-8351)",
)
```

And update the fetch logic:

```python
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
```

**Step 5: Run existing tests to ensure backward compatibility**

```bash
pytest tests/ -v
```

Expected: All tests pass.

**Step 6: Commit**

```bash
git add epic_timeline_estimator.py
git commit -m "feat: add multi-epic fetching support to EpicAnalyzer"
```

______________________________________________________________________

## Task 3: Track per-epic completion in simulation

**Files:**

- Modify: `epic_timeline_estimator.py:134-258`

**Step 1: Add helper method to get epic completion time from simulation**

Add to `EpicAnalyzer` class:

```python
def _calculate_epic_completion_workday(
    self,
    epic_key: str,
    critical_path_points: float,
    total_points: float,
    developers: float,
    coordination_factor: float,
    variance: float,
) -> float:
    """
    Calculate when a specific epic completes in a single simulation run.

    Returns the cumulative workdays when all issues for this epic are complete.
    """
    # Get issues for this epic
    epic_issues = self.get_epic_issues(epic_key)
    if not epic_issues:
        return 0.0

    # Calculate metrics for this epic only
    epic_total_points = sum(
        i.story_points for i in epic_issues.values() if not i.is_complete
    )

    # Build subgraph for this epic (only its issues)
    from issue_parser import build_dependency_graph, handle_cycles

    # Create a filtered issues dict with only this epic's issues
    filtered_issues = {
        k: v
        for k, v in self.issues.items()
        if v.epic_key == epic_key and not v.is_complete
    }

    G = build_dependency_graph(filtered_issues, include_completed=False)
    G = handle_cycles(G)

    # Get critical path for this epic
    from issue_parser import calculate_critical_path

    epic_critical_path_points, _ = calculate_critical_path(G)

    # Simulate this epic's completion using same logic as overall project
    effective_developers = developers * random.gauss(1.0, variance)
    effective_developers = max(0.5, effective_developers)

    efficiency = self._compute_team_efficiency(
        effective_developers, coordination_factor
    )
    parallel_days = (
        epic_total_points / effective_developers
        if effective_developers > 0
        else float("inf")
    )
    sequential_days = epic_critical_path_points
    workdays = max(parallel_days, sequential_days)
    workdays = workdays / efficiency

    return workdays
```

**Step 2: Modify estimate_timeline to track per-epic completion**

Update the method signature:

```python
def estimate_timeline(
    self,
    epic_keys: List[str] = None,  # Can be None for backward compat (uses self.epic_keys)
    developers: float = None,
    points_per_sprint_per_dev: float = None,
    sprint_weeks: int = None,
    coordination_factor: float = 0.15,
    simulations: int = 10000,
    variance: float = 0.10,
) -> Dict:
```

Replace the old single `epic_key` parameter with `epic_keys`.

**Step 3: Initialize epic_keys if not provided**

```python
if epic_keys is None:
    epic_keys = (
        self.epic_keys
        if self.epic_keys
        else [list(self.issues.values())[0].epic_key] if self.issues else []
    )

if not epic_keys:
    raise ValueError("No epics provided or found")

print("\nEstimating timeline...")
print(f"Analyzing {len(epic_keys)} epic(s): {', '.join(epic_keys)}")
```

**Step 4: Add per-epic tracking to Monte Carlo loop**

Replace the simulation loop:

```python
# Monte Carlo simulation for workday-based estimation
workday_results: List[float] = []
epic_workday_results: Dict[str, List[float]] = {epic: [] for epic in epic_keys}

for _ in range(simulations):
    workdays = self._simulate_workdays_for_run(
        critical_path_points,
        total_points,
        developers,
        coordination_factor,
        variance=variance,
    )
    workday_results.append(workdays)

    # Track per-epic completion times
    for epic_key in epic_keys:
        epic_workdays = self._calculate_epic_completion_workday(
            epic_key,
            critical_path_points,
            total_points,
            developers,
            coordination_factor,
            variance,
        )
        epic_workday_results[epic_key].append(epic_workdays)

# Sort results for percentile calculation
workday_results.sort()
for epic in epic_workday_results:
    epic_workday_results[epic].sort()
```

**Step 5: Calculate per-epic percentiles**

After calculating p50/p85/p95 for overall project, add:

```python
# Calculate per-epic percentiles
epic_estimates = {}
for epic_key in epic_keys:
    epic_results = epic_workday_results[epic_key]

    p50_idx = int(len(epic_results) * 0.50)
    p85_idx = int(len(epic_results) * 0.85)
    p95_idx = int(len(epic_results) * 0.95)

    epic_p50_workdays = epic_results[p50_idx]
    epic_p85_workdays = epic_results[p85_idx]
    epic_p95_workdays = epic_results[p95_idx]

    # Convert to calendar dates
    epic_p50_weeks = epic_p50_workdays / 5
    epic_p85_weeks = epic_p85_workdays / 5
    epic_p95_weeks = epic_p95_workdays / 5

    epic_p50_end_date = now + timedelta(weeks=epic_p50_weeks)
    epic_p85_end_date = now + timedelta(weeks=epic_p85_weeks)
    epic_p95_end_date = now + timedelta(weeks=epic_p95_weeks)

    # Get issue counts for this epic
    epic_issues = self.get_epic_issues(epic_key)
    epic_total_points = sum(
        i.story_points for i in epic_issues.values() if not i.is_complete
    )

    epic_estimates[epic_key] = {
        "epic_key": epic_key,
        "total_points": epic_total_points,
        "p50_workdays": round(epic_p50_workdays, 1),
        "p85_workdays": round(epic_p85_workdays, 1),
        "p95_workdays": round(epic_p95_workdays, 1),
        "p50_weeks": round(epic_p50_weeks, 1),
        "p85_weeks": round(epic_p85_weeks, 1),
        "p95_weeks": round(epic_p95_weeks, 1),
        "p50_end_date": epic_p50_end_date.strftime("%Y-%m-%d"),
        "p85_end_date": epic_p85_end_date.strftime("%Y-%m-%d"),
        "p95_end_date": epic_p95_end_date.strftime("%Y-%m-%d"),
    }
```

**Step 6: Return updated result dictionary**

Update the return statement to include epic summaries:

```python
return {
    "epics": epic_keys,
    "epic_summaries": epic_estimates,
    "epic_key": epic_keys[0] if len(epic_keys) == 1 else None,  # For backward compat
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
    # Monte Carlo workday estimates (p50/p85/p95) - overall project
    "p50_workdays": round(p50_workdays, 1),
    "p85_workdays": round(p85_workdays, 1),
    "p95_workdays": round(p95_workdays, 1),
    "min_workdays_critical": min_workdays_critical,
    # Calendar projections - overall project
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
```

**Step 7: Run tests**

```bash
pytest tests/ -v
```

Expected: All tests pass.

**Step 8: Commit**

```bash
git add epic_timeline_estimator.py
git commit -m "feat: add per-epic completion tracking to Monte Carlo simulation"
```

______________________________________________________________________

## Task 4: Update print_summary for multi-epic output

**Files:**

- Modify: `epic_timeline_estimator.py:260-315`

**Step 1: Create new print_epic_summary helper method**

```python
def _print_epic_summary(self, epic_key: str, epic_summary: Dict) -> None:
    """Print summary for a single epic"""
    print(f"\n📌 Epic: {epic_key}")
    print(f"  Total Points: {epic_summary['total_points']:.1f}")
    print(
        f"  p50 (50% confidence): {epic_summary['p50_weeks']:.1f} weeks → {epic_summary['p50_end_date']} ({int(epic_summary['p50_weeks'] * 7)} days)"
    )
    print(
        f"  p85 (85% confidence): {epic_summary['p85_weeks']:.1f} weeks → {epic_summary['p85_end_date']} ({int(epic_summary['p85_weeks'] * 7)} days)"
    )
    print(
        f"  p95 (95% confidence): {epic_summary['p95_weeks']:.1f} weeks → {epic_summary['p95_end_date']} ({int(epic_summary['p95_weeks'] * 7)} days)"
    )
```

**Step 2: Update print_summary to handle multiple epics**

```python
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
    print(
        f"  Velocity: {timeline['points_per_sprint_per_dev']:.1f} points/sprint/developer"
    )
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
    print(
        f"  Minimum (critical path only): {timeline['min_workdays_critical']:.1f} days"
    )
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
```

**Step 3: Update main() to pass correct arguments to estimate_timeline**

```python
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
```

**Step 4: Run tests**

```bash
pytest tests/ -v
```

Expected: All tests pass.

**Step 5: Commit**

```bash
git add epic_timeline_estimator.py
git commit -m "feat: update output formatting for multi-epic analysis"
```

______________________________________________________________________

## Task 5: Update docstring and backward compatibility

**Files:**

- Modify: `epic_timeline_estimator.py:1-20`

**Step 1: Update module docstring**

```python
"""
Epic Timeline Estimator with Monte Carlo Workday Estimation

Analyzes Jira epic(s) to estimate completion timeline based on:
- Story points and dependencies (blockers)
- Team capacity (developers, points per sprint)
- Critical path through dependency graph
- Monte Carlo simulation for probabilistic estimates (p50/p85/p95)
- Brooks's Law coordination overhead factor for team efficiency
- Multi-epic support with per-epic completion tracking

Usage (single epic):
    python epic_timeline_estimator.py PX-8350 \\
        --developers 3.25 \\
        --points-per-sprint 8 \\
        --sprint-weeks 2 \\
        --coordination-factor 0.15 \\
        --variance 0.10 \\
        --simulations 10000

Usage (multiple epics):
    python epic_timeline_estimator.py PX-8350 PX-8351 PX-8352 \\
        --developers 3.25 \\
        --points-per-sprint 8 \\
        --sprint-weeks 2 \\
        --coordination-factor 0.15 \\
        --variance 0.10 \\
        --simulations 10000
"""
```

**Step 2: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass, backward compatibility maintained.

**Step 3: Manual test with single epic (backward compatibility)**

```bash
# Test single epic still works
python epic_timeline_estimator.py PX-8350 --json
```

Expected: Output includes single epic analysis.

**Step 4: Commit**

```bash
git add epic_timeline_estimator.py
git commit -m "docs: update module docstring for multi-epic support"
```

______________________________________________________________________

## Integration Testing

**Files:**

- Create: `tests/test_epic_timeline_estimator.py`

**Step 1: Write integration test for single epic (backward compat)**

```python
import pytest
from unittest.mock import MagicMock, patch
from epic_timeline_estimator import EpicAnalyzer


@pytest.fixture
def mock_jira_client():
    """Create a mock Jira client"""
    client = MagicMock()
    return client


def test_single_epic_analysis(mock_jira_client):
    """Test single epic analysis for backward compatibility"""
    analyzer = EpicAnalyzer(mock_jira_client)

    # Mock issues
    raw_issues = [
        {
            "key": "TEST-1",
            "fields": {
                "summary": "Task 1",
                "status": {"name": "To Do"},
                "customfield_10115": 5,
                "issuelinks": [],
            },
        },
        {
            "key": "TEST-2",
            "fields": {
                "summary": "Task 2",
                "status": {"name": "To Do"},
                "customfield_10115": 3,
                "issuelinks": [],
            },
        },
    ]

    mock_jira_client.search_jql.return_value = raw_issues

    analyzer.fetch_epic_issues("EPIC-1")

    assert len(analyzer.issues) == 2
    assert "TEST-1" in analyzer.issues
    assert "TEST-2" in analyzer.issues
```

**Step 2: Write integration test for multi-epic**

```python
def test_multi_epic_analysis(mock_jira_client):
    """Test multi-epic analysis"""
    analyzer = EpicAnalyzer(mock_jira_client)

    # Mock issues for multiple epics
    def mock_search(jql, fields, max_results):
        if "parent = EPIC-1" in jql:
            return [
                {
                    "key": "TEST-1",
                    "fields": {
                        "summary": "Epic 1 Task 1",
                        "status": {"name": "To Do"},
                        "customfield_10115": 5,
                        "issuelinks": [],
                    },
                },
            ]
        elif "parent = EPIC-2" in jql:
            return [
                {
                    "key": "TEST-2",
                    "fields": {
                        "summary": "Epic 2 Task 1",
                        "status": {"name": "To Do"},
                        "customfield_10115": 3,
                        "issuelinks": [],
                    },
                },
            ]
        return []

    mock_jira_client.search_jql.side_effect = mock_search

    analyzer.fetch_multi_epic_issues(["EPIC-1", "EPIC-2"])

    assert len(analyzer.issues) == 2
    assert len(analyzer.epic_keys) == 2
    assert "EPIC-1" in analyzer.issues_by_epic
    assert "EPIC-2" in analyzer.issues_by_epic
    assert analyzer.issues["TEST-1"].epic_key == "EPIC-1"
    assert analyzer.issues["TEST-2"].epic_key == "EPIC-2"
```

**Step 3: Run integration tests**

```bash
pytest tests/test_epic_timeline_estimator.py -v
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add tests/test_epic_timeline_estimator.py
git commit -m "test: add integration tests for multi-epic support"
```

______________________________________________________________________

## Verification Checklist

Before marking complete:

- [ ] All existing tests pass
- [ ] New tests for epic_key tracking pass
- [ ] Multi-epic fetching works correctly
- [ ] Per-epic completion dates are calculated
- [ ] Output formatting displays all information clearly
- [ ] Single-epic usage still works (backward compatible)
- [ ] JSON output includes epic_summaries
- [ ] Manual testing with multiple epics works
