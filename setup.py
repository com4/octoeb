from __future__ import absolute_import
from setuptools import find_packages
from setuptools import setup


setup(
    name='octoeb',
    version='1.4.3',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click>=7.0',
        'flake8>=3.7.9',
        'python-slugify>=4.0.0',
        'requests>=2.22.0',
        'six>=1.14.0',
        'slacker>=0.14.0',
    ],
    entry_points={
        'console_scripts': [
            'octoeb=octoeb.cli:cli'
        ]
    },
)
