# Project Timeline Estimation Toolkit

A focused toolkit for accurate project timeline estimation using live Jira data
and CSV-based planning, featuring NetworkX-powered critical path analysis and
team optimization.

## 🚀 Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd project-management
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set Jira credentials (for epic timeline estimator)
export JIRA_BASE_URL="https://your-company.atlassian.net"
export JIRA_EMAIL="your-email@company.com"
export JIRA_TOKEN="your-jira-api-token"

# Run demo
chmod +x example.sh
./example.sh
```

## 📋 Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
- [Development](#development)
- [Mathematical Foundations](#mathematical-foundations)
- [Tools Reference](#tools-reference)
- [Data Sources](#data-sources)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This toolkit provides two focused tools for accurate project timeline
estimation:

### 1. **Epic Timeline Estimator** (`epic_timeline_estimator.py`)

Analyzes live Jira epics with production-grade critical path analysis

**Use for:** Active Jira epics, progress tracking, accurate timeline estimates

**Features:**

- ✅ **Live Jira Integration** - Real-time data from Jira API with automatic
  status tracking
- ✅ **Critical Path Analysis** - NetworkX DAG algorithms (`dag_longest_path`)
  for accurate scheduling
- ✅ **Dual Estimation Methods** - Sprint-based and work-days based estimates
  with parallelization constraints
- ✅ **Dependency Management** - Automatic dependency parsing with cycle
  detection and recovery
- ✅ **Buffer Management** - Configurable overhead buffer (default 20%) for
  realistic planning
- ✅ **Visual DAG Export** - Dependency graph visualization with status color
  coding

### 2. **Engineer Optimization** (`engineer_optimization.py`)

Analyzes optimal team size using diminishing returns analysis

**Use for:** Finding the right team size for Jira epics, avoiding over-staffing

**Features:**

- ✅ **Live Jira Integration** - Analyzes actual epic data for team size
  optimization
- ✅ **Team Size Analysis** - Find optimal team size before diminishing returns
  kick in
- ✅ **Efficiency Metrics** - Utilization rates and workload distribution
  analysis
- ✅ **Visual Charts** - Duration vs. team size with efficiency curves
- ✅ **Critical Path Aware** - Shows theoretical minimum duration limit

## 🔧 Installation

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

### Optional: GraphViz for Visualization

```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt install graphviz

# Then install Python bindings
pip install -e ".[viz]"
```

### Jira Configuration (for epic_timeline_estimator.py)

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

## 📚 Basic Usage

### 1. Epic Timeline Estimation

Analyze a Jira epic with critical path analysis:

```bash
python3 epic_timeline_estimator.py PX-8350 \
    --developers 3.25 \
    --points-per-sprint 8 \
    --sprint-weeks 2 \
    --buffer 20
```

**Output:**

- Console report with dual estimation methods (sprint-based and work-days)
- Critical path analysis with issue breakdown
- Completion metrics and team utilization
- Optional: `--export-dag` for dependency graph visualization
- Optional: `--json` for machine-readable output

### 2. Export Dependency Graph

Visualize epic dependencies with status color coding:

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

### 3. Find Optimal Team Size

Analyze the best number of engineers for a Jira epic:

```bash
python3 engineer_optimization.py PX-8350 \
    --max-engineers 10 \
    --output "team-optimization"
```

**Output:**

- `output/team-optimization.png` - Scaling analysis charts
- `output/team-optimization.json` - Detailed optimization data
- Console report with optimal team size recommendation

**Optional: Export dependency graph**

```bash
python3 engineer_optimization.py PX-8350 \
    --max-engineers 10 \
    --export-dag
```

## 👨‍💻 Development

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
pytest tests/test_issue_parser.py

# Run specific test
pytest tests/test_issue_parser.py::test_issue_creation -v
```

### Code Formatting

```bash
# Format all code (black + ruff)
make format

# Check formatting without changes
black --check .
ruff check .
```

### Type Checking

```bash
# Run mypy on all files
make type-check

# Run on specific file
mypy issue_parser.py
```

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit:

- ✅ Trailing whitespace removal
- ✅ End-of-file fixing
- ✅ YAML/JSON/TOML validation
- ✅ Black formatting
- ✅ Ruff linting
- ✅ MyPy type checking
- ✅ Bandit security scanning
- ✅ Markdown formatting

