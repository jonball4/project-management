# Project Timeline Estimation Toolkit

A focused toolkit for accurate project timeline estimation using live Jira data,
featuring discrete event Monte Carlo simulation, NetworkX-powered critical path
analysis, and team optimization.

## Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd project-management
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set Jira credentials
export JIRA_BASE_URL="https://your-company.atlassian.net"
export JIRA_EMAIL="your-email@company.com"
export JIRA_TOKEN="your-jira-api-token"

# Estimate a single epic
python3 epic_timeline_estimator.py PX-8350 \
    --developers 3.25 \
    --points-per-sprint 8

# Estimate multiple epics as one project
python3 epic_timeline_estimator.py PX-9911 PX-9912 PX-9913 \
    --developers 2.5 \
    --points-per-sprint 10
```

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
- [How the Simulator Works](#how-the-simulator-works)
- [Development](#development)
- [Tools Reference](#tools-reference)
- [Data Sources](#data-sources)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

This toolkit provides two focused tools for accurate project timeline
estimation:

### 1. **Epic Timeline Estimator** (`epic_timeline_estimator.py`)

Monte Carlo discrete event simulator for Jira epics.

**Use for:** Active Jira epics, multi-epic project planning, progress tracking

**Features:**

- **Multi-Epic Support** - Analyze one or more epics as a single project with
  per-epic completion dates
- **Monte Carlo Simulation** - 10,000 discrete event simulations producing
  p50/p85/p95 confidence intervals
- **Discrete Event Simulator** - Workday-by-workday simulation with per-engineer
  ticket assignment
- **Priority Scheduling** - Engineers pick tickets that unblock the most
  downstream work first (DAG descendant count)
- **Brooks's Law** - Team efficiency degrades with size:
  `efficiency = 1 / (1 + factor * log2(team_size))`
- **Weekend-Aware Dates** - Projected completion dates always land on weekdays
- **Critical Path Analysis** - NetworkX DAG algorithms for dependency-aware
  scheduling
- **Dependency Management** - Automatic dependency parsing with cycle detection
  and recovery
- **Visual DAG Export** - Dependency graph visualization with status color
  coding

### 2. **Engineer Optimization** (`engineer_optimization.py`)

Analyzes optimal team size using diminishing returns analysis.

**Use for:** Finding the right team size for Jira epics, avoiding over-staffing

**Features:**

- **Live Jira Integration** - Analyzes actual epic data for team size
  optimization
- **Team Size Analysis** - Find optimal team size before diminishing returns
  kick in
- **Efficiency Metrics** - Utilization rates and workload distribution analysis
- **Visual Charts** - Duration vs. team size with efficiency curves
- **Critical Path Aware** - Shows theoretical minimum duration limit

## Installation

### Prerequisites

- Python 3.8+
- Jira account with API access
- GraphViz (optional, for dependency graph visualization)

### Quick Install

```bash
# Clone repository
git clone <repository-url>
cd project-management

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package
pip install -e .

# Optional: Install with visualization support
pip install -e ".[viz]"
```

### Development Install

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Setup pre-commit hooks
pre-commit install

# Or use Make for complete setup
make setup
```

### Jira Configuration

```bash
# Set environment variables for Jira v3 API
export JIRA_BASE_URL="https://your-company.atlassian.net"
export JIRA_EMAIL="your-email@company.com"
export JIRA_TOKEN="your-jira-api-token"
```

**Get your Jira API token:**

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
1. Click "Create API token"
1. Copy the token and set it as `JIRA_TOKEN`

## Basic Usage

### Single Epic Estimation

```bash
python3 epic_timeline_estimator.py PX-8350 \
    --developers 3.25 \
    --points-per-sprint 8 \
    --sprint-weeks 2
```

### Multi-Epic Project Estimation

Analyze multiple epics as one project. All work items are placed in a single
DAG, engineers work across all epics, and each epic gets individual p50/p85/p95
dates alongside the overall project completion date.

