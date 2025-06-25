#!/usr/bin/env python3
"""
JIRA Project Management Epic Maker - Creates JIRA tasks from CSV with dependency linking
"""

import argparse
import csv
import json
import logging
import os
import sys
from typing import Dict, List, Optional
import requests
from requests.auth import HTTPBasicAuth
import networkx as nx


class JiraClient:
    """JIRA API client for creating tickets and managing dependencies"""
    
    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(email, api_token)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
    def test_connection(self) -> bool:
        """Test JIRA connection and authentication"""
        try:
            response = self.session.get(f"{self.base_url}/rest/api/3/myself")
            response.raise_for_status()
            user_info = response.json()
            logging.info(f"Connected to JIRA as: {user_info.get('displayName', 'Unknown')}")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to JIRA: {e}")
            return False
    
    def get_project_info(self, project_key: str) -> Optional[Dict]:
        """Get project information"""
        try:
            response = self.session.get(f"{self.base_url}/rest/api/3/project/{project_key}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Failed to get project info for {project_key}: {e}")
            return None
    
    def validate_epic(self, epic_key: str) -> bool:
        """Validate that the epic exists and is accessible"""
        try:
            response = self.session.get(f"{self.base_url}/rest/api/3/issue/{epic_key}")
            response.raise_for_status()
            issue = response.json()
            if issue['fields']['issuetype']['name'].lower() != 'epic':
                logging.error(f"{epic_key} is not an Epic issue type")
                return False
            logging.info(f"Validated epic: {issue['fields']['summary']}")
            return True
        except Exception as e:
            logging.error(f"Failed to validate epic {epic_key}: {e}")
            return False
    
    def get_existing_tickets(self, epic_key: str) -> Dict[str, str]:
        """Get existing tickets in the epic, return dict of {task_name: ticket_key}"""
        try:
            # Query for all tickets in the epic
            jql = f"parent = {epic_key}"
            response = self.session.get(
                f"{self.base_url}/rest/api/3/search",
                params={
                    'jql': jql,
                    'fields': 'key,summary',
                    'maxResults': 1000
                }
            )
            response.raise_for_status()
            result = response.json()
            
            existing_tickets = {}
            for issue in result['issues']:
                task_name = issue['fields']['summary']
                ticket_key = issue['key']
                existing_tickets[task_name] = ticket_key
            
            logging.info(f"Found {len(existing_tickets)} existing tickets in epic {epic_key}")
            return existing_tickets
            
        except Exception as e:
            logging.error(f"Failed to get existing tickets from epic {epic_key}: {e}")
            return {}
    
    def discover_story_points_field(self, existing_ticket_key: str = None) -> Optional[str]:
        """Discover the correct Story Points field ID for this JIRA instance"""
        
        # Method 1: Check existing ticket with story points
        if existing_ticket_key:
            try:
                logging.info(f"Checking existing ticket {existing_ticket_key} for story points field...")
                response = self.session.get(f"{self.base_url}/rest/api/3/issue/{existing_ticket_key}")
                response.raise_for_status()
                issue = response.json()
                
                # Look through all fields for numeric values that could be story points
                for field_id, field_value in issue['fields'].items():
                    if field_id.startswith('customfield_') and isinstance(field_value, (int, float)) and field_value > 0:
                        logging.info(f"Found potential story points field: {field_id} = {field_value}")
                        return field_id
                        
            except Exception as e:
                logging.warning(f"Could not check existing ticket {existing_ticket_key}: {e}")
        
        # Method 2: Query all fields and find Story Points by name
        try:
            logging.info("Querying all JIRA fields to find Story Points...")
            response = self.session.get(f"{self.base_url}/rest/api/3/field")
            response.raise_for_status()
            fields = response.json()
            
            for field in fields:
                field_name = field.get('name', '').lower()
                field_id = field.get('id', '')
                
                if field_name == 'story points':
                    logging.info(f"Found Story Points field: {field['name']} -> {field_id}")
                    return field_id
                    
        except Exception as e:
            logging.warning(f"Could not query JIRA fields: {e}")
        
        logging.warning("Could not discover Story Points field ID")
        return None
    
    def create_task(self, project_key: str, epic_key: str, summary: str, 
                   description: str, story_points: Optional[int] = None, 
                   story_points_field: Optional[str] = None) -> Optional[str]:
        """Create a task under the specified epic"""
        
        # Build the issue data
        issue_data = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": description
                                }
                            ]
                        }
                    ]
                },
                "issuetype": {"name": "Task"},
                "parent": {"key": epic_key}
            }
        }
        
        # Add story points if provided and field ID is known
        if story_points is not None and story_points_field:
            issue_data["fields"][story_points_field] = story_points
            logging.debug(f"Adding story points: {story_points_field} = {story_points}")
        elif story_points is not None:
            logging.warning(f"Story points provided ({story_points}) but no field ID discovered - skipping story points")
        
        try:
            response = self.session.post(
                f"{self.base_url}/rest/api/3/issue",
                data=json.dumps(issue_data)
            )
            response.raise_for_status()
            result = response.json()
            ticket_key = result['key']
            logging.info(f"Created task: {ticket_key} - {summary}")
            return ticket_key
        except requests.exceptions.HTTPError as e:
            logging.error(f"Failed to create task '{summary}': {e}")
            logging.error(f"Request payload: {json.dumps(issue_data, indent=2)}")
            
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"JIRA response status: {e.response.status_code}")
                logging.error(f"JIRA response body: {e.response.text}")
            else:
                logging.error("No response object available in exception")
            
            return None
        except Exception as e:
            logging.error(f"Failed to create task '{summary}': {e}")
            return None
    
    def create_blocks_link(self, blocker_key: str, blocked_key: str) -> bool:
        """Create a 'blocks' relationship between two issues"""
        link_data = {
            "type": {"name": "Blocks"},
            "inwardIssue": {"key": blocked_key},
            "outwardIssue": {"key": blocker_key}
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/rest/api/3/issueLink",
                data=json.dumps(link_data)
            )
            response.raise_for_status()
            logging.info(f"Created link: {blocker_key} blocks {blocked_key}")
            return True
        except Exception as e:
            logging.error(f"Failed to create link {blocker_key} -> {blocked_key}: {e}")
            return False


