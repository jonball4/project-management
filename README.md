# JIRA Project Management Toolkit

A comprehensive toolkit for JIRA project management that bridges CSV planning with JIRA execution, featuring advanced scheduling algorithms and resource optimization analysis.

## 🚀 Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd project-management
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run complete workflow
chmod +x example.sh
./example.sh
```

## 📋 Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
- [Mathematical Foundations](#mathematical-foundations)
- [Tools Reference](#tools-reference)
- [CSV Format](#csv-format)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This toolkit provides four integrated tools for comprehensive JIRA project management:

1. **JIRA Task Creator** - Creates JIRA tasks from CSV files under existing epics
2. **JIRA CSV Updater** - Syncs JIRA ticket data back to CSV
3. **Effort Estimator** - Generates realistic project timelines with business day scheduling
4. **Engineer Optimization** - Analyzes optimal team size using diminishing returns analysis

### Key Features

- ✅ **Business Days Scheduling** - Realistic timelines excluding weekends
- ✅ **Dependency Management** - Automatic task ordering and critical path analysis
- ✅ **Resource Optimization** - Data-driven team size recommendations
- ✅ **Google Sheets Integration** - Clean CSV export with clickable links
- ✅ **Visual Timeline Generation** - Professional Gantt charts with milestones

## 🔧 Installation

### Prerequisites

- Python 3.8+
- JIRA account with API access (optional)
- Mermaid CLI for diagram rendering (optional)

### Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install Mermaid CLI for diagram rendering
npm install -g @mermaid-js/mermaid-cli
```

### JIRA Configuration

```bash
# Set environment variables
export JIRA_EMAIL="your-email@company.com"
export JIRA_TOKEN="your-jira-api-token"
export JIRA_URL="https://your-company.atlassian.net"
```

## 📚 Basic Usage

### 1. Simple Timeline Generation

Generate a basic project timeline from your CSV:

```bash
python3 effort_estimator.py \
    --csv "your-tasks.csv" \
    --engineers 4 \
    --output "project-timeline"
```

**Output:**
- `project-timeline.png` - Visual Gantt chart
- `project-timeline.mmd` - Mermaid source file
- Console report with project statistics

### 2. Find Optimal Team Size

Analyze the best number of engineers for your project:

```bash
python3 engineer_optimization.py \
    --csv "your-tasks.csv" \
    --max-engineers 10 \
    --output "team-optimization"
```

**Output:**
- `team-optimization.png` - Scaling analysis charts
- `team-optimization.json` - Detailed optimization data
- Console report with recommendations

### 3. Create JIRA Tasks

Create JIRA tasks from your CSV under an existing epic:

```bash
python3 jira_epic_maker.py \
    --csv "your-tasks.csv" \
    --epic "PROJ-123"
```

### 4. Sync Back to CSV

Update your CSV with actual JIRA ticket numbers:

```bash
python3 jira_csv_updater.py \
    --csv "your-tasks.csv" \
    --epic "PROJ-123" \
    --output "tasks-with-tickets.csv"
```

## 🎓 Advanced Usage

### Multi-Stage Project Analysis

```bash
# Stage 1: Initial planning
python3 effort_estimator.py --csv tasks.csv --engineers 3 --output stage1
python3 effort_estimator.py --csv tasks.csv --engineers 5 --output stage2
python3 effort_estimator.py --csv tasks.csv --engineers 8 --output stage3

# Stage 2: Optimization analysis
python3 engineer_optimization.py --csv tasks.csv --max-engineers 12 --output optimization

# Stage 3: JIRA integration
python3 jira_epic_maker.py --csv tasks.csv --epic "PA-100"
python3 jira_csv_updater.py --csv tasks.csv --epic "PA-100" --output final-tasks.csv

# Stage 4: Final timeline with JIRA data
python3 effort_estimator.py --csv final-tasks.csv --engineers 6 --output final-timeline
```

### Custom Story Point Mapping

The system uses a standard Fibonacci-based mapping:

```python
# Default mapping in effort_estimator.py
STORY_POINTS_TO_DAYS = {
    1: 1,    # <= 1 Day of work
    2: 2,    # 2 days of work
    3: 3,    # 3 days of work
    5: 5,    # 5 days of work
    8: 8,    # Consider splitting the task
    13: 13   # Epic-level task (definitely split)
}
```

### Advanced CSV Features

Your CSV can include complex dependencies:

