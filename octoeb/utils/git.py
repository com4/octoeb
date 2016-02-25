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


issue_re = re.compile(
    r'merge pull request #\d+ from .*(?:[/-]([a-z]+-\d+))', re.I)
changelog_re = re.compile(
    r'merge pull request #\d+ from .*(?:[/-]([a-z]{2,4}-\d+)-(.*))', re.I)
staticfiles_re = re.compile(r'^[AMD].*static.*', re.I)
pip_re = re.compile(r'M.*requirements.*', re.I)
migrations_re = re.compile(r'A.*migrations.*', re.I)


integrations_re = re.compile(r'M.*integrations', re.I)


def log(base='master', head='', directory=None, merges=False):
    """Retrun simple git log.

    Args:
        base (str): base branch or sha to compare with.
        head (str): branch or sha with most recent changes.
        directory (str): directory of the git repo, if None, we assume the
            cwd.
        merges (bool): default False, when true the git log will be the minimal
            oneline log with merges shown. When false, the log is the more
            vervose log with file changes included.

    Return:
        str
    """
    try:
        cmd = ['git', 'log', ]
        if merges:
            cmd.append('--oneline')
            cmd.append('--merges')
        else:
            cmd.append('--name-status')

        cmd.append('{base}..{head}'.format(base=base, head=head))
        logger.debug(u'Running: {}'.format(cmd))
        return subprocess.check_output(cmd)
    except subprocess.CalledProcessError:
        raise ValueError(
            'Can not find the git log, directory may not be a repo')


def find_staticfile_changes(log):
    return staticfiles_re.findall(log)


def find_migrations_changes(log):
    return migrations_re.findall(log)


def find_bower_changes(log):
    return re.findall(r'^[AMD].*bower.*', log)


def find_requirements_changes(log):
    return re.findall(r'^M.*requirements.*', log)


def changelog(log, ticket_ids=False):
    """Generate changelog from a git log.

    Args:
        log (str): A string containing a gitlog, as from the `log` method.
        ticket_ids (bool): default False, when True we return a tuple that
            of the form `(ticket_ids, str_changelog)`.

    Returns:
        str or tuple.
    """
    try:
        jira_issues = issue_re.findall(log)
        changelog = changelog_re.findall(log)
    except subprocess.CalledProcessError:
        jira_issues = []
        changelog = []
    else:
        jira_issues = set(jira_issues)
        for i, m in enumerate(changelog):
            # m[0] is the issue id
            # m[1] is the issue title
            changelog[i] = u'{}: {}'.format(
                m[0].upper(),
                m[1].replace(u'-', u' ').replace(u'_', u' ').title()
            )
        changelog = u'\n'.join(sorted(changelog))

    if ticket_ids:
        return jira_issues, changelog

    return changelog