```bash
python3 epic_timeline_estimator.py PX-9911 PX-9912 PX-9913 PX-9914 \
    --developers 2.5 \
    --points-per-sprint 10 \
    --sprint-weeks 2
```

**Output includes:**

- Overall project p50/p85/p95 completion dates
- Per-epic p50/p85/p95 completion dates
- Critical path analysis across all epics
- Team configuration and efficiency metrics

### Export Dependency Graph

```bash
python3 epic_timeline_estimator.py PX-8350 \
    --developers 3.25 \
    --points-per-sprint 8 \
    --export-dag
```

**Output:**

- `epic_dag.dot` - GraphViz DOT file
- `epic_dag.png` - Rendered dependency graph (requires graphviz)
- Green nodes: completed issues
- Blue nodes: remaining work

### Find Optimal Team Size

```bash
python3 engineer_optimization.py PX-8350 \
    --max-engineers 10 \
    --output "team-optimization"
```

**Output:**

- `output/team-optimization.png` - Scaling analysis charts
- `output/team-optimization.json` - Detailed optimization data
- Console report with optimal team size recommendation

## How the Simulator Works

### Discrete Event Monte Carlo Simulation

The estimator runs 10,000 simulation iterations (configurable). Each iteration:

1. **Apply variance** to each work item's story points (fixed per run, Gaussian
   with configurable std dev)
1. **Compute daily capacity** per engineer:
   `capacity = points_per_sprint_per_dev / (sprint_weeks * 5)`
1. **Apply Brooks's Law** efficiency:
   `effective_capacity = capacity * (1 / (1 + factor * log2(team_size)))`
1. **Simulate workday-by-workday:**
   - Idle engineers claim the next available ticket
   - Tickets are prioritized by downstream descendant count (most-blocking
     first)
   - Each engineer works on exactly one ticket at a time (no sharing)
   - Dependencies must be fully resolved before a ticket is available
   - Completed tickets free the engineer for new work
1. **Track per-epic and overall completion days**

After all simulations, results are sorted and p50/p85/p95 percentiles are
extracted. Completion dates are projected using weekday-only arithmetic (no
weekends).

### Priority Scheduling

Engineers don't pick tickets in arbitrary order. Before simulation begins, each
ticket's descendant count is computed from the dependency DAG. When an engineer
is idle, they pick the available (unblocked, unclaimed) ticket with the most
downstream dependents. This ensures:

- Blockers are resolved as early as possible
- Small independent tickets don't get starved behind large backlogs
- Critical path work is naturally prioritized

### Brooks's Law

Team efficiency degrades logarithmically with team size:

```
efficiency = 1 / (1 + coordination_factor * log2(team_size))
```

With the default coordination factor of 0.15:

| Team Size | Efficiency |
| --------- | ---------- |
| 1         | 100%       |
| 2         | 87%        |
| 4         | 77%        |
| 8         | 69%        |

### Critical Path Analysis

The toolkit uses NetworkX's `dag_longest_path` algorithm to find the critical
path - the longest chain of dependent work items. This represents the absolute
minimum project duration regardless of team size.

### Cycle Detection and Recovery

Circular dependencies are detected and handled:

- All cycles are reported to the user
- One edge per cycle is removed to create a valid DAG
- Estimation continues with degraded but functional results

## Advanced Usage

### Complete Project Lifecycle

```bash
# Phase 1: Find Optimal Team Size
python3 engineer_optimization.py PA-100 \
    --max-engineers 12 \
    --output team-analysis \
    --export-dag

# Phase 2: Get Detailed Timeline Estimate
python3 epic_timeline_estimator.py PA-100 \
    --developers 6 \
    --points-per-sprint 8 \
    --sprint-weeks 2

# Phase 3: Track Progress Over Time (run weekly)
python3 epic_timeline_estimator.py PA-100 \
    --developers 6 \
    --json > weekly-report-$(date +%Y%m%d).json

# Phase 4: Multi-epic project estimation
python3 epic_timeline_estimator.py PA-100 PA-101 PA-102 \
    --developers 6 \
    --points-per-sprint 8
```

### Tuning Simulation Parameters