```csv
Task,Description,Dependencies,Points
Setup Database,Create initial schema,,2
Create API,Build REST endpoints,Setup Database,5
Frontend UI,Build user interface,Create API,8
Integration Tests,End-to-end testing,"Create API,Frontend UI",3
```

## 🧮 Mathematical Foundations

### Business Days Calculation

The system converts calendar days to business days using:

```
Business Days = ⌊(Calendar Days × 5) / 7⌋ + Adjustment
```

Where the adjustment accounts for partial weeks and ensures weekends are excluded.

**Implementation:**
```python
def add_business_days(start_date: datetime, business_days: int) -> datetime:
    current_date = start_date
    days_added = 0
    
    while days_added < business_days:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
            days_added += 1
    
    return current_date
```

### Critical Path Analysis

The critical path is calculated using the **Longest Path Algorithm** on a Directed Acyclic Graph (DAG):

```
Critical Path Length = max(path_length(start_node, end_node))
                      for all start_nodes, end_nodes
```

**Mathematical Properties:**
- **Lower Bound**: No project can complete faster than the critical path
- **Dependency Constraint**: `start_time(task) ≥ max(end_time(dependency)) for all dependencies`
- **Resource Independence**: Critical path assumes unlimited resources

### Resource Optimization Model

The optimization analysis uses **Diminishing Returns Theory**:

```
Efficiency(n) = Total_Work / (n × Project_Duration(n))

Marginal_Benefit(n) = Duration(n-1) - Duration(n)
Marginal_Cost(n) = Cost_per_Engineer

Optimal_n = argmax(Marginal_Benefit(n) / Marginal_Cost(n))
```

**Key Equations:**

1. **Team Efficiency**: `E(n) = W / (n × D(n))`
   - W = Total work (story points)
   - n = Number of engineers  
   - D(n) = Project duration with n engineers

2. **Utilization Rate**: `U(n) = Σ(engineer_workload) / (n × max_workload)`

3. **Diminishing Returns Threshold**: When `(D(n-1) - D(n)) / D(n-1) < 0.05` (5% improvement)

### Scheduling Algorithm

The system uses a **Priority-Based List Scheduling** algorithm:

```
1. Topological Sort: Order tasks by dependencies
2. For each task in topological order:
   a. Calculate earliest start time based on dependencies
   b. Find engineer with earliest availability ≥ earliest start time
   c. Assign task to that engineer
   d. Update engineer's availability
```

**Time Complexity**: O(V + E + V log V) where V = tasks, E = dependencies

**Space Complexity**: O(V + E) for the dependency graph

### Statistical Analysis

The optimization tool provides several statistical measures:

1. **Mean Utilization**: `μ = (1/n) Σ utilization_i`
2. **Standard Deviation**: `σ = √[(1/n) Σ(utilization_i - μ)²]`
3. **Efficiency Variance**: Measures workload distribution fairness
4. **Confidence Intervals**: 95% confidence bounds on duration estimates

## 🛠️ Tools Reference

### effort_estimator.py

**Purpose**: Generate project timelines with business day scheduling

**Key Parameters:**
- `--csv`: Input CSV file path
- `--engineers`: Number of engineers (default: 4)
- `--output`: Output file prefix
- `--format`: Output format (gantt, png, both)

**Algorithm**: Priority-based list scheduling with topological ordering

**Outputs:**
- Gantt chart visualization
- Project statistics report
- Critical path analysis

### engineer_optimization.py

**Purpose**: Analyze optimal team size using diminishing returns

**Key Parameters:**
- `--csv`: Input CSV file path
- `--max-engineers`: Maximum team size to analyze (default: 12)
- `--output`: Output file prefix

**Algorithm**: Exhaustive search with efficiency analysis

**Outputs:**
- Dual-chart visualization (duration vs efficiency)
- Optimization recommendations
- JSON data export

### jira_epic_maker.py

**Purpose**: Create JIRA tasks from CSV under an existing epic

**Key Parameters:**
- `--csv`: Input CSV file path
- `--epic`: Epic key (e.g., "PROJ-123")
- `--project`: JIRA project name (default: "Prime Trade")
- `--dry-run`: Validate without creating tickets
- `--verbose`: Enable verbose logging

**Features:**
- Automatic field discovery
- Dependency relationship creation
- Duplicate handling

### jira_csv_updater.py

**Purpose**: Sync JIRA ticket data back to CSV

**Key Parameters:**
- `--csv`: Original CSV file path
- `--epic`: Epic key (e.g., "PROJ-123")
- `--output`: Updated CSV file path

**Features:**
- Google Sheets compatible links
- Dependency ticket extraction
- Bidirectional sync

