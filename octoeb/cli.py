#! /usr/bin/env python
"""
OctoEB is a script to help with the integration of Gitflow, Github, and Jira.

## Installation
The only external library that this tool depends on is Requests.  Clone the
repo run

    pip install .

To verify the install, start a new shell and run

    octoeb -h

## Configuration
The script looks for the file `.octoebrc` in either
your home directory or the current directory.  We expect this file to
contain the following ini-style configuration:

```
[repo]
OWNER=repo-owner
FORK=fork-repo-owner
REPO=repo-name
TOKEN=oauth-token
USER=email@test.com
```

1) OWNER and REPO are https://github.com/OWNER/REPO when you vist a repo on
   GitHub, so for example https://github.com/enderlabs/octoeb gives
   OWNER=enderlabs and REPO=octoeb
2) The token can be obtained from https://github.com/settings/tokens
3) USER is your login email for GitHub


## Usage
There are three major command `start`, `qa`, and `release`. Enter
    $ octoeb start --help
    $ octoeb qa --help
    $ octoeb release --help
respectively for usage details.
"""

# import argparse
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser
import logging
import re
import subprocess
import sys

import click
from requests.exceptions import RequestException

from octoeb.utils.formatting import build_release_name
from octoeb.utils.formatting import extract_release_branch_version
from octoeb.utils.formatting import slackify_release_name
from octoeb.utils import git
from octoeb.utils import python
from octoeb.utils import migrations
from octoeb.utils.config import get_config
from octoeb.utils.config import get_config_value
from octoeb.utils.GitHubAPI import GitHubAPI, GitHubAPIError
from octoeb.utils.JiraAPI import JiraAPI
from octoeb.utils.slack import create_release_channel

try:
    import slacker
except ImportError:
    slacker = None


logger = logging.getLogger(__name__)
click.disable_unicode_literals_warning = True
# Allow commands to access the api object via the clikc ctx
pass_api = click.make_pass_decorator(GitHubAPI)
# use to allow -h for for help
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


def set_logging(ctx, param, level):
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise click.BadParameter('Invalid log level: {}'.format(level))

    logger.setLevel(numeric_level)


def validate_version_arg(ctx, param, version):
    if version is None:
        raise click.BadParameter('Version number is required')

    if re.match(r'^(?:\.?\d+){4,5}$', version):
        return version

    raise click.BadParameter('Invalid version format: {}'.format(version))


def validate_version_arg_or_latest_prerelease(ctx, param, version):
    if version is None:
        logger.debug('Version not provided, pulling latest from github')
        version = ctx.obj['apis'].\
            get('mainline').latest_prerelease().get('tag_name')
        if version is None:
            raise click.BadParameter('Version number is required')

        logger.debug('Found pre-release version: {}'.format(version))

    if re.match(r'^(?:\.?\d+){4,5}$', version):
        return version

    raise click.BadParameter('Invalid version format: {}'.format(version))


def validate_ticket_arg(ctx, param, name):
    """Verify issue id format and return issue slug"""
    if name is None:
        raise click.BadParameter('Ticket number is required')

    if re.match(r'^[a-zA-Z]+-\d+', name):
        return name

    raise click.BadParameter('Invalid ticket format {}'.format(name))


def validate_ticket_arg_or_pull_from_branch(ctx, param, name):
    """Verify issue id format and return issue slug"""
    if name is None:
        logger.debug('Ticket id not provided, search the current branch')
        branch_name = subprocess.check_output([
            'git', 'rev-parse', '--abbrev-ref', 'HEAD'
        ])
        name_result = re.match(
            r'^[a-zA-Z]+-?/?([a-zA-Z]+-\d+).*', branch_name.strip())
        if name_result is None:
            raise click.BadParameter('Ticket number is required')

        else:
            logger.debug('Found ticket id: {}'.format(name_result.group(1)))
            return name_result.group(1)

    if re.match(r'^[a-zA-Z]+-\d+', name):
        return name

    raise click.BadParameter('Invalid ticket format {}'.format(name))


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    '--log',
    default='ERROR', help='Set the log level',
    expose_value=False,
    callback=set_logging,
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']))
@click.version_option('1.4')
@click.pass_context
def cli(ctx):
    """CLI main entry point"""
    # Setup the API
    config = get_config()

    ctx.obj = {
        'apis': {
            'mainline': GitHubAPI(
                config.get('repo', 'USER'),
                config.get('repo', 'TOKEN'),
                config.get('repo', 'OWNER'),
                config.get('repo', 'REPO')
            ),
            'fork': GitHubAPI(
                config.get('repo', 'USER'),
                config.get('repo', 'TOKEN'),
                config.get('repo', 'FORK'),
                config.get('repo', 'REPO')
            ),
            'jira': JiraAPI(
                config.get('bugtracker', 'BASE_URL'),
                config.get('bugtracker', 'USER'),
                config.get('bugtracker', 'TOKEN'),
                config.items('bugtracker')
            ),
        },
        'config': config,
    }

    if slacker:
        try:
            ctx.obj['apis']['slack'] = slacker.Slacker(
                config.get('slack', 'TOKEN'))
        except ConfigParser.NoSectionError:
            pass