```bash
python3 epic_timeline_estimator.py PX-8350 \
    --developers 3.25 \
    --points-per-sprint 8 \
    --sprint-weeks 2 \
    --coordination-factor 0.15 \  # Brooks's Law factor (0 = no overhead)
    --variance 0.10 \             # Per-item variance std dev (0 = deterministic)
    --simulations 10000           # Number of Monte Carlo iterations
```

**Variance guidance:**

- `0.0` - Deterministic (no randomness, useful for debugging)
- `0.05-0.10` - Low variance (stable, well-understood work)
- `0.15-0.25` - Moderate variance (typical software projects)
- `0.30+` - High variance (research, new technology, high uncertainty)

**Coordination factor guidance:**

- `0.0` - No coordination overhead (unrealistic for teams > 1)
- `0.10-0.15` - Typical for co-located teams with good processes
- `0.20-0.30` - Distributed teams or high coordination needs
- `0.50+` - Very high overhead (new teams, complex integration)

## Development

This project follows modern Python best practices with automated code quality
tools.

### Development Setup

```bash
# Quick setup with Make
make setup

# Or manual setup
pip install -e ".[dev]"
pre-commit install
```

### Code Quality Tools

| Tool           | Purpose              | Command            |
| -------------- | -------------------- | ------------------ |
| **Black**      | Code formatting      | `make format`      |
| **Ruff**       | Fast Python linter   | `make lint`        |
| **MyPy**       | Static type checking | `make type-check`  |
| **Pytest**     | Testing framework    | `make test`        |
| **Pre-commit** | Git hooks            | `make pre-commit`  |
| **Bandit**     | Security scanning    | Runs in pre-commit |

### Running Tests

```bash
# Run all tests
make test

# Run with coverage report
make test-cov

# Run specific test file
pytest tests/test_epic_timeline_estimator.py -v

# Run specific test class
pytest tests/test_epic_timeline_estimator.py::TestSimulateWorkdays -v
```

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit:

- Trailing whitespace removal
- End-of-file fixing
- YAML/JSON/TOML validation
- Black formatting
- Ruff linting
- MyPy type checking
- Bandit security scanning
- Markdown formatting

### Project Structure

```
project-management/
├── pyproject.toml              # Modern Python packaging
├── .pre-commit-config.yaml     # Pre-commit hooks config
├── Makefile                    # Development commands
├── .editorconfig               # Editor configuration
├── .github/                    # GitHub Actions CI/CD
│   └── workflows/
├── tests/                      # Test suite
│   ├── test_epic_timeline_estimator.py  # Simulator tests (41 tests)
│   ├── test_issue_parser.py    # Parser tests
│   ├── test_scheduler.py       # Scheduler tests
│   └── conftest.py             # Shared fixtures
├── jira_client.py             # Common: Jira v3 API client
├── issue_parser.py            # Common: Issue parsing & dependency graphs
├── scheduler.py               # Common: Task scheduling
├── dag_exporter.py            # Common: DAG visualization
├── epic_timeline_estimator.py # Tool 1: Monte Carlo timeline estimation
├── engineer_optimization.py   # Tool 2: Team size optimization
└── docs/plans/                # Design documents
```

## Tools Reference

### epic_timeline_estimator.py

**Purpose**: Monte Carlo discrete event simulation for Jira epic timeline
estimation.

**Positional Arguments:**

- `epic_keys`: One or more epic keys (e.g., `PX-8350` or `PX-8350 PX-8351`)

**Options:**

| Flag                    | Default | Description                           |
| ----------------------- | ------- | ------------------------------------- |
| `--developers`          | 3.25    | Number of FTE developers              |
| `--points-per-sprint`   | 8       | Story points per sprint per developer |
| `--sprint-weeks`        | 2       | Sprint length in weeks                |
| `--coordination-factor` | 0.15    | Brooks's Law overhead factor          |
| `--variance`            | 0.10    | Per-item variance std dev             |
| `--simulations`         | 10000   | Number of Monte Carlo iterations      |
| `--export-dag`          | -       | Export dependency graph as DOT/PNG    |
| `--json`                | -       | Output results as JSON                |

