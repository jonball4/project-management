"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_jira_issues():
    """Sample Jira issues for testing."""
    return [
        {
            "key": "TEST-1",
            "fields": {
                "summary": "Setup environment",
                "status": {"name": "To Do"},
                "customfield_10115": 2,
                "issuelinks": [],
            },
        },
        {
            "key": "TEST-2",
            "fields": {
                "summary": "Build API",
                "status": {"name": "In Progress"},
                "customfield_10115": 5,
                "issuelinks": [
                    {
                        "type": {"name": "Blocks", "inward": "is blocked by", "outward": "blocks"},
                        "inwardIssue": {"key": "TEST-1"},
                    }
                ],
            },
        },
        {
            "key": "TEST-3",
            "fields": {
                "summary": "Create frontend",
                "status": {"name": "Done"},
                "customfield_10115": 8,
                "issuelinks": [
                    {
                        "type": {"name": "Blocks", "inward": "is blocked by", "outward": "blocks"},
                        "inwardIssue": {"key": "TEST-2"},
                    }
                ],
            },
        },
    ]
