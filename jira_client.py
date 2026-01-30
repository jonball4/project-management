#!/usr/bin/env python3
"""
Jira API Client - Common module for Jira v3 API interactions
"""

import os
from typing import Dict, List

import requests


class JiraClient:
    """Simple Jira API client using environment variables"""

    def __init__(self):
        self.base_url = os.getenv("JIRA_BASE_URL")
        self.email = os.getenv("JIRA_EMAIL")
        self.token = os.getenv("JIRA_TOKEN")

        if not all([self.base_url, self.email, self.token]):
            raise ValueError(
                "Missing required environment variables: " "JIRA_BASE_URL, JIRA_EMAIL, JIRA_TOKEN"
            )

        self.base_url = self.base_url.rstrip("/")
        self.auth = (self.email, self.token)

    def search_jql(self, jql: str, fields: List[str], max_results: int = 100) -> List[Dict]:
        """Search Jira using JQL with the v3 API"""
        url = f"{self.base_url}/rest/api/3/search/jql"

        all_issues: List[Dict] = []
        next_page_token: object = None

        while True:
            params: Dict[str, object] = {
                "jql": jql,
                "fields": ",".join(fields),
                "maxResults": max_results,
            }

            if next_page_token:
                params["nextPageToken"] = next_page_token

            response = requests.get(url, auth=self.auth, params=params, timeout=30)  # type: ignore[arg-type]
            response.raise_for_status()
            data = response.json()

            issues = data.get("issues", [])
            all_issues.extend(issues)

            # Check if there are more pages
            if data.get("isLast", True):
                break

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

        return all_issues
