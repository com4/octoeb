from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import logging

import requests

from octoeb.utils.formatting import extract_major_version


logger = logging.getLogger(__name__)


class DuplicateBranchError(Exception):
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
        url = '{}{}'.format(self.base, path)

        logger.debug(url)
        return url

    def get(self, path):
        return requests.get(
            self.build_path(path),
            auth=(self.user, self.token)
        )

    def post(self, path, *args, **kwargs):
        logger.debug('GitHubAPI.post: {} {} {}'.format(path, args, kwargs))
        return requests.post(
            self.build_path(path),
            auth=(self.user, self.token), *args, **kwargs
        )

    def releases(self):
        return self.get('releases')

    def prereleases(self):
        resp = self.get('releases')

        logger.debug(resp)

        try:
            releases = resp.json()
        except Exception:
            logger.error('GitHubAPI.prereleases could not parse to json')
            releases = []

        return [x for x in releases if x.get('prerelease')]

    def latest_release(self):
        resp = self.get('releases/latest')

        logger.debug(resp)

        return resp.json()

    def latest_prerelease(self):
        prereleases = self.prereleases()
        if not prereleases:
            return None

        return prereleases[0]

    def get_release(self, name, raise_for_status=True):
        resp = self.get('releases/tags/{}'.format(name))

        logger.debug(resp)
        if raise_for_status:
            resp.raise_for_status()

        return resp.json()

    def get_branch(self, name, raise_for_status=True):
        resp = self.get('git/refs/heads/{}'.format(name))

        logger.debug(resp)
        if raise_for_status:
            resp.raise_for_status()

        return resp.json()

    def compare(self, base, head, raise_for_status=True):
        resp = self.get('compare/{}...{}'.format(base, head))

        logger.debug(resp)
        if raise_for_status:
            resp.raise_for_status()

        return resp.json()

    def create_branch(self, name, base_name):
        # raise an error if we can find the branch, continue if we get
        # a 404
        try:
            self.get_branch(name)
        except requests.exceptions.HTTPError:
            pass
        else:
            raise DuplicateBranchError(
                'Branch already started. Run'
                '\n\tgit fetch --all && get checkout {}'.format(name)
            )

        base = self.get_branch(base_name)
        try:
            branch_info = {
                'ref': 'refs/heads/{}'.format(name),
                'sha': base['object']['sha']
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

    def create_release_branch(self, release_name):
        return self.create_branch(release_name, 'develop')

    def create_hotfix_branch(self, fix_name):
        return self.create_branch(fix_name, 'master')

    def create_releasefix_branch(self, fix_name, version_name):
        return self.create_branch(fix_name, version_name)

    def create_feature_branch(self, feature_name):
        return self.create_branch(feature_name, 'develop')

    def create_pull_request(self, base, head):
        """Create a new pull request

        Arguments:
            base (str): name of the branch where your changes are implemented.
                For cross-repository pull requests in the same network,
                namespace head with a user like this: username:branch
            head (str): name of the branch you want your changes pulled into.
        """
        pull_info = {
            'head': head,
            'base': base
        }
        logger.info(pull_info)

        resp = self.post('pulls', json=pull_info)
        try:
            resp.raise_for_status()
        except Exception:
            logger.error(resp.json())
            raise

        return resp.json()

    def create_pre_release(self, release_name, body=""):
        name = 'release-{}'.format(extract_major_version(release_name))
        release_branch = self.get_branch(name)

        try:
            self.get_release(release_name)
        except requests.exceptions.HTTPError:
            pass
        else:
            raise Exception(
                'Release already created.'
            )

        try:
            release_info = {
                "tag_name": release_name,
                "target_commitish": release_branch['object']['sha'],
                "name": 'release-{}'.format(release_name),
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

    def create_release(self, release_name, body=""):

        # maybe we should just trying merging the branches
        # https://developer.github.com/v3/repos/merging/
        merge_status = self.compare(
            'master',
            'release-{}'.format(extract_major_version(release_name))
        ).get('status')

        # can be one of diverged, ahead, behind, identical according to
        # http://stackoverflow.com/a/23969867
        if merge_status in ['diverged', 'ahead']:
            raise Exception(
                'Release must be merged into master before release')

        try:
            self.get_release(release_name)
        except requests.exceptions.HTTPError:
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
                "name": 'release-{}'.format(release_name),
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
