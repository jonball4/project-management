#!/usr/bin/env python3
"""
JIRA Project Management CSV Updater - Reads tickets from JIRA epic and updates CSV with ticket numbers and dependencies
"""

import argparse
import csv
import logging
import os
import sys
from typing import Dict, List
import requests
from requests.auth import HTTPBasicAuth


class JiraClient:
    """JIRA API client for reading tickets and dependencies"""
    
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
    
    def get_epic_tickets(self, epic_key: str) -> List[Dict]:
        """Get all tickets in the specified epic"""
        try:
            # Query for all tickets in the epic
            jql = f"parent = {epic_key}"
            response = self.session.get(
                f"{self.base_url}/rest/api/3/search",
                params={
                    'jql': jql,
                    'fields': 'key,summary,description,customfield_10016,issuelinks',
                    'expand': 'issuelinks',
                    'maxResults': 1000
                }
            )
            response.raise_for_status()
            result = response.json()
            
            tickets = []
            for issue in result['issues']:
                # Get story points (customfield_10016 is standard story points field)
                story_points = issue['fields'].get('customfield_10016')
                
                ticket_data = {
                    'key': issue['key'],
                    'summary': issue['fields']['summary'],
                    'description': issue['fields'].get('description', ''),
                    'story_points': story_points,
                    'issue_links': issue['fields'].get('issuelinks', [])
                }
                tickets.append(ticket_data)
            
            logging.info(f"Found {len(tickets)} tickets in epic {epic_key}")
            return tickets
            
        except Exception as e:
            logging.error(f"Failed to get tickets from epic {epic_key}: {e}")
            return []
    
    def get_ticket_dependencies(self, ticket: Dict, all_tickets: List[Dict]) -> List[str]:
        """Get dependency tickets that block this ticket"""
        dependencies = []
        ticket_keys_to_summaries = {t['key']: t['summary'] for t in all_tickets}
        
        for link in ticket.get('issue_links', []):
            link_type = link.get('type', {}).get('name', '')
            
            # Check if this ticket is blocked by another ticket
            if link_type.lower() == 'blocks':
                if 'inwardIssue' in link:
                    # This ticket is blocked by the inward issue
                    blocker_key = link['inwardIssue']['key']
                    blocker_summary = link['inwardIssue']['fields']['summary']
                    
                    # Only include dependencies that are within our epic
                    if blocker_key in ticket_keys_to_summaries:
                        dependencies.append(f"{blocker_summary} ({blocker_key})")
        
        return dependencies


def parse_csv(csv_file: str) -> List[Dict]:
    """Parse the original CSV file"""
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
            
            task_data = {
                'name': row['Task'].strip(),
                'description': row['Description'].strip(),
                'dependencies': row['Dependencies'].strip(),
                'points': row['Points'].strip()
            }
            tasks.append(task_data)
    
    return tasks


def match_tickets_to_tasks(tasks: List[Dict], tickets: List[Dict]) -> tuple:
    """Match JIRA tickets to CSV tasks using exact matching"""
    matched_tasks = []
    unmatched_tickets = []
    
    # Create lookup for exact matching
    task_by_name = {task['name']: task for task in tasks}
    ticket_by_summary = {ticket['summary']: ticket for ticket in tickets}
    
    # Match tasks to tickets
    for task in tasks:
        task_name = task['name']
        if task_name in ticket_by_summary:
            ticket = ticket_by_summary[task_name]
            matched_task = task.copy()
            matched_task['matched_ticket'] = ticket
            matched_tasks.append(matched_task)
            logging.info(f"Matched task '{task_name}' to ticket {ticket['key']}")
        else:
            # Task has no matching ticket
            matched_task = task.copy()
            matched_task['matched_ticket'] = None
            matched_tasks.append(matched_task)
            logging.warning(f"No ticket found for task: '{task_name}'")
    
    # Find unmatched tickets
    for ticket in tickets:
        if ticket['summary'] not in task_by_name:
            unmatched_tickets.append(ticket)
            logging.info(f"Unmatched ticket {ticket['key']}: '{ticket['summary']}'")
    
    return matched_tasks, unmatched_tickets


