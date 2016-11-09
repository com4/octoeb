from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import logging
import re
import subprocess

logger = logging.getLogger(__name__)

not_null_finder = re.compile(r'NOT NULL', re.M)
drop_col_finder = re.compile(r'DROP COLUMN', re.M)
add_with_default_finder = re.compile(r'ADD COLUMN .* DEFAULT', re.M)
issue_re = re.compile(
    r'merge pull request #\d+ from .*(?:[/-]([a-z]+-\d+))', re.I)
changelog_re = re.compile(
    r'merge pull request #\d+ from .*(?:[/-]([a-z]{2,4}-\d+)-(.*))', re.I)
migrations_info_re = re.compile(
    r'apps/((.*)/migrations/(\d+[0-9a-z_]*))\.py', re.I)


def check_for_not_null(sql):
    """Check if a column does not allow NULL

    Non-nullable fields are not backwards compatiable with previous
    of the code base.  We can not allow a column to be added that is
    NOT NULL in a single deploy.  If a column is marked as NOT NULL,
    then the column must be added as NULL in a previous DEPLOY.

    Check if the column is also added in this deploy.
    """
    if not_null_finder.search(sql):
        return u'- contains NOT NULL columns'

    return None


def check_for_dropped_columns(sql):
    """Check if a column is removed.

    Removing a column must be done very carefully and we  must verify
    that it is not still referenced in the code.
    """
    if drop_col_finder.search(sql):
        return u'- drops columns'

    return None


def check_for_add_with_default(sql):
    """Check if a new column has a default

    When adding columns, adding a default causes a table re-write and can
    lock or deadlock. Columns that require a default should be added in several
    steps

    1) as nullable
    2) add the default
    3) backfill the default
    """
    if add_with_default_finder.search(sql):
        return u'- adds a new column with DEFAULT'

    return None


SQL_BACKWARDS_COMPATIBILITY_CHECKS = [
    check_for_not_null,
    check_for_dropped_columns,
    check_for_add_with_default,
]


def check_problem_sql(migrations_list):
    with open('/dev/null', 'w') as devnull:
        sql_map = {}

        for x in migrations_list:
            match = migrations_info_re.search(x, re.I)

            if match:
                _, app, name = match.groups()
            else:
                logger.debug('Could not find migration info in {}'.format(x))
                continue

            try:
                cmd = ('./do', 'manage', 'sqlmigrate', app, name)
                # dump the error/logging output to null
                sql = subprocess.check_output(cmd, stderr=devnull)
            except subprocess.CalledProcessError:
                logger.debug('Error trying to run: {}'.format(cmd))
                continue
            else:
                sql_map[x] = sql

    problem_migrations = {}
    for migration, sql in sql_map.iteritems():
        # check for problem migrations by applying each backwards compatibility
        # check
        errors = []
        for fnc in SQL_BACKWARDS_COMPATIBILITY_CHECKS:
            result = fnc(sql)
            if result is not None:
                errors.append(result)

        if any(errors):
            problem_migrations[migration] = errors

    return problem_migrations, sql_map
