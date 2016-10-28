"""
JIRA API wrapper object.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import logging
import re

import requests
from slugify import slugify

# from octoeb.utils.formatting import validate_ticket_name


logger = logging.getLogger(__name__)


class JiraAPI(object):
    """Wrapper for the JIRA API."""
    def __init__(self, base_path, user, token, configs, *args, **kwargs):
        self.auth = (user, token)
        self.base_path = base_path
        self.config = dict(configs)
        self.base = '{}/rest/api/latest/'.format(self.base_path)

    def build_path(self, path):
        """Returns JIRA api enpoint

        Arguments:
            path (str): JIRA API endpoint, sans a leading slash.
        """
        url = '{}{}'.format(self.base, path)

        logger.debug('JiraAPI.build_path: {}'.format(url))
        return url

    def get(self, path, raise_for_status=True, **kwargs):
        """Get path from JIRA"""
        logger.debug('JiraAPI.get: {}'.format(path))
        resp = requests.get(self.build_path(path), auth=self.auth, **kwargs)

        logger.debug(resp)

        if raise_for_status:
            resp.raise_for_status()

        return resp.json()

    def post(self, path, raise_for_status=True, **kwargs):
        """POST to path on JIRA"""
        logger.debug('JiraAPI.post: path={}, kwargs={}'.format(path, kwargs))

        resp = requests.post(
            self.build_path(path), auth=self.auth, **kwargs
        )

        logger.debug(resp)

        if raise_for_status:
            resp.raise_for_status()

        return resp.json()

    def get_issue(self, id, raise_for_status=True):
        """Returns ticket JSON

        Arguments:
            id (str): issue id
            raise_for_status (bool): determines if a non-200 status raises an
                exception.

        Returns:
            dict - JSON representation of the issue

        Raises:

        """
        logger.debug(
            'JiraAPI.get_issue: id={}, raise_for_status={}'.format(
                id, raise_for_status
            )
        )
        endpoint = 'issue/{}'.format(id)
        return self.get(endpoint, raise_for_status)

    def get_filter(self, id, raise_for_status=True):
        """Get JIRA filter definition"""

        logger.debug(
            'JiraAPI.get_filter: id={}, raise_for_status={}'.format(
                id, raise_for_status
            )
        )

        return self.get(
            'filter/{}'.format(id), raise_for_status=raise_for_status)

    def get_my_tickets(self):
        filter_id = self.config.get('ticket_filter_id', None)
        logger.debug('JiraAPI.get_my_tickets: filter_id={}'.format(filter_id))

        if filter_id is None:
            return []

        filter_instance = self.get_filter(filter_id)

        return self.get('search', params={'jql': filter_instance.get('jql')})\
                   .get('issues')

    def get_my_ticket_ids(self):
        """Return string for TAB completion of ticket ids"""
        tickets = self.get_my_tickets()

        return ' '.join(x.get('key') for x in tickets)

    def check_for_issue(self, id, raise_for_status=True):
        """Verify if issue `id` exists

        Arguments:
            id (str): JIRA issue id

        Returns:
            bool
        """
        logger.debug(
            'JiraAPI.check_for_issue: id={}, raise_for_status={}'.format(
                id, raise_for_status
            )
        )
        endpoint = 'issue/{}'.format(id)

        resp = self.get(endpoint)

        if resp:
            return True

        return False

    def get_open_transitions(self, id, subcategory=4, raise_for_status=True):
        """Get list of transitions

        Arguments:
            id (str): JIRA issue to transition
            subcategory (int): Target status subcategory id.
                2 = To Do, 4 = In Progress
        """
        logger.debug(
            'JiraAPI.get_open_transitions: '
            'id={}, subcategory={}, raise_for_status={}'.format(
                id, subcategory, raise_for_status
            )
        )
        # get list of possible transitions
        endpoint = 'issue/{}/transitions'.format(id)
        resp = self.get(endpoint)
        logger.debug(resp)

        transitions = resp.get('transitions')

        in_progress_transitions = [
            (x.get('name'), x.get('id')) for x in transitions
            if x['to']['statusCategory']['id'] == int(subcategory)
        ]

        logger.debug(in_progress_transitions)

        return sorted(x[1] for x in in_progress_transitions)

    def create_issue(self, summary, description='', project='MAN',
                     type='RELEASE', raise_for_status=True):
        """Create a new issue.

        Args:
            project (str): The name of the project
            type (str): The ticket type
            summary (str): The issue summary
            description (str): The description of the issue)
            raise_for_status (bool): Set to True to raise an exception for a
                non-successful status message.

        Returns:
            (str, str): The ticket ID, the ticket name
        """
        endpoint = 'issue'
        payload = {
            'fields': {
                'project': {
                    'key': project,
                },
                'summary': summary,
                'description': description,
                'issuetype': {
                    'name': type,
                },
            },
        }

        logger.debug('JiraAPI.create_issue: project={}, type={}'.format(
            project, type))

        resp = self.post(
            endpoint, json=payload, raise_for_status=raise_for_status)

        return resp.get('id'), resp.get('key')

    def start_issue(self, id, raise_for_status=True):
        """Transition the issue to 'Start'"""
        endpoint = 'issue/{}/transitions'.format(id)
        payload = {
            'transition': {
                'id': 21
            }
        }
        logger.debug(
            'JiraAPI.start_issue: id={}, raise_for_status={}'.format(
                id, raise_for_status
            )
        )
        logger.debug('payload: {}'.format(payload))
        resp = self.post(endpoint, json=payload,
                         raise_for_status=raise_for_status)

        return resp

    def get_status_categories(self):
        logger.debug('JiraAPI.get_status_categories')
        return self.get('statuscategory')

    def get_issue_slug(self, id, summary=None):
        logger.debug('JiraAPI.get_issue_slug')
        if summary is None:
            issue = self.get_issue(id)
            summary = issue.get('fields').get('summary')

        return '{}-{}'.format(id, slugify(summary))

    def get_issue_summary(self, id):
        logger.debug('JiraAPI.get_issue_summary')
        issue = self.get_issue(id)
        return issue.get('fields').get('summary')

    def get_release_notes(self, version_id, project_id):
        logger.debug('JiraAPI.get_release_notes')
        path = (
            '{}secure/ReleaseNote.jspa?version={}&styleName=Text&projectId={}'
        ).format('https://eventboard.atlassian.net/', version_id, project_id)

        resp = requests.get(path, auth=self.auth)

        notes = re.findall(
            r'<textarea rows="40" cols="120">(.*)</textarea>',
            resp.content,
            re.S | re.M
        )[0]

        # convert  JIRA text markup to Markdown for the github release
        # description
        notes = re.sub(r'\n{2,}', '\n\n', notes)
        notes = re.sub(r'\s+\*\*\s', '\n\n#### ', notes)
        notes = re.sub(r'\s+\*\s', '\n* ', notes)
        return notes
