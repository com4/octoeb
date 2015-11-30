"""
JIRA API wrapper object.
"""
from __future__ import absolute_import
import logging

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

        logger.debug(url)
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
        resp = requests.post(
            self.build_path(endpoint), json=payload, auth=self.auth
        )

        logger.debug(payload)
        logger.debug(resp)

        if raise_for_status:
            resp.raise_for_status()

        return None

    def get_issue_slug(self, id):

        issue = self.get_issue(id)
        return '{}-{}'.format(id, slugify(issue.get('fields').get('summary')))
