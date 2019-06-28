"""Git repo API wrapper"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from contextlib import contextmanager
import logging
import re
import subprocess


from octoeb.utils.config import get_config
from octoeb.utils.config import get_config_value


logger = logging.getLogger(__name__)


class GitError(Exception):
    pass


def fetch(remote_name):
    return subprocess.call(['git', 'fetch', remote_name])


def checkout(branch_name):
    return subprocess.call(['git', 'checkout', branch_name])


def update(base_branch):
    return subprocess.call(['git', 'pull', '-r', base_branch])


staticfiles_re = re.compile(r'^[AMD].*static.*', re.I)
pip_re = re.compile(r'M.*requirements.*', re.I)
migrations_re = re.compile(r'A.*migrations.*', re.I)
integrations_re = re.compile(r'M.*integrations', re.I)


def log_messages(base='develop', head='', number=None):
    """Return the log messages of the current branch, since base."""
    cmd = ['git', 'log', '--format=%B', ]
    cmd.append('{base}...'.format(base=base))
    try:
        logger.debug(u'Running: {}'.format(cmd))
        return subprocess.check_output(cmd)
    except subprocess.CalledProcessError:
        raise ValueError('Can not generate log messages.')


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
    return re.findall(r'^[AMD].*bower.*', log, flags=re.M)


def find_requirements_changes(base='master', head=''):
    try:
        cmd = ['git', 'diff']
        cmd.append('{base}..{head}'.format(base=base, head=head))
        cmd.append('--')
        cmd.append('requirements.txt')
        cmd_output = subprocess.check_output(cmd)
    except subprocess.CalledProcessError:
        raise ValueError('Could not find diff of requirements. Directory may '
                         'not be a git repo')

    return re.findall(r'^[\+\-].*', cmd_output, flags=re.M)


def find_cron_changes(log):
    files = None
    cron_changes = list()

    with open('/dev/null', 'w') as devnull:
        try:
            cmd = ['./do', 'get_cron_files']
            files = subprocess.check_output(cmd, stderr=devnull)
        except Exception:
            logger.debug('Error trying to run this thing')

    if files:
        files_list = files.split('\n')
        for f in files_list:
            if f and not f.startswith('DEBUG'):
                search = r'^[AMD].*' + re.escape(f.strip()) + '.*'
                if re.findall(search, log, flags=re.M):
                    cron_changes.append(f)

    return cron_changes


def changelog(log, ticket_ids=False):
    """Generate changelog from a git log.

    Args:
        log (str): A string containing a gitlog, as from the `log` method.
        ticket_ids (bool): default False, when True we return a tuple that
            of the form `(ticket_ids, str_changelog)`.

    Returns:
        str or tuple.
    """

    config = get_config()
    changelog_re_pattern = get_config_value(
        config, 'repo', 'changelog_re',
        "merge pull request #\d+ from [\w/]*(?:[/-]([a-z]{2,4}-\d+)-(.*))"
    )
    issue_re_pattern = get_config_value(
        config, 'repo', 'issue_re',
        "merge pull request #\d+ from [\w/]*(?:[/-]([a-z]+-\d+))")

    issue_re = re.compile(issue_re_pattern, re.I)
    changelog_re = re.compile(changelog_re_pattern, re.I)

    try:
        jira_issues = issue_re.findall(log)
        changelog = changelog_re.findall(log)
    except subprocess.CalledProcessError:
        jira_issues = []
        changelog = []
    else:
        jira_issues = set(jira_issues)
        for i, m in enumerate(changelog):
            logger.debug('Change Log: {}, {}'.format(i, m))
            # m[0] is the issue id
            # m[1] is the issue title
            changelog[i] = u'* {} : {}'.format(
                m[0].upper(),
                m[1].replace(u'-', u' ').replace(u'_', u' ').title()
            )
        changelog = u'\n'.join(sorted(set(changelog)))

    if ticket_ids:
        return jira_issues, changelog

    return changelog


def get_deploy_relavent_changes(base, head):
    log_str = log(base, head)
    staticfile_changes = find_staticfile_changes(log_str)
    migration_changes = find_migrations_changes(log_str)
    bower_changes = find_bower_changes(log_str)
    pip_changes = find_requirements_changes(base=base, head=head)
    cron_changes = find_cron_changes(log_str)

    if staticfile_changes:
        staticfile_msg = 'Staticfile changes:\n{}'.format(
            u'\n'.join(staticfile_changes))
    else:
        staticfile_msg = 'No staticfile changes'

    if bower_changes:
        bower_msg = 'Bower chagnes:\n{}'.format(
            u'\n'.join(bower_changes))
    else:
        bower_msg = 'No bower changes'

    if pip_changes:
        pip_msg = 'Pip changes:\n{}'.format(
            u'\n'.join(pip_changes))
    else:
        pip_msg = 'No pip changes'

    if cron_changes:
        cron_msg = 'Cron Changes:\n{}'.format(
            u'\n'.join(cron_changes))
    else:
        cron_msg = 'No cron changes'

    return (staticfile_msg, bower_msg, pip_msg, cron_msg), migration_changes


@contextmanager
def on_branch(name, remote_name='mainline'):
    """Quickly out a branch and then revert to the orignal state.

    The `on_branch` context manager allows you to store the user's current
    branch info, including any staged or unstaged changes.  It will then
    checkout the named branch, update it from the remote, and then do
    the work inside the context manager.  When finished it will go back to
    the original branch and pop any stashed work.
    """
    # store the current branch info
    org_branch = subprocess.check_output([
        'git', 'rev-parse', '--abbrev-ref', 'HEAD'
    ])
    org_branch = org_branch.strip()
    logger.debug('current branch name: {}'.format(org_branch))

    logger.debug('stashing current branch')
    stash_ref = subprocess.check_output(['git', 'stash', 'create', '-q'])
    stash_ref = stash_ref.strip()

    if stash_ref:
        logger.debug('stash_ref: {}'.format(stash_ref))
        subprocess.call(['git', 'stash', 'store', '-q', stash_ref])
        subprocess.call(['git', 'reset', '--hard'])

    # go to the new branch
    subprocess.call(['git', 'checkout', '-q', name])
    # update the branch from the remote
    subprocess.call(['git', 'pull', '-q', remote_name, name])

    # do work inside the context manager here
    yield

    # go back to the original branch state
    logger.debug('checkout the original branch: {}'.format(org_branch))
    subprocess.call(['git', 'checkout', '-q', org_branch])

    if stash_ref:
        subprocess.call(['git', 'stash', 'pop', '-q'])
