from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import re

from octoeb.utils.config import get_config_value


logger = logging.getLogger(__name__)


def build_release_base_name(config):
    parts = (
        get_config_value(config, 'release', 'PREFIX', None),
        get_config_value(config, 'release', 'MAIN', 'release'),
    )
    return '-'.join((x for x in parts if x))


def build_release_name(config, version):
    parts = (
        build_release_base_name(config),
        version,
    )
    return '-'.join((x for x in parts if x))


def slackify_release_name(release_name):
    return release_name.replace('.', '-')


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


def validate_ticket_name(name):
    if re.match(r'^EB-\d+(?:-.+)?$', name):
        return True

    raise Exception('Invalid ticket format {}'.format(name))


def validate_version(version):
    if re.match(r'^(?:\.?\d+){4,5}$', version):
        return True

    raise Exception('Invalid version number {}'.format(version))
