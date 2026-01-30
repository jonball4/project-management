#!/bin/bash

# Project Timeline Estimation - Demonstration Script
# Demonstrates epic timeline estimation and team optimization analysis

set -e  # Exit on any error

echo "🚀 Project Timeline Estimation - Demo"
echo "====================================="
echo

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check for required environment variables
if [ -z "$JIRA_BASE_URL" ] || [ -z "$JIRA_EMAIL" ] || [ -z "$JIRA_TOKEN" ]; then
    echo "⚠️  WARNING: Jira credentials not set!"
    echo "   Both tools require these environment variables:"
    echo
    echo "   export JIRA_BASE_URL='https://your-company.atlassian.net'"
    echo "   export JIRA_EMAIL='your-email@company.com'"
    echo "   export JIRA_TOKEN='your-jira-api-token'"
    echo
    echo "   Cannot proceed without Jira credentials."
    echo
    exit 1
fi

# Example epic key - replace with your own
EPIC_KEY="PX-8350"

echo "=============================================="
echo "STEP 1: Find Optimal Team Size"
echo "=============================================="
echo
echo "📈 Running Engineer Optimization Analysis"
echo "-----------------------------------------"
echo "  Analyzing epic: $EPIC_KEY"
echo "  Testing team sizes: 1-10 engineers"
echo

python3 engineer_optimization.py "$EPIC_KEY" \
    --max-engineers 10 \
    --output "team-optimization" \
    --export-dag

echo
echo "  ✅ Generated: output/team-optimization.png"
echo "  ✅ Generated: output/team-optimization.json"
echo "  ✅ Generated: ${EPIC_KEY,,}_optimization_dag.dot"
if command -v dot &> /dev/null; then
    echo "  ✅ Generated: ${EPIC_KEY,,}_optimization_dag.png"
fi
echo
echo "  💡 Review output/team-optimization.png to see:"
echo "     • Optimal team size (marked with ⭐)"
echo "     • Critical path limit (red dashed line)"
echo "     • Diminishing returns curve"
echo "     • Team efficiency and utilization"

# Extract optimal team size from JSON
OPTIMAL_TEAM=$(python3 -c "import json; data=json.load(open('output/team-optimization.json')); print(data['analysis']['optimal_engineers'])")

echo
echo "=============================================="
echo "STEP 2: Detailed Timeline Estimation"
echo "=============================================="
echo
echo "📊 Running Epic Timeline Estimator"
echo "----------------------------------"
echo "  Using optimal team size: $OPTIMAL_TEAM engineers"
echo

python3 epic_timeline_estimator.py "$EPIC_KEY" \
    --developers "$OPTIMAL_TEAM" \
    --points-per-sprint 8 \
    --sprint-weeks 2 \
    --buffer 20 \
    --export-dag

echo
echo "  ✅ Generated: epic_dag.dot"
if command -v dot &> /dev/null; then
    echo "  ✅ Generated: epic_dag.png"
fi

echo
echo "=============================================="
echo "STEP 3: Compare Different Team Sizes"
echo "=============================================="
echo
echo "📊 Testing various team configurations..."
echo

for devs in 2 4 6 8 10; do
    result=$(python3 epic_timeline_estimator.py "$EPIC_KEY" \
        --developers $devs \
        --points-per-sprint 8 \
        --json 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"{data['estimated_weeks']:.1f} weeks ({data['estimated_sprints_with_buffer']:.1f} sprints)\")" 2>/dev/null || echo "error")

    marker=""
    if [ "$devs" -eq "$OPTIMAL_TEAM" ]; then
        marker=" ⭐ OPTIMAL"
    fi

    echo "  $devs developers: $result$marker"
done

echo
echo "=============================================="
echo "STEP 4: Export for Reporting"
echo "=============================================="
echo

python3 epic_timeline_estimator.py "$EPIC_KEY" \
    --developers "$OPTIMAL_TEAM" \
    --points-per-sprint 8 \
    --json > epic-timeline-report.json 2>/dev/null

echo "  ✅ Generated: epic-timeline-report.json"
echo "  💡 Use this JSON for:"
echo "     • Custom dashboards"
echo "     • Automated reporting"
echo "     • Integration with other tools"

echo
echo "✅ Demo Complete!"
echo "================"
echo

echo "📁 Generated Files:"
echo "  📈 output/team-optimization.png - Team size analysis"
echo "  📋 output/team-optimization.json - Optimization data"
echo "  📊 epic-timeline-report.json - Timeline estimate"
echo "  📊 ${EPIC_KEY,,}_optimization_dag.dot - Optimization dependency graph"
echo "  📊 epic_dag.dot - Timeline dependency graph"
if command -v dot &> /dev/null; then
    echo "  📊 ${EPIC_KEY,,}_optimization_dag.png - Optimization visualization"
    echo "  📊 epic_dag.png - Timeline visualization"
else
    echo "  ⚠️  Install GraphViz for PNG visualization: brew install graphviz"
fi

echo
echo "🎯 Key Findings:"
echo "  • Optimal team size: $OPTIMAL_TEAM engineers"
echo "  • Review charts for detailed analysis"
echo "  • Critical path shows minimum possible duration"
echo "  • Adding more engineers beyond optimal shows diminishing returns"
echo
echo "📖 For detailed usage, see README.md"
