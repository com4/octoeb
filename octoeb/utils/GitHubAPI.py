from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import logging
import re

import requests

from octoeb.utils.config import get_config
from octoeb.utils.formatting import build_release_base_name
from octoeb.utils.formatting import extract_year_week_version
from octoeb.utils.formatting import extract_release_branch_version


logger = logging.getLogger(__name__)

RELEASE_TICKET_ID_RE = re.compile(
    r'^release ticket id: ([a-z0-9-]*)$',
    re.I | re.M
)


class DuplicateBranchError(Exception):
    pass


class GitHubAPIError(Exception):
    """Raised when there is a non-200 level error from the GitHub API"""
    pass


class GitHubAPI(object):
    DuplicateBranchError = DuplicateBranchError

    def __init__(self, user, token, owner, repo, *args, **kwargs):
        self.user = user
        self.token = token
        self.owner = owner
        self.repo = repo
        self.base = 'https://api.github.com/repos/{}/{}/'.format(owner, repo)

    def build_path(self, path):
        """Concatenates the URL for the Github API with the provided path

        Args:
            path (str): Path of interest. For example releases/latest

        Returns:
            str: Fully qualified URL for the Github API resource.
            E.g. ``https://api.github.com/repos/user/repo/releases/latest/``
            where user and repo are the username and repository name for the
            project.
        """
        return '{}{}'.format(self.base, path)

    def send_request(self, method, path, *args, **kwargs):
        """Request the provided ``path`` from Github using the HTTP ``method``

        .. note::

           Additional args and kwargs will be passed to the request. These are
           used in POST and PATCH requests.

        Args:
            method (str): The HTTP method for this request. GET, POST, PATCH,
                DELETE, etc
            path (str): The resource path for this request.
                E.g. releases/latest

        Returns:
            :class:`requests.Response`: The response of the request.
        """
        path = self.build_path(path)

        logger.debug('GitHubAPI.send_request: {} {} {} {}'.format(
            method, path, args, kwargs))

        response = requests.request(
            method, path, auth=(self.user, self.token), *args, **kwargs)

        if response.status_code > 299:
            raise GitHubAPIError('Status: {}; Message: {}'.format(
                    response.status_code, response.json()['message']))

        logger.debug('GitHubAPI.send_request response: {}'.format(
            response))

        return response

    def get(self, path):
        return self.send_request('GET', path)

    def post(self, path, *args, **kwargs):
        return self.send_request('POST', path, *args, **kwargs)

    def patch(self, path, *args, **kwargs):
        return self.send_request('PATCH', path, *args, **kwargs)

    def releases(self):
        return self.get('releases')

    def prereleases(self):
        resp = self.get('releases')

        try:
            releases = resp.json()
        except Exception:
            logger.error('GitHubAPI.prereleases could not parse to json')
            releases = []

        return [x for x in releases if x.get('prerelease')]

    def latest_release(self):
        resp = self.get('releases/latest')

        return resp.json()

    def latest_prerelease(self):
        prereleases = self.prereleases()
        if not prereleases:
            return None

        return prereleases[0]

    def get_release(self, name, raise_for_status=True):
        resp = self.get('releases/tags/{}'.format(name))

        if raise_for_status:
            resp.raise_for_status()

        return resp.json()

    def get_release_ticket_key_for_tag(self, name):
        try:
            resp = self.get_release(name)
            return RELEASE_TICKET_ID_RE.search(resp.get('body', '')).group(1)
        except Exception:
            logger.error(resp)
            logger.exception('Failed to get release ticket id')

        return None

    def get_branch(self, name, raise_for_status=True):
        resp = self.get('git/refs/heads/{}'.format(name))

        if raise_for_status:
            resp.raise_for_status()

        return resp.json()

    def compare(self, base, head, raise_for_status=True):
        resp = self.get('compare/{}...{}'.format(base, head))

        if raise_for_status:
            resp.raise_for_status()

        return resp.json()

    def create_branch(self, name, base_name, from_sha=False):
        """Create a new branch.

        Args:
            name (str): name of the new branch
            base_name (str): name of the base branch or the base sha
            from_sha (bool): determine if the `base_name` is a sha or a name.
                Defaults to False.

        Returns:
            dict: json response from GitHub.

        Raises:
            DuplicateBranchError
            Exception
        """

        logger.debug(
            'GitHubAPI.create_branch: name={}, base_name={}'.format(
                name, base_name
            )
        )
        # raise an error if we can find the branch, continue if we get
        # a 404
        try:
            self.get_branch(name)
        except GitHubAPIError:
            pass
        else:
            raise DuplicateBranchError(
                'Branch already started. Run'
                '\n\tgit fetch --all && get checkout {}'.format(name)
            )

        if not from_sha:
            base = self.get_branch(base_name)
            base_sha = base['object']['sha']
        else:
            base_sha = base_name

        try:
            branch_info = {
                'ref': 'refs/heads/{}'.format(name),
                'sha': base_sha
            }
        except KeyError:
            logger.error('base repsonse: {}'.format(base))
            raise Exception(
                'Could not locate the current SHA for '.format(base_name))

        resp = self.post('git/refs', json=branch_info)
        try:
            resp.raise_for_status()
        except Exception:
            logger.error(resp.json())
            raise

        return resp.json()

    def update_branch(self, name, sha):
        """Update attempt to update branch to the given SHA."""
        branch_info = {
            'sha': sha,
        }
        resp = self.patch('git/refs/heads/{}'.format(name), json=branch_info)

        try:
            resp.raise_for_status()
        except Exception:
            logger.error(resp.json())
            raise

        return resp.json()

    def create_release_branch(self, release_name):
        return self.create_branch(release_name, 'develop')

    def create_hotfix_branch(self, fix_name):
        return self.create_branch(fix_name, 'master')

    def create_releasefix_branch(self, fix_name, version_name):
        return self.create_branch(fix_name, version_name)

    def create_feature_branch(self, feature_name):
        return self.create_branch(feature_name, 'develop')

    def create_pull_request(self, base, head, title, body=None):
        """Create a new pull request

        Arguments:
            base (str): name of the branch where your changes are implemented.
                For cross-repository pull requests in the same network,
                namespace head with a user like this: username:branch
            head (str): name of the branch you want your changes pulled into.
        """
        pull_info = {
            'title': title,
            'head': head,
            'base': base
        }
        if body:
            pull_info['body'] = body

        logger.info(pull_info)

        resp = self.post('pulls', json=pull_info)
        try:
            resp.raise_for_status()
        except Exception:
            logger.error(resp.json())
            raise

        return resp.json()

    def create_pre_release(self, release_name, release_branch_name, body=""):

        release_branch = self.get_branch(release_branch_name)

        try:
            self.get_release(release_name)
        except GitHubAPIError:
            pass
        else:
            raise Exception(
                'Release already created.'
            )

        try:
            release_info = {
                "tag_name": release_name,
                "target_commitish": release_branch['object']['sha'],
                "name": release_branch_name,
                "body": body,
                "draft": False,
                "prerelease": True
            }
        except KeyError:
            logger.error('Release branch repsonse: {}'.format(release_branch))
            raise Exception('Could not locate the current SHA for the release')

        resp = self.post('releases', json=release_info)
        try:
            resp.raise_for_status()
        except Exception:
            logger.error(resp.json())
            raise

        return resp.json()

    def check_release_status(self, release_name, release_branch):
        """Verify that the release is actually read to be released

        If the release is new (corresponds to a release branch), then we check
        that the release is merged into master.

        If we can not find the release branch, we assume that it is a hotfix
        and we verify that the major version number matches the latest release.

        Args:
            release_name (str): the version number to release

        Returns:
            None

        Raises:
            - Exception
            - GitHubAPIError
        """
        logger.debug('GitHubAPI.check_release_status args: {}; {}'.format(
            release_name, release_branch)
        )
        release_version = extract_release_branch_version(release_name)
        release_branch_base = build_release_base_name(get_config())
        # Assume that this is a new release
        # Check if the release branch is merged into master
        try:
            merge_status = self.compare(
                'master',
                release_branch
            ).get('status')
        except GitHubAPIError as e:
            logger.debug('HTTPError: {}'.format(e.message))
            if not e.response.status_code == 404:
                raise e
        else:
            # can be one of diverged, ahead, behind, identical according to
            # http://stackoverflow.com/a/23969867
            if merge_status in ['diverged', 'ahead']:
                raise Exception(
                    'Release must be merged into master before release')
            return

        # if the release branch does not exist, then we end up here,
        # Assume that it is a hotfix
        raw_version = self.latest_release().get('name', '')
        if raw_version.startswith(release_branch_base):
            raw_version = raw_version[len(release_branch_base):]

        version = extract_year_week_version(raw_version)
        logger.debug(version)
        if extract_year_week_version(release_version) != version:
            raise Exception(
                'New release version does not match the current release, '
                'we expected a hotfix.'
            )

        return

    def create_release(self, release_name, release_branch, body=""):

        logger.info("GithubAPI.create_release: {}; {}".format(
            release_name, release_branch))
        logger.info("GithubAPI.create_release body: {}".format(body))
        self.check_release_status(release_name, release_branch)

        try:
            self.get_release(release_name)
        except GitHubAPIError:
            pass
        else:
            raise Exception(
                'Release already created.'
            )

        master = self.get_branch('master')
        try:
            release_info = {
                "tag_name": release_name,
                "target_commitish": master['object']['sha'],
                "name": release_branch,
                "body": body,
                "draft": False,
                "prerelease": False
            }
        except KeyError:
            logger.error('Release branch repsonse: {}'.format(master))
            raise Exception('Could not locate the current SHA for the release')

        resp = self.post('releases', json=release_info)
        try:
            resp.raise_for_status()
        except Exception:
            logger.error(resp.json())
            raise

        return resp.json()

    def get_statuses(self, ref):
        logger.info('GitHubAPI.get_statuses')
        resp = self.get('statuses/{ref}'.format(ref=ref))

        return resp.content
