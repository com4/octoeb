"""Git repo API wrapper"""
import subprocess


def fetch(remote_name):
    return subprocess.call(['git', 'fetch', remote_name])


def checkout(branch_name):
    return subprocess.call(['git', 'checkout', branch_name])


def update(base_branch):
    return subprocess.call(['git', 'pull', '-r', base_branch])