@cli.command()
@click.pass_obj
def sync(ctx):
    """Sync fork with mainline

    Checkout each core branch (master and develop), pull from `mainline`, then
    push to the origin (the fork).

    Returns:
        None
    """
    # TODO: It would be nice if the master and develop branch names where
    #       configurable.  In fact, it would be good if we could do this for
    #       more branches.
    logger.debug('stashing current branch')
    stash_ref = subprocess.check_output(['git', 'stash', 'create', '-q'])
    stash_ref = stash_ref.strip()

    if stash_ref:
        logger.debug('stash_ref: {}'.format(stash_ref))
        subprocess.call(['git', 'stash', 'store', '-q', stash_ref])
        subprocess.call(['git', 'reset', '--hard'])

    try:
        org_branch = subprocess.check_output([
            'git', 'rev-parse', '--abbrev-ref', 'HEAD'
        ])
        org_branch = org_branch.strip()
        logger.debug('current branch name: {}'.format(org_branch))

        # sync each core branch
        for x in ('master', 'develop'):
            logger.debug('syncing {}'.format(x))
            subprocess.call(['git', 'checkout', '-q', x])
            subprocess.call(['git', 'pull', '-q', 'mainline', x])
            subprocess.call(['git', 'push', 'origin', x])

        logger.debug('checkout the original branch: {}'.format(org_branch))
        subprocess.call(['git', 'checkout', '-q', org_branch])
    finally:
        if stash_ref:
            subprocess.call(['git', 'stash', 'pop', '-q'])

    sys.exit()


@cli.command()
@click.option(
    '-b', '--base',
    help='Set the base branch to update from',
)
@click.pass_obj
def update(ctx, base):
    """Update local branch from the upstream base

    Rebase the local branch with any changes from the upstream copy of the base
    branch.  That is, for example, if the current branch is

        feature-EB-123-abc

    Then the base branch is `develop` and the `update` command is equivalent
    to

        $ git stash

        $ git pull -r mainline develop

        $ git push -f origin feature-EB-123

        $ git stash pop

    Returns:
        None
    """
    # get the current branch name
    current_branch = subprocess.check_output([
        'git', 'rev-parse', '--abbrev-ref', 'HEAD'
    ])
    current_branch = current_branch.strip()
    logger.debug('current branch: {}'.format(current_branch))

    # try to detect if branch is hotfix, releasefix, feature, or a release
    branch_type = current_branch.split('-')[0]
    BRANCH_TYPE_UPDATE_MAP = {
        'hotfix': 'master',
        'feature': 'develop',
    }

    if branch_type not in BRANCH_TYPE_UPDATE_MAP and not base:
        sys.exit(
            'We can not determine the base branch to be used,'
            ' supply a --base value to continue.'
        )

    base_branch = base or BRANCH_TYPE_UPDATE_MAP.get(branch_type)
    logger.debug('Base branch determined as: {}'.format(base_branch))

    logger.debug('stashing current branch')
    stash_ref = subprocess.check_output(['git', 'stash', 'create', '-q'])
    stash_ref = stash_ref.strip()

    if stash_ref:
        logger.debug('stash_ref: {}'.format(stash_ref))
        subprocess.call(['git', 'stash', 'store', '-q', stash_ref])
        subprocess.call(['git', 'reset', '--hard'])

    try:
        logger.debug('Updating the local branch')
        subprocess.check_call(['git', 'pull', '-r', 'mainline', base_branch])
    except subprocess.CalledProcessError:
        # if the pull -r fails, abort the rebase and checkout the original
        # branch
        subprocess.call(['git', 'rebase', '--abort'])
        subprocess.call(['git', 'checkout', current_branch])
    else:
        # if there are no errors, push the changes to origin
        logger.debug('Pushing update to origin')
        subprocess.call(['git', 'push', '-f', 'origin', base_branch])
    finally:
        # alway try to pop the stash changes after the update is done
        if stash_ref:
            logger.debug('Pop stashed changes')
            subprocess.call(['git', 'stash', 'pop', '-q'])

    sys.exit()


