from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import sys

try:
    import six.moves.configparser
except ImportError:
    import configparser as ConfigParser


logger = logging.getLogger(__name__)
CACHE = {}


def get_config(validate=True):
    """Read octoeb configs.

    Returns
        ConfigParser config object.
    """
    logger.debug('Get config')

    cached_config = CACHE.get('config')
    if cached_config:
        logger.debug('Config from cache')
        return cached_config

    config = six.moves.configparser.ConfigParser()
    config.read([
        os.path.expanduser('~/.config/octoeb'),
        os.path.expanduser('~/.octoebrc'),
        '.octoebrc'
    ])

    if not validate:
        return config

    try:
        validate_config(config)
    except Exception as e:
        sys.exit('ERROR: {}'.format(e.message))

    CACHE['config'] = config

    return config


def get_config_value(config, section, option, default=None):
    """Provide a getter for configparser that supports a default.

    ConfigParser should have had this from the get go.

    Args:
        config (ConfigParser): The ``ConfigParser``
        section (str): The section the setting is in
        option (str): The name of the option
        default (object): The optional default.
    """
    logger.debug('Get config value: {s}; {o}, {d}'.format(
        s=section, o=option, d=default))
    try:
        return config.get(section, option)
    except (six.moves.configparser.NoSectionError, six.moves.configparser.NoOptionError):
        logger.debug('Return default value')
        return default


def validate_config(config):
    assert config.has_section('repo'), 'Missing repo config'
    assert config.has_option('repo', 'USER'), 'Missing USER name in config'
    assert config.has_option('repo', 'TOKEN'), 'Missing TOKEN in config'
    assert config.has_option('repo', 'REPO'), 'Missing REPO name in config'
    assert config.has_option('repo', 'FORK'), 'Missing FORK name in config'
    assert config.has_option('repo', 'OWNER'), \
        'Missing mainline OWNER name in config'
    assert config.has_section('bugtracker'), 'Missing bugtracker section'