```bash
# Run manually on all files
make pre-commit

# Skip hooks (not recommended)
git commit --no-verify
```

### Project Structure

```
project-management/
├── pyproject.toml              # Modern Python packaging
├── .pre-commit-config.yaml     # Pre-commit hooks config
├── Makefile                    # Development commands
├── .editorconfig               # Editor configuration
├── .github/                    # GitHub Actions CI/CD
│   ├── workflows/
│   │   ├── ci.yml             # Test & lint pipeline
│   │   └── release.yml        # Release automation
│   ├── ISSUE_TEMPLATE/        # Issue templates
│   └── PULL_REQUEST_TEMPLATE.md
├── tests/                      # Test suite
│   ├── test_issue_parser.py
│   ├── test_scheduler.py
│   └── conftest.py            # Shared fixtures
├── jira_client.py             # Common: Jira API
├── issue_parser.py            # Common: Parsing & graphs
├── scheduler.py               # Common: Task scheduling
├── dag_exporter.py            # Common: Visualization
├── epic_timeline_estimator.py # Tool 1: Timeline estimation
├── engineer_optimization.py   # Tool 2: Team optimization
├── CONTRIBUTING.md            # Contribution guidelines
├── ARCHITECTURE.md            # Technical documentation
└── LICENSE                    # MIT License
```

### Continuous Integration

GitHub Actions automatically:

- ✅ Run tests on Python 3.8-3.12
- ✅ Check code formatting
- ✅ Run linters and type checkers
- ✅ Generate coverage reports
- ✅ Run security scans

See `.github/workflows/ci.yml` for details.

## 🎓 Advanced Usage

### Complete Project Lifecycle

```bash
# Phase 1: Find Optimal Team Size
python3 engineer_optimization.py PA-100 \
    --max-engineers 12 \
    --output team-analysis \
    --export-dag

# Review output/team-analysis.png to determine optimal team size
# Example output: "Optimal team size: 6 engineers"

# Phase 2: Get Detailed Timeline Estimate
python3 epic_timeline_estimator.py PA-100 \
    --developers 6 \
    --points-per-sprint 8 \
    --sprint-weeks 2 \
    --export-dag

# Phase 3: Track Progress Over Time
# Run weekly to see updated estimates as work progresses
python3 epic_timeline_estimator.py PA-100 \
    --developers 6 \
    --json > weekly-report-$(date +%Y%m%d).json

# Phase 4: Adjust Team Size if Needed
# If timeline is too long, check if adding engineers helps
python3 engineer_optimization.py PA-100 --max-engineers 10
python3 epic_timeline_estimator.py PA-100 --developers 8  # Test new size
```

### Comparing Estimation Methods

The epic timeline estimator provides two complementary approaches:

```bash
# Run estimation with default settings
python3 epic_timeline_estimator.py PX-8350 --developers 3.25

# Output shows both methods:
# 1. Sprint-Based: Uses team velocity (points per sprint)
#    - Accounts for sprint ceremonies and overhead
#    - Best for established teams with known velocity
#
# 2. Work-Days Based: Assumes 1 point = 1 day
#    - More granular daily tracking
#    - Useful for new teams or variable capacity
#
# The tool takes max(parallel, sequential) for both methods
# to account for parallelization constraints
```

### Understanding Critical Path

```bash
# Critical path shows the longest dependency chain
python3 epic_timeline_estimator.py PX-8350 --developers 3.25 --export-dag

# Key insights:
# - Critical path length = minimum possible duration
# - Cannot be parallelized (sequential constraint)
# - Focus optimization efforts on critical path tasks
# - Adding engineers won't help if critical path is the bottleneck
```

## 🧮 Mathematical Foundations

### Critical Path Analysis (NetworkX DAG Algorithms)

The epic timeline estimator uses NetworkX's `dag_longest_path` algorithm:

```python
# Build directed acyclic graph with story points as edge weights
G = nx.DiGraph()
for issue in issues:
    G.add_node(issue.key, story_points=issue.story_points)
    for blocked_issue in issue.blocks:
        G.add_edge(issue.key, blocked_issue, weight=issue.story_points)

# Calculate critical path (longest path through DAG)
critical_path = nx.dag_longest_path(G, weight="weight")
critical_path_length = nx.dag_longest_path_length(G, weight="weight")
```

