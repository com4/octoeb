"""Git repo API wrapper"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import logging
import re
import subprocess

logger = logging.getLogger(__name__)
changelog_re = re.compile(
    r'merge pull request #\d+ from .*(?:[/-]([a-z]{2,4}-\d+)-(.*))', re.I)


class GitError(Exception):
    pass


def fetch(remote_name):
    return subprocess.call(['git', 'fetch', remote_name])


def checkout(branch_name):
    return subprocess.call(['git', 'checkout', branch_name])


def update(base_branch):
    return subprocess.call(['git', 'pull', '-r', base_branch])


def changelog(base_branch, new_branch):
    """
    Generate the JIRA issue changelog between base_branch and new_branch

    Args:
        base_branch (str): name of the branch to compare against
        new_branch (str): name of the branch with the new changes

    Returns:
        str: This will be a paragraph of text of the format

            PROJECT_ID-NUMBER: Remaining Branch Name Title Cased
            PROJECT_ID-NUMBER: Remaining Branch Name Title Cased
            PROJECT_ID-NUMBER: Remaining Branch Name Title Cased
            PROJECT_ID-NUMBER: Remaining Branch Name Title Cased
    """
    try:
        log = subprocess.check_output(
            (
                'git', 'log', '--oneline', '--merges',
                '{base}..{new}'.format(base=base_branch, new=new_branch)
            )
        )
        changelog = changelog_re.findall(log)
    except subprocess.CalledProcessError as e:
        logger.error(e)
        changelog = []
    else:
        for i, m in enumerate(changelog):
            # m[0] is the issue id
            # m[1] is the issue title
            changelog[i] = '{}: {}'.format(
                m[0].upper(),
                m[1].replace('-', ' ').replace('_', ' ').title()
            )
        return '\n'.join(sorted(changelog))
