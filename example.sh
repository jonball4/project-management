#!/bin/bash

# JIRA Project Management - Complete Workflow Example
# This script demonstrates the full workflow from CSV to JIRA to optimization analysis

set -e  # Exit on any error

echo "🚀 JIRA Project Management - Complete Workflow Example"
echo "======================================================"
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
if [ -z "$JIRA_EMAIL" ] || [ -z "$JIRA_TOKEN" ] || [ -z "$JIRA_URL" ]; then
    echo "⚠️  WARNING: JIRA credentials not set!"
    echo "   Please set JIRA_EMAIL, JIRA_TOKEN, and JIRA_URL environment variables"
    echo "   Example:"
    echo "   export JIRA_EMAIL='your-email@company.com'"
    echo "   export JIRA_TOKEN='your-jira-api-token'"
    echo "   export JIRA_URL='https://your-company.atlassian.net'"
    echo
    echo "   You can still run the analysis tools without JIRA credentials."
    echo
fi

# Example CSV file (using the provided one)
CSV_FILE="Just-in-time Settlement Work Items - Sheet1.csv"
EPIC_KEY="PX-7150"  # Replace with your epic key

echo "📊 Step 1: Basic Effort Estimation (4 Engineers)"
echo "------------------------------------------------"
python3 effort_estimator.py \
    --csv "$CSV_FILE" \
    --engineers 4 \
    --output "basic-timeline" \
    --verbose

echo
echo "📈 Step 2: Engineer Optimization Analysis"
echo "----------------------------------------"
python3 engineer_optimization.py \
    --csv "$CSV_FILE" \
    --max-engineers 10 \
    --output "optimization-analysis" \
    --verbose

echo
if [ -n "$JIRA_EMAIL" ] && [ -n "$JIRA_TOKEN" ] && [ -n "$JIRA_URL" ]; then
    echo "🎫 Step 3: Create JIRA Tasks under Epic"
    echo "--------------------------------------"
    python3 jira_epic_maker.py \
        --csv "$CSV_FILE" \
        --epic "$EPIC_KEY" \
        --verbose

    echo
    echo "🔄 Step 4: Update CSV with JIRA Ticket Links"
    echo "--------------------------------------------"
    python3 jira_csv_updater.py \
        --csv "$CSV_FILE" \
        --epic "$EPIC_KEY" \
        --output "tasks-with-jira-links.csv" \
        --verbose

    echo
    echo "📊 Step 5: Generate Final Timeline with JIRA Data"
    echo "------------------------------------------------"
    python3 effort_estimator.py \
        --csv "tasks-with-jira-links.csv" \
        --engineers 4 \
        --output "final-jira-timeline" \
        --verbose
else
    echo "⏭️  Skipping JIRA steps (credentials not provided)"
fi

echo
echo "✅ Workflow Complete!"
echo "===================="
echo
echo "📁 Generated Files (in output/ folder):"
echo "  📊 output/basic-timeline.png - Initial timeline visualization"
echo "  📈 output/optimization-analysis.png - Engineer scaling analysis"
echo "  📋 output/optimization-analysis.json - Detailed optimization data"

if [ -n "$JIRA_EMAIL" ] && [ -n "$JIRA_TOKEN" ] && [ -n "$JIRA_URL" ]; then
    echo "  🎫 output/tasks-with-jira-links.csv - CSV updated with JIRA tickets"
    echo "  📊 output/final-jira-timeline.png - Timeline with actual JIRA data"
fi

echo
echo "🔍 Key Insights:"
echo "  • Check output/optimization-analysis.png for optimal team size"
echo "  • Review timeline files in output/ folder for project scheduling"
echo "  • Use CSV files for project management in Google Sheets"
echo
echo "📖 For detailed usage, see README.md"