**Mathematical Properties:**

- **Lower Bound**: No project can complete faster than the critical path
- **Dependency Constraint**:
  `start_time(task) ≥ max(end_time(dependency)) for all dependencies`
- **Parallelization Limit**: Critical path work cannot be parallelized
- **Time Complexity**: O(V + E) using dynamic programming on DAG

### Dual Estimation Model

The system provides two complementary estimates and takes the maximum:

**1. Sprint-Based Estimation:**

```
min_sprints_parallel = total_points / team_capacity_per_sprint
min_sprints_sequential = critical_path_points / team_capacity_per_sprint
estimated_sprints = max(min_sprints_parallel, min_sprints_sequential)
estimated_sprints_with_buffer = estimated_sprints × (1 + buffer_percent/100)
```

**2. Work-Days Estimation:**

```
work_days_parallel = total_points / num_developers
work_days_sequential = critical_path_points  # Cannot parallelize
work_days_estimate = max(work_days_parallel, work_days_sequential)
work_days_with_buffer = work_days_estimate × (1 + buffer_percent/100)
```

**Why Take the Maximum:**

- Parallel constraint: Limited by total work ÷ team capacity
- Sequential constraint: Limited by critical path (no parallelization possible)
- Reality: Both constraints apply simultaneously
- Result: More accurate than either method alone

### Buffer Management

Configurable buffer accounts for overhead and uncertainty:

```
buffer_percent = 20.0  # Default 20% buffer

# Applied to both estimation methods
estimated_sprints_with_buffer = estimated_sprints_raw × 1.20
work_days_with_buffer = work_days_estimate × 1.20

# Converts to calendar time
estimated_weeks = estimated_sprints_with_buffer × sprint_weeks
work_weeks = work_days_with_buffer / 5  # 5 work days per week
```

**Buffer Rationale:**

- Sprint ceremonies and overhead
- Context switching and communication
- Unexpected blockers and dependencies
- Integration and testing time
- Code review and rework

### Cycle Detection and Recovery

The system detects circular dependencies and handles them gracefully:

```python
if not nx.is_directed_acyclic_graph(G):
    cycles = list(nx.simple_cycles(G))
    # Remove cycles by removing edges
    G = nx.DiGraph(
        [
            (u, v, d)
            for u, v, d in G.edges(data=True)
            if not any((u in c and v in c) for c in cycles)
        ]
    )
```

**Recovery Strategy:**

- Detect all cycles using NetworkX
- Report cycles to user for awareness
- Remove problematic edges to create valid DAG
- Continue with estimation (degraded but functional)

## 🛠️ Tools Reference

### epic_timeline_estimator.py

**Purpose**: Analyze Jira epics with critical path analysis and dual estimation
methods

**Key Parameters:**

- `epic_key`: Epic key (e.g., "PX-8350") - required positional argument
- `--developers`: Number of FTE developers (default: 3.25)
- `--points-per-sprint`: Story points per sprint per developer (default: 8)
- `--sprint-weeks`: Sprint length in weeks (default: 2)
- `--buffer`: Buffer percentage for overhead (default: 20)
- `--export-dag`: Export dependency graph as DOT/PNG
- `--json`: Output results as JSON

**Algorithm**: NetworkX DAG algorithms with dual estimation methods

**Outputs:**

- Sprint-based estimate with team velocity
- Work-days estimate with parallelization constraints
- Critical path analysis with issue breakdown
- Completion metrics and progress tracking
- Optional: Dependency graph visualization

### engineer_optimization.py

**Purpose**: Analyze optimal team size using diminishing returns analysis

**Key Parameters:**

- `epic_key`: Jira epic key (e.g., "PX-8350") - required positional argument
- `--max-engineers`: Maximum team size to analyze (default: 12)
- `--output`: Output file prefix (default: "engineer-optimization")
- `--story-points-field`: Jira custom field ID for story points (default:
  customfield_10115)
- `--export-dag`: Export dependency graph as DOT/PNG

**Algorithm**: Exhaustive search with efficiency analysis and critical path
calculation using NetworkX

**Outputs:**