@cli.group()
@click.pass_obj
def start(ctx):
    """Start new branch for a fix, feature, or a new release"""
    pass


@start.command('release')
@click.option(
    '-v', '--version',
    callback=validate_version_arg,
    help='Major version number of the release to start')
@click.pass_obj
def start_release(ctx, version):
    """Start new version branch"""
    apis = ctx.get('apis')
    api = apis.get('mainline')
    try:
        major_version = extract_release_branch_version(version)
        name = build_release_name(ctx['config'], major_version)
        branch = api.create_release_branch(name)
    except GitHubAPI.DuplicateBranchError as e:
        git.fetch('mainline')
        git.checkout(name)
        branch = api.get_branch(name)
        logger.debug('Branch already started')
    except Exception as e:
        sys.exit(e.message)

    try:
        git.fetch('mainline')
        git.checkout(name)
        log = git.log(
            'mainline/master', 'mainline/{}'.format(name), merges=True)
        ticket_ids, changelog = git.changelog(log, ticket_ids=True)

        click.echo('Changelog:')
        click.echo(changelog)

        audit = audit_changes('mainline/master', name)

        logger.info('Creating release ticket')
        jira = apis.get('jira')
        ticket_project = get_config_value(
            ctx.get('config'), 'bugtracker', 'RELEASE_TICKET_PROJECT', 'TEEM')
        ticket_type = get_config_value(
            ctx.get('config'), 'bugtracker', 'RELEASE_TICKET_TYPE', 'RELEASE')
        ticket_id, ticket_name = jira.create_issue(
            summary='Release {}'.format(major_version),
            description='Release changes Audit:\n{{code}}{}{{code}}'.format(audit),
            type=ticket_type, project=ticket_project)
        # link release ticket and changelog tickets
        logger.info('Linking changelog tickets to the release')
        for change_id in ticket_ids:
            logger.debug('Linking {} to {}'.format(change_id, ticket_name))
            try:
                resp = jira.link_issues(change_id, ticket_name)
                logger.debug(
                    'start_release issue link for {} response: {}'.format(
                        change_id, resp
                    )
                )
            except RequestException as e:
                logger.error(
                    'start_release issue link for {} failed with: {}'.format(
                        change_id, e.response.json()
                    )
                )

        if apis.get('slack', None):
            config = ctx.get('config')
            channel_name = slackify_release_name(name)
            logger.info('Creating slack channel: {}'.format(channel_name))

            topic_str = get_config_value(
                config, 'slack', 'TOPIC_STR', 'Release Ticket: {}')
            channel_topic = topic_str.format(ticket_name)
            channel_text = '{}\n```\n{}\n\n{}\n```'.format(
                channel_topic, changelog, audit)
            group_id = get_config_value(
                config, 'slack', 'GROUP_ID', 'S0JT9FNMD')

            create_release_channel(
                apis.get('slack', None), channel_name,
                channel_topic, channel_text, group_id)

        qa(ctx, version, release_ticket_key=ticket_name)

    except Exception as e:
        print(e.message)
        sys.exit(e.message)
    finally:
        click.echo('Branch: {} created'.format(name))
        click.echo(branch.get('url'))
        click.echo('\tgit fetch --all && git checkout {}'.format(name))

        # create pre-release tag
        qa(ctx, version)

    sys.exit()


def audit_changes(base, head, txt=False):
    changes_txt_list, migrations_list = git.get_deploy_relavent_changes(base, head)
    problem_migrations, sql_map = migrations.check_problem_sql(migrations_list)

    sql_msgs = []
    # Print out the SQL for the "non problem" migrations
    for migration, sql in sql_map.iteritems():
        if migration in problem_migrations:
            alert = (
                u'\\033[0;31m{m} could break backwards compatibility\033[0m'
                u'\n{errors}'
                u'\n{sql}'

            ).format(
                m=migration,
                errors=u'\n'.join(problem_migrations[migration]),
                sql=sql)
        else:
            alert = u'{}:\n{}'.format(migration, sql or '\tNOOP')

        sql_msgs.append(alert)

    if not sql_msgs:
        sql_msgs.append('No migrations found.')

    return "{file_changes}\n\nMigrations:\n{sql_changes}".format(
        file_changes='\n'.join(changes_txt_list),
        sql_changes='\n'.join(sql_msgs),
    )


