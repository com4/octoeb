"""Git repo API wrapper"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import subprocess


class GitError(Exception):
    pass


def fetch(remote_name):
    return subprocess.call(['git', 'fetch', remote_name])


def checkout(branch_name):
    return subprocess.call(['git', 'checkout', branch_name])


def update(base_branch):
    return subprocess.call(['git', 'pull', '-r', base_branch])