- `output/<prefix>.png` - Dual-chart visualization (duration vs efficiency)
- `output/<prefix>.json` - Detailed optimization data with recommendations
- Console report with optimal team size and utilization metrics
- Optional: `<epic>_optimization_dag.png` - Dependency graph visualization

**Example:**

```bash
python3 engineer_optimization.py PX-8350 \
    --max-engineers 10 \
    --output team-analysis \
    --export-dag
```

## 📊 Data Sources

### Live Jira Data (Both Tools)

Both tools pull real-time data from Jira v3 API:

**Fetched Data:**

- Issue keys and summaries
- Story points (customfield_10115 - configurable via `--story-points-field`)
- Issue status (Done, In Progress, etc.)
- Issue links (blocks/blocked by relationships)
- Parent hierarchy (uses `parent = EPIC-KEY` JQL)

**Automatic Filtering:**

- Excludes completed issues from estimates (Done, Closed, Duplicate, Won't Fix)
- Tracks completion percentage
- Handles missing story points gracefully (defaults to 0)

**Pagination:**

- Automatically handles large epics (500+ issues)
- Uses `nextPageToken` for efficient pagination

**Environment Variables Required:**

```bash
export JIRA_BASE_URL="https://your-company.atlassian.net"
export JIRA_EMAIL="your-email@company.com"
export JIRA_TOKEN="your-api-token"
```

### Common Modules

The toolkit uses shared modules for consistency:

- `jira_client.py` - Jira v3 API client with pagination
- `issue_parser.py` - Issue parsing and dependency graph building
- `scheduler.py` - Task scheduling across engineers
- `dag_exporter.py` - Dependency graph visualization

To use the toolkit:

1. Create an epic in Jira
1. Add child issues to the epic (using parent hierarchy)
1. Add story points to each issue
1. Link issues with "blocks/blocked by" relationships for dependencies
1. Run the tools with your epic key

## ⚙️ Configuration

### Environment Variables

**Required for both tools:**

```bash
# Jira Configuration (v3 API)
export JIRA_BASE_URL="https://your-company.atlassian.net"
export JIRA_EMAIL="user@company.com"
export JIRA_TOKEN="your-api-token"
```

### Custom Story Points Field

Both tools support the `--story-points-field` parameter:

```bash
# Epic timeline estimator
python3 epic_timeline_estimator.py PX-8350 \
    --developers 3.25 \
    --story-points-field customfield_12345

# Engineer optimization
python3 engineer_optimization.py PX-8350 \
    --max-engineers 10 \
    --story-points-field customfield_12345
```

To find your story points field ID:

```bash
curl -u "$JIRA_EMAIL:$JIRA_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/field" | jq '.[] | select(.name | contains("Story Points"))'
```

## 🔍 Troubleshooting

### Common Issues

**1. "Missing required environment variables"**

```bash
# For both tools
export JIRA_BASE_URL="https://your-company.atlassian.net"
export JIRA_EMAIL="your-email@company.com"
export JIRA_TOKEN="your-api-token"

# Test connection
python3 -c "
from jira_client import JiraClient
jira = JiraClient()
print('✅ Jira connection successful')
"
```

**2. "No issues found for epic"**

```bash
# Verify epic exists and has child issues
curl -u "$JIRA_EMAIL:$JIRA_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/search?jql=parent=PX-8350"

# Check if issues are linked via parent hierarchy (not epic link)
# The tool uses: parent = EPIC-KEY
```

**3. "Circular dependencies detected"**

```bash
# The system will report cycles and continue with degraded accuracy
# Example output:
# ⚠️  Warning: Found 2 circular dependencies!
#    Cycle: PX-101 -> PX-102 -> PX-103 -> PX-101

# Fix in Jira by removing one blocking link from the cycle
```

**4. "GraphViz not installed (for --export-dag)"**

```bash
# Install graphviz library
pip install graphviz

# Install GraphViz system package
brew install graphviz  # macOS
# or
sudo apt install graphviz  # Ubuntu/Debian
```

**5. "Story points not showing (all 0 points)"**

```bash
# Find your custom field ID
curl -u "$JIRA_EMAIL:$JIRA_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/field" | jq '.[] | select(.name | contains("Story"))'

# Update line 111 in epic_timeline_estimator.py with your field ID
```

### Performance Optimization

For large epics (>100 issues):

```bash
# Use JSON output for faster processing
python3 epic_timeline_estimator.py PX-8350 --developers 6 --json > analysis.json

# Process programmatically
python3 -c "
import json
with open('analysis.json') as f:
    data = json.load(f)
    print(f'Duration: {data[\"estimated_weeks\"]:.1f} weeks')
    print(f'Critical path: {data[\"critical_path_points\"]} points')
"

# Pagination is automatic (handles 500+ issues)
# The JiraClient uses nextPageToken for large result sets
```

### Comparing Team Sizes

Quickly compare different team configurations:

```bash
# Create comparison script
for devs in 2 3 4 5 6; do
  echo "=== $devs Developers ==="
  python3 epic_timeline_estimator.py PX-8350 --developers $devs \
    | grep "Target Completion"
done
```

## 📈 Best Practices

### 1. When to Use Each Tool

**Use epic_timeline_estimator.py when:**

- Epic exists in Jira with child issues
- Need accurate estimates based on real data
- Want to track progress over time
- Critical path analysis is important
- Team has established velocity

**Use engineer_optimization.py when:**

- Planning new projects (not yet in Jira)
- Exploring different team size scenarios
- Need visual Gantt charts
- Doing theoretical "what-if" analysis

### 2. Story Point Guidelines

- **1 point**: \<= 1 Day of work
- **2 points**: 2 days of work
- **3 points**: 3 days of work
- **5 points**: 5 days of work
- **8+ points**: Consider splitting the task
- **Missing points**: Tool handles gracefully (excluded from estimates)

### 3. Dependency Management in Jira

- Use "blocks/blocked by" link types (automatically parsed)
- Keep dependency chains reasonable (\<10 levels)
- The tool detects and reports circular dependencies
- Review dependency graph with `--export-dag`

### 4. Buffer Configuration

- Default 20% buffer accounts for typical overhead
- Increase buffer (30-40%) for:
  - New teams or unfamiliar technology
  - High uncertainty or changing requirements
  - Integration-heavy projects
- Decrease buffer (10-15%) for:
  - Mature teams with stable velocity
  - Well-understood problem domains
  - Minimal external dependencies

### 5. Interpreting Results

**When estimates differ significantly:**

- Sprint-based > Work-days: Team velocity is lower than 1 point/day
- Work-days > Sprint-based: Critical path is the bottleneck
- Both similar: Good balance of parallelizable work

**Critical path insights:**

- High critical path ratio (>60% of total): Limited parallelization benefit
- Low critical path ratio (\<30%): Adding engineers helps significantly
- Focus optimization on critical path tasks first

## 🎯 Use Case Decision Tree

```
Have a Jira epic with issues?
│
├─ Need to find optimal team size?
│  └─ YES → Use engineer_optimization.py EPIC-KEY
│            • Analyzes 1-12 engineers (configurable)
│            • Shows diminishing returns
│            • Recommends optimal team size
│            • Outputs: chart + JSON + report
│
└─ Need detailed timeline estimate?
   └─ YES → Use epic_timeline_estimator.py EPIC-KEY
             • Dual estimation methods
             • Sprint-based + work-days
             • Buffer management
             • Progress tracking
             • Outputs: report + JSON + optional DAG

💡 Pro Tip: Run engineer_optimization.py first to find optimal
   team size, then use that number with epic_timeline_estimator.py
   for detailed timeline estimates.
```

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed
guidelines.

### Quick Start for Contributors

```bash
# Setup development environment
make setup

# Run tests
make test

# Format code
make format

# Run linter
make lint

# Type check
make type-check

# Run all pre-commit hooks
make pre-commit
```

### Development Commands

| Command           | Description                   |
| ----------------- | ----------------------------- |
| `make setup`      | Complete development setup    |
| `make test`       | Run test suite                |
| `make test-cov`   | Run tests with coverage       |
| `make format`     | Format code with black & ruff |
| `make lint`       | Run ruff linter               |
| `make type-check` | Run mypy type checker         |
| `make clean`      | Remove build artifacts        |

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines.

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- **Issues**: GitHub Issues
- **Documentation**: This README and ARCHITECTURE.md
- **Examples**: See `example.sh` for complete workflow demonstration

______________________________________________________________________

**Made with ❤️ for accurate project estimation**
