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

        logger.debug('JiraAPI.build_path: {}'.foramt(url))
        return url

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
        resp = requests.get(self.build_path(endpoint), auth=self.auth)

        if raise_for_status:
            resp.raise_for_status()

        return resp.json()

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
        resp = requests.get(self.build_path(endpoint), auth=self.auth)

        if raise_for_status:
            resp.raise_for_status()

        if resp.status_code == 200:
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
        resp = requests.get(self.build_path(endpoint), auth=self.auth)
        logger.debug(resp)

        if raise_for_status:
            resp.raise_for_status()

        transitions = resp.json().get('transitions')

        in_progress_transitions = [
            (x.get('name'), x.get('id')) for x in transitions
            if x['to']['statusCategory']['id'] == int(subcategory)
        ]

        logger.debug(in_progress_transitions)

        return sorted(x[1] for x in in_progress_transitions)

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
        resp = requests.post(
            self.build_path(endpoint), json=payload, auth=self.auth
        )

        logger.debug(payload)
        logger.debug(resp)

        if raise_for_status:
            resp.raise_for_status()

        return None

    def get_issue_slug(self, id):
        logger.debug('JiraAPI.get_issue_slug')
        issue = self.get_issue(id)
        return '{}-{}'.format(id, slugify(issue.get('fields').get('summary')))

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

        # convert the notes to markdown for the github release description
        notes = re.sub(r'\n{2,}', '\n\n', notes)
        notes = re.sub(r'\s+\*\*\s', '\n\n#### ', notes)
        notes = re.sub(r'\s+\*\s', '\n* ', notes)
        return notes
