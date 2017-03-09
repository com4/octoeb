from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import re


logger = logging.getLogger(__name__)


def extract_major_version(version):
    return '.'.join(version.split('.')[:4])


def extract_year_week_version(version):
    if version.startswith('0'):
        return '.'.join(version.split('.')[2:4])

    else:
        return '.'.join(version.split('.')[:2])


def extract_release_branch_version(version):
    version_nums = version.split('.')[:4]
    version_nums[-1] = '01'

    return '.'.join(version_nums)


def validate_config(config):
    assert config.has_section('repo'), 'Missing repo config'
    assert config.has_option('repo', 'USER'), 'Missing USER name in config'
    assert config.has_option('repo', 'TOKEN'), 'Missing TOKEN in config'
    assert config.has_option('repo', 'REPO'), 'Missing REPO name in config'
    assert config.has_option('repo', 'FORK'), 'Missing FORK name in config'
    assert config.has_option('repo', 'OWNER'), \
        'Missing mainline OWNER name in config'
    assert config.has_section('bugtracker'), 'Missing bugtracker section'


def validate_ticket_name(name):
    if re.match(r'^EB-\d+(?:-.+)?$', name):
        return True

    raise Exception('Invalid ticket format {}'.format(name))


def validate_version(version):
    if re.match(r'^(?:\.?\d+){4,5}$', version):
        return True

    raise Exception('Invalid version number {}'.format(version))
