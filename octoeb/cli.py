#! /usr/bin/env python
"""
Author: Lucas Roesler <lucas@eventboard.io>

OctoEB is a script to help with the creation of GitHub releases for Eventboard
projects.  This is to help us avoid merge, branch, and tag issues. It also
simplifies the process so that it is executed the same way by each developer
each time.

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
   GitHub, so for example https://github.com/enderlabs/eventboard.io gives
   OWNER=enderlabs and REPO=eventboard.io
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
import ConfigParser
import logging
import re
import sys

import click


from octoeb.utils.formatting import extract_major_version
from octoeb.utils.formatting import validate_config
from octoeb.utils.GitHubAPI import GitHubAPI


logger = logging.getLogger(__name__)
# Allow commands to access the api object via the clikc ctx
pass_api = click.make_pass_decorator(GitHubAPI)
# use to allow -h for for help
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


def set_logging(ctx, param, level):
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise click.BadParameter('Invalid log level: {}'.format(level))

    logging.basicConfig(level=numeric_level)


def validate_version_arg(ctx, param, version):
    if version is None:
        raise click.BadParameter('Version number is required')

    if re.match(r'^(?:\.?\d+){4,5}$', version):
        return version

    raise click.BadParameter('Invalid versom format: {}'.format(version))


def validate_ticket_arg(ctx, param, name):
    if name is None:
        raise click.BadParameter('Ticket number is required')

    if re.match(r'^EB-\d+(?:-.+)?$', name):
        return name

    raise click.BadParameter('Invalid ticket format {}'.format(name))


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    '--log',
    default='ERROR', help='Set the log level',
    expose_value=False,
    callback=set_logging,
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']))
@click.version_option('1.2')
@click.pass_context
def cli(ctx):
    """Eventboard releases script"""
    # Setup the API
    config = ConfigParser.ConfigParser()
    config.read(['.octoebrc', '~/.config/octoeb', '~/.octoebrc'])

    try:
        validate_config(config)
    except Exception as e:
        sys.exit('ERROR: {}'.format(e.message))

    ctx.obj = {
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
    }


@cli.group()
@click.pass_obj
def start(apis):
    """Start new branch for a fix, feature, or a new release"""
    pass


@start.command('release')
@click.option(
    '-v', '--version',
    callback=validate_version_arg,
    help='Major version number of the release to start')
@click.pass_obj
def start_release(apis, version):
    """Start new version branch"""
    api = apis.get('mainline')
    try:
        name = 'release-{}'.format(extract_major_version(version))
        branch = api.create_release_branch(name)
    except Exception as e:
        sys.exit(e.message)

    click.echo('Branch: {} created'.format(name))
    click.echo(branch.get('url'))
    click.echo('\tgit fetch --all && git checkout {}'.format(name))
    sys.exit()


@start.command('hotfix')
@click.option(
    '-t', '--ticket',
    callback=validate_ticket_arg,
    help='Name of ticket reporting the bug to be fixed')
@click.pass_obj
def start_hotfix(apis, ticket):
    """Start new hotfix branch"""
    api = apis.get('fork')
    try:
        name = 'hotfix-{}'.format(extract_major_version(ticket))
        branch = api.create_hotfix_branch(name)
    except Exception as e:
        sys.exit(e.message)

    click.echo('Branch: {} created'.format(name))
    click.echo(branch.get('url'))
    click.echo('\tgit fetch --all && git checkout {}'.format(name))
    sys.exit()


@start.command('releasefix')
@click.option(
    '-v', '--version',
    callback=validate_version_arg,
    help='Major version number of the release to fix')
@click.option(
    '-t', '--ticket',
    callback=validate_ticket_arg,
    help='Name of ticket reporting the bug to be fixed')
@click.pass_obj
def start_releasefix(apis, version, ticket):
    """Start new hotfix for a pre-release"""
    api = apis.get('fork')
    try:
        name = 'releasefix-{}'.format(extract_major_version(ticket))
        branch = api.create_hotfix_branch(
            name,
            'release-{}'.format(extract_major_version(version))
        )
    except Exception as e:
        sys.exit(e.message)

    click.echo('Branch: {} created'.format(name))
    click.echo(branch.get('url'))
    click.echo('\tgit fetch --all && git checkout {}'.format(name))
    sys.exit()


@start.command('feature')
@click.option(
    '-t', '--ticket',
    callback=validate_ticket_arg,
    help='Name of ticket reporting the feature to implement')
@click.pass_obj
def start_feature(apis, ticket):
    """Start new feature branch"""
    api = apis.get('fork')
    name = 'feature-{}'.format(ticket)
    try:
        branch = api.create_feature_branch(name)
    except Exception as e:
        sys.exit(e.message)

    click.echo('Branch: {} created'.format(name))
    click.echo(branch.get('url'))
    click.echo('\tgit fetch --all && git checkout {}'.format(name))
    sys.exit()


@cli.command()
@click.option(
    '-v', '--version',
    callback=validate_version_arg,
    help='Full version number of the release to QA (pre-release)')
@click.pass_obj
def qa(apis, version):
    """Publish pre-release on GitHub for QA"""
    api = apis.get('mainline')
    try:
        api.create_pre_release(version)
        sys.exit()
    except Exception as e:
        sys.exit(e.message)


@cli.command()
@click.option(
    '-v', '--version',
    callback=validate_version_arg,
    help='Full version number of the release to publish')
@click.pass_obj
def release(apis, version):
    """Publish release on GitHub"""
    api = apis.get('mainline')
    try:
        api.create_release(version)
        sys.exit()
    except Exception as e:
        sys.exit(e.message)


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
def call_method(apis, target, method_name, method_args):
    """Call GitHubAPI directly"""
    api = apis.get(target)
    try:
        click.echo(getattr(api, method_name)(*method_args))
        sys.exit()
    except Exception as e:
        sys.exit(e.message)


if __name__ == '__main__':
    cli()