## 📊 CSV Format

### Required Columns

```csv
Task,Description,Dependencies,Points
```

### Column Specifications

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `Task` | String | Unique task name | "Setup Database" |
| `Description` | String | Detailed task description | "Create initial schema with tables" |
| `Dependencies` | String | Comma-separated task names | "Task A,Task B" |
| `Points` | Integer/String | Story points or "TBD" | "5" or "TBD" |

### Optional Enhancements

The CSV updater adds these columns:

| Column | Description |
|--------|-------------|
| `Ticket(s)` | JIRA ticket hyperlinks |
| `Dependency Tickets` | Plain text ticket keys |

### Example CSV

```csv
Task,Description,Dependencies,Points
Database Setup,Create PostgreSQL schema,,2
API Development,Build REST endpoints,Database Setup,5
Frontend UI,React component development,API Development,8
Integration Tests,End-to-end testing,"API Development,Frontend UI",3
Deployment,Production deployment,Integration Tests,2
```

## ⚙️ Configuration

### Environment Variables

```bash
# JIRA Configuration
export JIRA_EMAIL="user@company.com"
export JIRA_TOKEN="your-api-token"
export JIRA_URL="https://company.atlassian.net"

# Optional: Customize story point mapping
export STORY_POINT_MULTIPLIER="1.0"  # Adjust estimation factor
```

### Advanced Configuration

Create a `config.json` file:

```json
{
  "story_points_mapping": {
    "1": 1,
    "2": 2,
    "3": 3,
    "5": 5,
    "8": 8
  },
  "business_hours": {
    "start": "09:00",
    "end": "17:00",
    "timezone": "UTC"
  },
  "optimization": {
    "max_engineers": 15,
    "efficiency_threshold": 0.05,
    "cost_per_engineer": 1000
  }
}
```

## 🔍 Troubleshooting

### Common Issues

**1. "No tasks with valid story points found"**
```bash
# Check your CSV format
head -5 your-tasks.csv

# Ensure Points column has numeric values or "TBD"
# Valid: 1, 2, 3, 5, 8, TBD
# Invalid: "2 days", "medium", ""
```

**2. "Circular dependencies detected"**
```bash
# The system will report the circular dependency
# Example: Task A → Task B → Task C → Task A
# Fix by removing one dependency link
```

**3. "JIRA authentication failed"**
```bash
# Verify credentials
echo $JIRA_EMAIL
echo $JIRA_TOKEN

# Test connection
curl -u "$JIRA_EMAIL:$JIRA_TOKEN" \
  "$JIRA_URL/rest/api/3/myself"
```

**4. "Mermaid diagram not rendering"**
```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Or use online editor with .mmd files
# https://mermaid.live/
```

### Performance Optimization

For large projects (>100 tasks):

```bash
# Use JSON output for faster processing
python3 engineer_optimization.py --csv large-project.csv --output analysis
# Process analysis.json programmatically

# Limit engineer analysis range
python3 engineer_optimization.py --max-engineers 8  # Instead of default 12

# Use verbose mode for progress tracking
python3 effort_estimator.py --csv large-project.csv --verbose
```

### Debug Mode

Enable detailed logging:

```bash
# Set debug environment
export DEBUG=1

# Run with maximum verbosity
python3 effort_estimator.py --csv tasks.csv --verbose --engineers 4
```

## 📈 Best Practices

### 1. Story Point Guidelines

- **1 point**: <= 1 Day of work
- **2 points**: 2 days of work
- **3 points**: 3 days of work
- **5 points**: 5 days of work
- **8+ points**: Consider splitting the task

### 2. Dependency Management

- Keep dependencies simple and direct
- Avoid deep dependency chains (>5 levels)
- Use task splitting for complex dependencies
- Validate dependency logic before JIRA creation

### 3. Team Size Optimization

- Start with the optimization tool recommendation
- Consider team communication overhead (Brooks' Law)
- Factor in onboarding time for new team members
- Account for domain expertise requirements

### 4. Timeline Accuracy

- Use business days for realistic planning
- Add buffer time for integration and testing
- Consider holidays and team availability
- Update estimates based on actual progress

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit a pull request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt
# Uncomment dev dependencies in requirements.txt

# Run tests
python -m pytest tests/

# Format code
black *.py

# Type checking
mypy *.py
```

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- **Issues**: GitHub Issues
- **Documentation**: This README
- **Examples**: See `example.sh` and sample CSV files

---

**Made with ❤️ for better project management**