@cli.command()
@click.option(
    '-h', '--head',
    default='',
    help='Name of branch that contains the changes.')
@click.option(
    '-b', '--base',
    default='master',
    help='Name of the branch to compare the history starting from.')
@click.pass_obj
def changelog(ctx, base, head):
    """Get changelog between base branch and head branch"""
    log = git.log(base, head, merges=True)
    logger.debug(log)
    ticket_ids, changelog = git.changelog(log, ticket_ids=True)

    click.echo('\nChangelog:\n{changes}\n\nAuditing...'.format(
        changes=changelog))
    click.echo('\n{audit}'.format(audit=audit_changes(base, head)))


@start.command('hotfix')
@click.option(
    '-t', '--ticket',
    callback=validate_ticket_arg,
    help='ID of ticket reporting the bug to be fixed, slug will be generated')
@click.pass_obj
def start_hotfix(ctx, ticket):
    """Start new hotfix branch"""
    apis = ctx.get('apis')
    api = apis.get('fork')
    jira = apis.get('jira')
    try:
        name = 'hotfix-{}'.format(jira.get_issue_slug(ticket))
        branch = api.create_hotfix_branch(name)
    except GitHubAPI.DuplicateBranchError as e:
        git.fetch('origin')
        git.checkout(name)
        sys.exit('Branch already started')
    except Exception as e:
        sys.exit(e.message)

    click.echo('Branch: {} created'.format(name))
    click.echo(branch.get('url'))
    git.fetch('origin')
    git.checkout(name)
    sys.exit()


@start.command('releasefix')
@click.option(
    '-v', '--version',
    callback=validate_version_arg_or_latest_prerelease,
    help='Major version number of the release to fix')
@click.option(
    '-t', '--ticket',
    callback=validate_ticket_arg,
    help='ID of ticket reporting the bug to be fixed, slug will be generated')
@click.pass_obj
def start_releasefix(ctx, version, ticket):
    """Start new hotfix for a pre-release"""
    apis = ctx.get('apis')
    api = apis.get('mainline')
    fork = apis.get('fork')
    jira = apis.get('jira')

    release_name = build_release_name(
        ctx['config'], extract_release_branch_version(version))
    try:
        base_release_branch = api.get_branch(release_name)
        release_sha = base_release_branch['object']['sha']
    except Exception as e:
        sys.exit(e.message)

    # create or sync the release branch on the fork
    try:
        fork.create_branch(release_name, release_sha, from_sha=True)
    except GitHubAPI.DuplicateBranchError as e:
        fork.update_branch(release_name, release_sha)
    except Exception as e:
        sys.exit(e.message)

    # creak the releasefix branch
    try:
        name = 'releasefix-{}'.format(jira.get_issue_slug(ticket))
        branch = fork.create_releasefix_branch(name, release_name)
    except GitHubAPI.DuplicateBranchError as e:
        git.fetch('origin')
        git.checkout(name)
        sys.exit('Branch already started')
    except Exception as e:
        sys.exit(e.message)

    click.echo('Branch: {} created'.format(name))
    click.echo(branch.get('url'))
    git.fetch('origin')
    git.checkout(name)
    sys.exit()


@start.command('feature')
@click.option(
    '-t', '--ticket',
    callback=validate_ticket_arg,
    help='ID of ticket defining the feature, slug will be generated')
@click.pass_obj
def start_feature(ctx, ticket):
    """Start new feature branch"""
    apis = ctx.get('apis')
    api = apis.get('fork')
    jira = apis.get('jira')
    try:
        name = 'feature-{}'.format(jira.get_issue_slug(ticket))
        branch = api.create_feature_branch(name)
    except GitHubAPI.DuplicateBranchError as e:
        git.fetch('origin')
        git.checkout(name)
        sys.exit('Branch already started')
    except Exception as e:
        sys.exit(e.message)

    click.echo('Branch: {} created'.format(name))
    click.echo(branch.get('url'))
    git.fetch('origin')
    git.checkout(name)
    sys.exit()


@cli.group()
@click.pass_obj
def review(ctx):
    """Create PR to review your code"""
    pass


@review.command('flake8')
@click.option(
    '-b', '--branch',
    default='develop',
    help='Base branch to diff with')
