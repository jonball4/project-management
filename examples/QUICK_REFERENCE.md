# Quick Reference - Examples

## 🚀 Run Examples

### Simple Project (7 tasks, 17 points)
```bash
# Timeline with 2 engineers (optimal)
python3 effort_estimator.py --csv examples/simple-project.csv --engineers 2 --output simple-demo

# Find optimal team size
python3 engineer_optimization.py --csv examples/simple-project.csv --max-engineers 6 --output simple-opt
```

### Sample Project (20 tasks, 81 points)
```bash
# Timeline with 4 engineers
python3 effort_estimator.py --csv examples/sample-project.csv --engineers 4 --output sample-demo

# Find optimal team size (5 engineers recommended)
python3 engineer_optimization.py --csv examples/sample-project.csv --max-engineers 8 --output sample-opt
```

## 📊 Key Results

| Project | Optimal Team | Duration | Calendar Days | Efficiency |
|---------|--------------|----------|---------------|------------|
| Simple  | 2 engineers  | 15 days  | 22 days       | 56.7%      |
| Sample  | 5 engineers  | 23 days  | 34 days       | 49.6%      |

## 🎯 Critical Insights

### Simple Project
- **Linear dependencies** = No benefit from extra engineers
- **Critical path dominates** = 15 days minimum regardless of team size
- **Perfect for small teams** = 2 engineers optimal

### Sample Project  
- **Parallel work streams** = Benefits from larger teams
- **Complex dependencies** = Requires careful coordination
- **Diminishing returns** = 5+ engineers show minimal improvement

## 📁 Generated Files

```
examples/
├── simple-project.csv              # Input: 7-task project
├── simple-timeline.png            # Output: Gantt chart
├── simple-optimization.png        # Output: Team scaling analysis
├── sample-project.csv             # Input: 20-task e-commerce project  
├── sample-timeline.png            # Output: Complex project timeline
└── sample-optimization.png        # Output: Optimization analysis
```

## 🔧 Modify Examples

### Change Team Size
```bash
# Try different team sizes
python3 effort_estimator.py --csv examples/sample-project.csv --engineers 3 --output sample-3eng
python3 effort_estimator.py --csv examples/sample-project.csv --engineers 6 --output sample-6eng
```

### Edit Dependencies
```bash
# Edit CSV files to experiment with different dependency structures
# Then re-run analysis to see impact
```

### Custom Story Points
```bash
# Modify Points column in CSV files
# Observe how it affects optimal team size and duration
```

---
**💡 Tip**: Start with simple-project.csv to understand basics, then explore sample-project.csv for complex scenarios.