**Output:**

- p50/p85/p95 completion dates (overall and per-epic)
- Critical path analysis with issue breakdown
- Team configuration and efficiency metrics
- Optional: dependency graph visualization

### engineer_optimization.py

**Purpose**: Analyze optimal team size using diminishing returns analysis.

**Options:**

| Flag                   | Default               | Description                        |
| ---------------------- | --------------------- | ---------------------------------- |
| `epic_key`             | -                     | Jira epic key (positional)         |
| `--max-engineers`      | 12                    | Maximum team size to analyze       |
| `--output`             | engineer-optimization | Output file prefix                 |
| `--story-points-field` | customfield_10115     | Jira custom field for story points |
| `--export-dag`         | -                     | Export dependency graph            |

## Data Sources

### Live Jira Data

Both tools pull real-time data from Jira v3 API:

**Fetched Data:**

- Issue keys and summaries
- Story points (customfield_10115 - configurable)
- Issue status (Done, In Progress, etc.)
- Issue links (blocks/blocked by relationships)
- Parent hierarchy (uses `parent = EPIC-KEY` JQL)

**Automatic Filtering:**

- Excludes completed issues from simulation (Done, Closed, Duplicate, Won't Fix)
- Tracks completion percentage
- Handles missing story points gracefully (defaults to 0)

### Common Modules

- `jira_client.py` - Jira v3 API client with pagination
- `issue_parser.py` - Issue parsing, dependency graph building, epic key
  tracking
- `scheduler.py` - Task scheduling across engineers
- `dag_exporter.py` - Dependency graph visualization

## Configuration

### Environment Variables

```bash
export JIRA_BASE_URL="https://your-company.atlassian.net"
export JIRA_EMAIL="user@company.com"
export JIRA_TOKEN="your-api-token"
```

### Custom Story Points Field

```bash
python3 epic_timeline_estimator.py PX-8350 \
    --developers 3.25 \
    --story-points-field customfield_12345
```

To find your story points field ID:

```bash
curl -u "$JIRA_EMAIL:$JIRA_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/field" | jq '.[] | select(.name | contains("Story Points"))'
```

## Troubleshooting

### Common Issues

**1. "Missing required environment variables"**

```bash
export JIRA_BASE_URL="https://your-company.atlassian.net"
export JIRA_EMAIL="your-email@company.com"
export JIRA_TOKEN="your-api-token"

# Test connection
python3 -c "
from jira_client import JiraClient
jira = JiraClient()
print('Jira connection successful')
"
```

**2. "No issues found for epic"**

```bash
# Verify epic exists and has child issues
curl -u "$JIRA_EMAIL:$JIRA_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/search?jql=parent=PX-8350"

# The tool uses parent hierarchy: parent = EPIC-KEY
```

**3. "Circular dependencies detected"**

The system reports cycles and continues with degraded accuracy. Fix in Jira by
removing one blocking link from the cycle.

**4. "Story points not showing (all 0 points)"**

```bash
# Find your custom field ID
curl -u "$JIRA_EMAIL:$JIRA_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/field" | jq '.[] | select(.name | contains("Story"))'

# Pass it via --story-points-field
```

### Story Point Guidelines

- **1 point**: \<= 1 day of work
- **2 points**: 2 days of work
- **3 points**: 3 days of work
- **5 points**: 5 days of work
- **8+ points**: Consider splitting the task
- **Missing points**: Handled gracefully (defaults to 0)

### Dependency Management in Jira

- Use "blocks/blocked by" link types (automatically parsed)
- Keep dependency chains reasonable (\<10 levels)
- The tool detects and reports circular dependencies
- Review dependency graph with `--export-dag`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

```bash
make setup       # Complete development setup
make test        # Run test suite
make format      # Format code with black & ruff
make lint        # Run ruff linter
make type-check  # Run mypy type checker
make pre-commit  # Run all pre-commit hooks
```

## License

MIT License - see LICENSE file for details.