def write_updated_csv(matched_tasks: List[Dict], unmatched_tickets: List[Dict], 
                     all_tickets: List[Dict], jira_client: JiraClient, output_file: str):
    """Write the updated CSV with ticket information"""
    
    fieldnames = ['Task', 'Ticket(s)', 'Description', 'Dependencies', 'Points', 'Dependency Tickets']
    
    def create_jira_link(ticket_key: str, base_url: str) -> str:
        """Create a Google Sheets compatible hyperlink for JIRA ticket"""
        jira_url = f"{base_url}/browse/{ticket_key}"
        # Google Sheets HYPERLINK formula format
        return f'=HYPERLINK("{jira_url}","{ticket_key}")'
    
    def create_dependency_links(dependencies: List[str], base_url: str) -> str:
        """Create dependency links - just ticket keys for Google Sheets compatibility"""
        if not dependencies:
            return ''
        
        ticket_keys = []
        for dep in dependencies:
            # Extract ticket key from format "Task Name (PX-123)"
            if '(' in dep and dep.endswith(')'):
                ticket_key = dep[dep.rfind('(')+1:-1].strip()
                ticket_keys.append(ticket_key)
            else:
                ticket_keys.append(dep)
        
        return ', '.join(ticket_keys)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Write matched tasks with ticket information
        for task in matched_tasks:
            ticket = task.get('matched_ticket')
            
            if ticket:
                # Get dependencies for this ticket
                dependencies = jira_client.get_ticket_dependencies(ticket, all_tickets)
                dependency_tickets = create_dependency_links(dependencies, jira_client.base_url)
                
                row = {
                    'Task': task['name'],
                    'Ticket(s)': create_jira_link(ticket['key'], jira_client.base_url),
                    'Description': task['description'],
                    'Dependencies': task['dependencies'],
                    'Points': ticket['story_points'] if ticket['story_points'] is not None else task['points'],
                    'Dependency Tickets': dependency_tickets
                }
            else:
                # Task without matching ticket
                row = {
                    'Task': task['name'],
                    'Ticket(s)': task['tickets'],
                    'Description': task['description'],
                    'Dependencies': task['dependencies'],
                    'Points': task['points'],
                    'Dependency Tickets': ''
                }
            
            writer.writerow(row)
        
        # Add unmatched tickets as new rows
        for ticket in unmatched_tickets:
            dependencies = jira_client.get_ticket_dependencies(ticket, all_tickets)
            dependency_tickets = create_dependency_links(dependencies, jira_client.base_url)
            
            # Extract description text from JIRA's complex description format
            description = ''
            if ticket['description']:
                if isinstance(ticket['description'], dict):
                    # Handle JIRA's document format
                    content = ticket['description'].get('content', [])
                    for block in content:
                        if block.get('type') == 'paragraph':
                            for item in block.get('content', []):
                                if item.get('type') == 'text':
                                    description += item.get('text', '')
                else:
                    description = str(ticket['description'])
            
            row = {
                'Task': ticket['summary'],
                'Ticket(s)': create_jira_link(ticket['key'], jira_client.base_url),
                'Description': description,
                'Dependencies': '',  # Original CSV dependencies not available for unmatched tickets
                'Points': ticket['story_points'] if ticket['story_points'] is not None else '',
                'Dependency Tickets': dependency_tickets
            }
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description='Update CSV with JIRA ticket information from epic')
    parser.add_argument('--csv', required=True, help='Path to original CSV file')
    parser.add_argument('--epic', required=True, help='Epic key (e.g., PX-7150)')
    parser.add_argument('--output', required=True, help='Output CSV file path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Create output directory and update output path
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    
    # If output path doesn't already include output directory, prepend it
    if not args.output.startswith('output/'):
        args.output = os.path.join(output_dir, args.output)
    
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
        # Parse original CSV
        logging.info(f"Parsing CSV file: {args.csv}")
        tasks = parse_csv(args.csv)
        logging.info(f"Found {len(tasks)} tasks in CSV")
        
        # Connect to JIRA
        logging.info("Connecting to JIRA...")
        jira = JiraClient(jira_url, jira_email, jira_token)
        
        if not jira.test_connection():
            logging.error("Failed to connect to JIRA")
            sys.exit(1)
        
        # Validate epic
        if not jira.validate_epic(args.epic):
            logging.error(f"Epic validation failed: {args.epic}")
            sys.exit(1)
        
        # Get tickets from epic
        logging.info(f"Fetching tickets from epic {args.epic}...")
        tickets = jira.get_epic_tickets(args.epic)
        
        if not tickets:
            logging.error("No tickets found in epic")
            sys.exit(1)
        
        # Match tickets to tasks
        logging.info("Matching tickets to tasks...")
        matched_tasks, unmatched_tickets = match_tickets_to_tasks(tasks, tickets)
        
        # Write updated CSV
        logging.info(f"Writing updated CSV to: {args.output}")
        write_updated_csv(matched_tasks, unmatched_tickets, tickets, jira, args.output)
        
        # Summary
        matched_count = sum(1 for task in matched_tasks if task.get('matched_ticket'))
        unmatched_task_count = len(matched_tasks) - matched_count
        unmatched_ticket_count = len(unmatched_tickets)
        
        logging.info("Update completed successfully!")
        logging.info(f"Summary:")
        logging.info(f"  - Tasks matched to tickets: {matched_count}")
        logging.info(f"  - Tasks without tickets: {unmatched_task_count}")
        logging.info(f"  - Unmatched tickets added: {unmatched_ticket_count}")
        logging.info(f"  - Output file: {args.output}")
        
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
