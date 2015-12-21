"""Wrapper utilities to help with managing python related functions etc."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import subprocess

from octoeb.utils.git import GitError


def check_flake8_issues(base_branch='develop', head_branch=None):
    """Validate the python style of the new code.

    Run flake8 on the diff between base_branch and head_branch.

    Args:
        base_branch (str): name of the base branch to compare with. Defaults to
            develop.
        head_branch (str): name of the branch with the code changes.  If None,
            it will use the currently checked out branch.

    Returns:
        str - Empty string if no flake8 issues are raised, else the output of
            flake8.

    Raises:
        octoeb.utils.git.GitError: we could not get the git-diff of the provided
            sha range.
    """
    if head_branch is None:
        sha_range = u'{}..'.format(base_branch)
    else:
        sha_range = u'{}..{}'.format(base_branch, head_branch)

    try:
        diff = subprocess.Popen(
            ('git', 'diff', sha_range), stdout=subprocess.PIPE)
    except subprocess.CalledProcessError:
        raise GitError('Can not retreive the git diff')

    try:
        subprocess.check_output(
            ('flake8', '--diff'), stdin=diff.stdout, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        return e.output

    return ''