@click.pass_obj
def review_flake8(ctx, branch):
    """Run flake8 on the diff between the current branch the provided base"""
    try:
        issues = python.check_flake8_issues(branch)
    except Exception as e:
        sys.exit(e.message)
    else:
        # note that issues can be the empty string or the list of flake8 issues
        # if it is the empty string, sys.exit will exit with status code 0,
        # since we will pass it the None object.
        sys.exit(issues or None)


@review.command('feature')
@click.option(
    '-t', '--ticket',
    callback=validate_ticket_arg_or_pull_from_branch,
    help='Feature branch / ticket name')
@click.pass_obj
def review_feature(ctx, ticket):
    """Create PR for a feature branch"""
    apis = ctx.get('apis')
    api = apis.get('mainline')
    fork = apis.get('fork')
    jira = apis.get('jira')

    try:
        summary = jira.get_issue_summary(ticket)
        slug = jira.get_issue_slug(ticket, summary)
    except Exception as e:
        sys.exit(e.message)
    else:
        fix_branch = 'feature-{}'.format(slug)

    try:
        name = '{}:{}'.format(fork.owner, fix_branch)
        title = 'Feature {ticket}: {summary}'.format(
            ticket=ticket, summary=summary)
        resp = api.create_pull_request('develop', name, title)
        click.launch(resp.get('html_url'))
        sys.exit()
    except Exception as e:
        sys.exit(e.message)


@review.command('hotfix')
@click.option(
    '-t', '--ticket',
    callback=validate_ticket_arg_or_pull_from_branch,
    help='Hotfix branch / ticket name')
@click.pass_obj
def review_hotfix(ctx, ticket):
    """Create PR for a hotfix branch"""
    apis = ctx.get('apis')
    api = apis.get('mainline')
    fork = apis.get('fork')
    jira = apis.get('jira')

    try:
        summary = jira.get_issue_summary(ticket)
        slug = jira.get_issue_slug(ticket, summary)
    except Exception as e:
        sys.exit(e.message)
    else:
        fix_branch = 'hotfix-{}'.format(slug)

    try:
        name = '{}:{}'.format(fork.owner, fix_branch)
        title = 'Hotfix {ticket}: {summary}'.format(
            ticket=ticket, summary=summary)
        body = git.log_messages('master', fix_branch)
        resp = api.create_pull_request('master', name, title, body)
        click.launch(resp.get('html_url'))
        sys.exit()
    except Exception as e:
        sys.exit(e.message)


@review.command('releasefix')
@click.option(
    '-v', '--version',
    callback=validate_version_arg_or_latest_prerelease,
    help='Major version number of the release to fix')
@click.option(
    '-t', '--ticket',
    callback=validate_ticket_arg_or_pull_from_branch,
    help='Feature branch / ticket name')
@click.pass_obj
def review_releasefix(ctx, ticket, version):
    """Create PR for a release bugfix branch"""
    release_branch = build_release_name(
        ctx['config'],
        extract_release_branch_version(version)
    )
    apis = ctx.get('apis')
    api = apis.get('mainline')
    fork = apis.get('fork')
    jira = apis.get('jira')

    try:
        summary = jira.get_issue_summary(ticket)
        slug = jira.get_issue_slug(ticket, summary)
    except Exception as e:
        sys.exit(e.message)
    else:
        fix_branch = 'releasefix-{}'.format(slug)

    try:
        name = '{}:{}'.format(fork.owner, fix_branch)
        title = 'ReleaseFix {ticket}: {summary}'.format(
            ticket=ticket, summary=summary)
        body = git.log_messages(release_branch, fix_branch)
        resp = api.create_pull_request(release_branch, name, title, body)
        click.launch(resp.get('html_url'))
        sys.exit()
    except Exception as e:
        sys.exit(e.message)


@cli.command('qa')
@click.option(
    '-v', '--version',
    callback=validate_version_arg,
    help='Full version number of the release to QA (pre-release)')
@click.pass_obj
def start_prerelease(ctx, version):
    """Publish pre-release on GitHub for QA."""

    # Try to determine the Jira ticket for this release by looking up
    # the initial release changelog
    base_version = extract_release_branch_version(version)
    apis = ctx.get('apis')
    api = apis.get('mainline')

    try:
        release_ticket_key = api.get_release_ticket_key_for_tag(base_version)
    except Exception:
        release_ticket_key = None

    qa(ctx, version, release_ticket_key=release_ticket_key)