class TaskDependencyGraph:
    """Manages task dependencies and creation order"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.tasks = {}
        
    def add_task(self, task_name: str, task_data: Dict):
        """Add a task to the dependency graph"""
        self.tasks[task_name] = task_data
        self.graph.add_node(task_name)
        
    def add_dependency(self, task_name: str, dependency_name: str):
        """Add a dependency relationship (dependency blocks task)"""
        if dependency_name not in self.tasks:
            raise ValueError(f"Dependency '{dependency_name}' not found for task '{task_name}'")
        
        # Add edge from dependency to task (dependency must be completed first)
        self.graph.add_edge(dependency_name, task_name)
        
    def get_creation_order(self) -> List[str]:
        """Get tasks in dependency order using topological sort"""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXError as e:
            if "not a directed acyclic graph" in str(e):
                # Find cycles for debugging
                cycles = list(nx.simple_cycles(self.graph))
                logging.error(f"Circular dependencies detected: {cycles}")
                raise ValueError(f"Circular dependencies found: {cycles}")
            raise
    
    def validate_dependencies(self) -> List[str]:
        """Validate all dependencies exist and return any errors"""
        errors = []
        for task_name, task_data in self.tasks.items():
            dependencies = task_data.get('dependencies', [])
            for dep in dependencies:
                if dep not in self.tasks:
                    errors.append(f"Task '{task_name}' has invalid dependency: '{dep}'")
        return errors


def parse_csv(csv_file: str) -> List[Dict]:
    """Parse the CSV file and return task data"""
    tasks = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip the TOTAL row
            if row['Task'].strip().upper() == 'TOTAL':
                continue
                
            # Skip empty rows
            if not row['Task'].strip():
                continue
            
            # Parse dependencies (handle multi-line)
            dependencies = []
            if row['Dependencies'].strip():
                # Split by newlines - each line is a separate dependency
                dep_lines = row['Dependencies'].strip().split('\n')
                for line in dep_lines:
                    line = line.strip()
                    if line:
                        dependencies.append(line)
            
            # Parse story points
            points = None
            if row['Points'].strip() and row['Points'].strip().upper() != 'TBD':
                try:
                    points = int(row['Points'].strip())
                except ValueError:
                    logging.warning(f"Invalid points value for task '{row['Task']}': {row['Points']}")
            
            task_data = {
                'name': row['Task'].strip(),
                'description': row['Description'].strip(),
                'dependencies': dependencies,
                'points': points
            }
            tasks.append(task_data)
    
    return tasks


def main():
    parser = argparse.ArgumentParser(description='Create JIRA tasks from CSV with dependency linking')
    parser.add_argument('--csv', required=True, help='Path to CSV file')
    parser.add_argument('--epic', required=True, help='Epic key (e.g., PX-7150)')
    parser.add_argument('--project', default='Prime Trade', help='JIRA project name')
    parser.add_argument('--dry-run', action='store_true', help='Validate without creating tickets')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Get JIRA credentials from environment variables
    jira_token = os.getenv('JIRA_TOKEN')
    jira_email = os.getenv('JIRA_EMAIL')
    jira_url = os.getenv('JIRA_URL')
    
    if not jira_token:
        logging.error("JIRA_TOKEN environment variable is required")
        sys.exit(1)
    
    if not jira_email:
        logging.error("JIRA_EMAIL environment variable is required")
        sys.exit(1)
    
    if not jira_url:
        logging.error("JIRA_URL environment variable is required")
        sys.exit(1)
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Parse CSV
        logging.info(f"Parsing CSV file: {args.csv}")
        tasks = parse_csv(args.csv)
        logging.info(f"Found {len(tasks)} tasks")
        
        # Build dependency graph
        logging.info("Building dependency graph...")
        graph = TaskDependencyGraph()
        
        # Add all tasks first
        for task in tasks:
            graph.add_task(task['name'], task)
        
        # Validate and fix dependencies first
        errors = graph.validate_dependencies()
        if errors:
            for error in errors:
                logging.error(error)
            sys.exit(1)
        
        # Add dependencies after validation/fixing
        for task in tasks:
            for dep in task['dependencies']:
                try:
                    graph.add_dependency(task['name'], dep)
                except ValueError as e:
                    logging.error(str(e))
                    sys.exit(1)
        
        # Get creation order
        creation_order = graph.get_creation_order()
        logging.info(f"Task creation order determined: {len(creation_order)} tasks")
        
        if args.dry_run:
            logging.info("DRY RUN - Would create tasks in this order:")
            for i, task_name in enumerate(creation_order, 1):
                task_data = graph.tasks[task_name]
                deps = ', '.join(task_data['dependencies']) if task_data['dependencies'] else 'None'
                logging.info(f"{i:2d}. {task_name} (deps: {deps}) [{task_data['points']} pts]")
            return
        
        # Connect to JIRA
        logging.info("Connecting to JIRA...")
        jira = JiraClient(jira_url, jira_email, jira_token)
        
        if not jira.test_connection():
            logging.error("Failed to connect to JIRA")
            sys.exit(1)
        
        # Get project key from project name
        # For now, assume "Prime Trade" maps to a specific project key
        # You may need to adjust this based on your actual project setup
        project_key = "PX"  # Assuming based on epic key PX-7150
        
        # Validate epic
        if not jira.validate_epic(args.epic):
            logging.error(f"Epic validation failed: {args.epic}")
            sys.exit(1)
        
        # Get existing tickets to avoid duplicates
        logging.info("Checking for existing tickets...")
        existing_tickets = jira.get_existing_tickets(args.epic)
        
        # Discover the correct Story Points field ID
        story_points_field = None
        if existing_tickets:
            # Try to discover from existing ticket
            first_ticket = list(existing_tickets.values())[0]
            story_points_field = jira.discover_story_points_field(first_ticket)
        
        if not story_points_field:
            # Try to discover from field list
            story_points_field = jira.discover_story_points_field()
        
        if story_points_field:
            logging.info(f"Using Story Points field: {story_points_field}")
        else:
            logging.warning("Could not discover Story Points field - tickets will be created without story points")
        
        # Create tasks in dependency order
        all_tickets = {}  # Will contain both existing and newly created tickets
        newly_created = 0
        skipped_existing = 0
        
        logging.info("Creating JIRA tasks...")
        
        for task_name in creation_order:
            task_data = graph.tasks[task_name]
            
            if task_name in existing_tickets:
                # Task already exists, skip creation
                ticket_key = existing_tickets[task_name]
                all_tickets[task_name] = ticket_key
                skipped_existing += 1
                logging.info(f"Skipping existing ticket: {ticket_key} - {task_name}")
            else:
                # Create new task
                ticket_key = jira.create_task(
                    project_key=project_key,
                    epic_key=args.epic,
                    summary=task_name,
                    description=task_data['description'],
                    story_points=task_data['points'],
                    story_points_field=story_points_field
                )
                
                if ticket_key:
                    all_tickets[task_name] = ticket_key
                    newly_created += 1
                else:
                    logging.error(f"Failed to create task: {task_name}")
                    sys.exit(1)
        
        # Create dependency links
        logging.info("Creating dependency links...")
        for task_name in creation_order:
            task_data = graph.tasks[task_name]
            task_key = all_tickets[task_name]
            
            for dep_name in task_data['dependencies']:
                dep_key = all_tickets[dep_name]
                jira.create_blocks_link(dep_key, task_key)
        
        # Summary
        logging.info(f"Task processing completed!")
        logging.info(f"  - Newly created tickets: {newly_created}")
        logging.info(f"  - Existing tickets skipped: {skipped_existing}")
        logging.info(f"  - Total tickets processed: {len(all_tickets)}")
        
        if newly_created > 0:
            logging.info("Newly created tickets:")
            for task_name, ticket_key in all_tickets.items():
                if task_name not in existing_tickets:
                    logging.info(f"  {ticket_key}: {task_name}")
        
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
