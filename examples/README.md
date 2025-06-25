# Examples

This folder contains sample inputs and outputs demonstrating the JIRA Epic Maker toolkit capabilities.

## 📁 Sample Projects

### 1. Simple Project (`simple-project.csv`)
A basic 7-task project demonstrating fundamental workflow:
- **Tasks**: 7 tasks with clear dependencies
- **Story Points**: 17 total points
- **Complexity**: Linear dependency chain
- **Use Case**: Small feature development or proof-of-concept

**Project Structure:**
```
Setup Environment → Build API → Create Frontend → Add Authentication → Testing → Deployment
                 ↘ Design Database (parallel)
```

### 2. Sample Project (`sample-project.csv`)
A comprehensive 20-task e-commerce project:
- **Tasks**: 20 tasks with complex dependencies
- **Story Points**: 81 total points  
- **Complexity**: Multiple parallel tracks with integration points
- **Use Case**: Full-scale application development

**Project Structure:**
```
Project Setup → API Framework
Database Design → Database Implementation → User Auth → User Management → Admin Dashboard
                                        ↘ Product Catalog → Shopping Cart → Payment → Order Management
                                                         ↘ Mobile API
Performance Testing → Security Audit → Documentation → Deployment → Integration Testing → UAT → Launch
```

## 📊 Generated Outputs

### Timeline Visualizations

| File | Description | Project | Engineers |
|------|-------------|---------|-----------|
| `simple-timeline.png` | Basic project Gantt chart | Simple | 2 |
| `sample-timeline.png` | Complex project timeline | Sample | 4 |

### Optimization Analysis

| File | Description | Insights |
|------|-------------|----------|
| `simple-optimization.png` | Team scaling analysis for simple project | Optimal: 2 engineers, 15 days |
| `sample-optimization.png` | Team scaling analysis for sample project | Optimal: 5 engineers, 23 days |

### Data Files

| File | Type | Description |
|------|------|-------------|
| `simple-timeline.mmd` | Mermaid | Source for simple project timeline |
| `sample-timeline.mmd` | Mermaid | Source for sample project timeline |
| `simple-optimization.json` | JSON | Detailed optimization data for simple project |
| `sample-optimization.json` | JSON | Detailed optimization data for sample project |

## 🎯 Key Insights from Examples

### Simple Project Analysis
- **Optimal Team Size**: 2 engineers
- **Project Duration**: 15 business days (22 calendar days)
- **Critical Path**: All tasks are on critical path (linear dependency)
- **Team Efficiency**: 56.7% with optimal team
- **Key Finding**: Adding more than 2 engineers provides no benefit due to dependencies

### Sample Project Analysis
- **Optimal Team Size**: 5 engineers  
- **Project Duration**: 23 business days (34 calendar days)
- **Critical Path**: 39 days (Database → User Management → Admin Dashboard → Testing chain)
- **Team Efficiency**: 49.6% with optimal team
- **Key Finding**: Complex projects benefit from larger teams but hit diminishing returns quickly

## 🚀 How to Use These Examples

### 1. Basic Timeline Generation
```bash
# Simple project with 2 engineers
python3 effort_estimator.py --csv examples/simple-project.csv --engineers 2 --output my-simple-timeline

# Sample project with 4 engineers  
python3 effort_estimator.py --csv examples/sample-project.csv --engineers 4 --output my-sample-timeline
```

### 2. Optimization Analysis
```bash
# Find optimal team size for simple project
python3 engineer_optimization.py --csv examples/simple-project.csv --max-engineers 6 --output simple-analysis

# Find optimal team size for sample project
python3 engineer_optimization.py --csv examples/sample-project.csv --max-engineers 8 --output sample-analysis
```

### 3. Compare Different Team Sizes
```bash
# Generate timelines with different team sizes
python3 effort_estimator.py --csv examples/sample-project.csv --engineers 3 --output sample-3eng
python3 effort_estimator.py --csv examples/sample-project.csv --engineers 5 --output sample-5eng
python3 effort_estimator.py --csv examples/sample-project.csv --engineers 7 --output sample-7eng
```

## 📈 Understanding the Outputs

### Timeline Charts (`*.png`)
- **Gantt Chart**: Shows task scheduling across engineers
- **Business Days**: Only Monday-Friday scheduling
- **Dependencies**: Tasks automatically ordered by dependencies
- **Milestones**: Project completion clearly marked
- **Color Coding**: Each engineer has a distinct color

### Optimization Charts (`*-optimization.png`)
- **Top Chart**: Project duration vs number of engineers
- **Bottom Chart**: Team efficiency and utilization metrics
- **Critical Path Line**: Theoretical minimum duration
- **Optimal Point**: Highlighted with red circle
- **Diminishing Returns**: Visible curve flattening

### JSON Data (`*.json`)
```json
{
  "results": [
    {
      "engineers": 1,
      "duration_days": 17,
      "calendar_days": 24,
      "efficiency": 1.0,
      "avg_utilization": 100.0
    }
  ],
  "analysis": {
    "optimal_engineers": 2,
    "critical_path_duration": 15
  }
}
```

## 🎓 Learning Exercises

### Exercise 1: Modify Dependencies
1. Edit `simple-project.csv` to add parallel tasks
2. Run the analysis and observe how it affects the timeline
3. Compare critical path changes

### Exercise 2: Story Point Impact
1. Change story points in `sample-project.csv`
2. Analyze how it affects optimal team size
3. Observe efficiency changes

### Exercise 3: Custom Project
1. Create your own CSV based on a real project
2. Run both timeline and optimization analysis
3. Compare results with your actual project experience

## 🔍 Troubleshooting Examples

### Common Issues

**1. Dependency Errors**
```bash
# Error: Task 'X' has invalid dependency: 'Y'
# Solution: Ensure dependency names match task names exactly
```

**2. No Optimization Benefit**
```bash
# When critical path dominates (like simple-project.csv)
# Adding engineers beyond critical path requirements shows no benefit
```

**3. Low Team Efficiency**
```bash
# High efficiency (>80%): Good task distribution
# Medium efficiency (50-80%): Acceptable with some idle time  
# Low efficiency (<50%): Consider task restructuring
```

## 📚 Next Steps

1. **Try Your Own Data**: Replace the sample CSVs with your project data
2. **Experiment with Parameters**: Try different engineer counts and see the impact
3. **Integrate with JIRA**: Use the JIRA tools with these examples (requires JIRA credentials)
4. **Customize Analysis**: Modify the optimization parameters for your specific needs

## 🤝 Contributing Examples

To add new example projects:

1. Create a new CSV file following the format
2. Generate outputs using the toolkit
3. Document key insights and use cases
4. Submit a pull request with your example

---

**These examples demonstrate real-world project management scenarios and help you understand the toolkit's capabilities before applying it to your own projects.**