def qa(ctx, version, release_ticket_key=None):
    """Publish pre-release on GitHub for QA."""
    apis = ctx.get('apis')
    api = apis.get('mainline')
    name = build_release_name(
        ctx['config'], extract_release_branch_version(version))

    log = ''
    with git.on_branch(name):
        log = git.log('master', name, merges=True)
        ticket_ids, changelog = git.changelog(log, ticket_ids=True)

        logger.debug('Changelog found:\n{}'.format(changelog))
        changelog = '**Changes:**\n{}'.format(changelog)

        if release_ticket_key is not None:
            # ensure that the github changelog references the JIRA release
            # ticket
            changelog = '{changes}\n\nRelease ticket id: {id}'.format(
                changes=changelog,
                id=release_ticket_key,
            )

            # update the changelog links in jira
            click.echo('Linking changelog tickets to the {} release'.format(
                release_ticket_key)
            )
            jira = apis.get('jira')
            with click.progressbar(ticket_ids) as bar:
                for change_id in bar:
                    logger.debug('Linking {} to {}'.format(
                        change_id, release_ticket_key)
                    )
                    try:
                        resp = jira.link_issues(change_id, release_ticket_key)
                        logger.debug(
                            'qa issue link for {} response: {}'.format(
                                change_id, resp
                            )
                        )
                    except RequestException as e:
                        logger.error(
                            'qa issue link for {} failed with: {}'.format(
                                change_id, e.response.json()
                            )
                        )

    try:
        api.create_pre_release(version, name, body=changelog)
        sys.exit()
    except Exception as e:
        sys.exit(e.message)


@cli.command()
@click.option(
    '-v', '--version',
    callback=validate_version_arg,
    help='Full version number of the release to publish')
@click.pass_obj
def release(ctx, version):
    """Publish release on GitHub"""
    apis = ctx.get('apis')
    api = apis.get('mainline')

    git.fetch('mainline')

    current_release = api.latest_release()

    log = ''
    with git.on_branch('master'):
        log = git.log(current_release.get('tag_name'), 'master', merges=True)
        ticket_ids, changelog = git.changelog(log, ticket_ids=True)

        logger.debug('Changelog found:\n{}'.format(changelog))
        changelog = '**Changes:**\n{}'.format(changelog)

    try:
        api.create_release(
            version,
            build_release_name(
                ctx['config'],
                extract_release_branch_version(version)
            ),
            body=changelog
        )
        sys.exit()
    except Exception as e:
        sys.exit(e.message)


@cli.command()
@click.pass_obj
def versions(ctx):
    """Get the current release and pre-release versions on GitHub"""
    apis = ctx.get('apis')
    api = apis.get('mainline')

    try:
        current_release = api.latest_release()
        click.echo('Release: {}'.format(current_release.get('tag_name')))
    except GitHubAPIError as e:
        msg = 'API Error getting current release version: {}'.format(
            e.message)

        if logger.level <= logging.DEBUG:
            raise
        else:
            sys.exit(msg)

    try:
        current_prerelease = api.latest_prerelease()
        click.echo('Pre-Release: {}'.format(
            current_prerelease.get('tag_name')))
    except GitHubAPIError as e:
        msg = 'API Error getting current pre-release version: {}'.format(
            e.message)
        if logger.level <= logging.DEBUG:
            raise
        else:
            sys.exit(msg)


@cli.command('method')
@click.option(
    '-t', '--target',
    help='Repo to target',
    type=click.Choice(['mainline', 'fork'])
)
@click.option(
    '-m', '--name', 'method_name',
    help='GitHubAPI method to call'
)
@click.option(
    '-a', '--args', 'method_args',
    multiple=True,
    help='GitHubAPI method arguments'
)
@click.pass_obj
def call_method(ctx, target, method_name, method_args):
    """(DEV) Call GitHubAPI directly"""
    apis = ctx.get('apis')
    api = apis.get(target)
    try:
        click.echo(getattr(api, method_name)(*method_args))
        sys.exit()
    except Exception as e:
        sys.exit(e.message)


@cli.command('jira')
@click.option(
    '-m', '--name', 'method_name',
    help='JIRA method to call'
)
@click.option(
    '-a', '--args', 'method_args',
    multiple=True,
    help='JIRA method arguments'
)
@click.pass_obj
def call_jira_method(ctx, method_name, method_args):
    """(DEV) Call JiraAPI mehtod directly"""
    apis = ctx.get('apis')
    jira = apis.get('jira')
    try:
        click.echo(getattr(jira, method_name)(*method_args))
        sys.exit()
    except Exception as e:
        sys.exit(e.message)


if __name__ == '__main__':
    cli()
