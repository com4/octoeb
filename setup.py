from setuptools import setup

setup(
    name='octoeb',
    version='1.0',
    packages=['octoeb', 'octoeb.utils', ],
    include_package_data=True,
    install_requires=[
        'click',
        'requests',
    ],
    entry_points={
        'console_scripts': [
            'octoeb=octoeb.cli:cli'
        ]
    },
)
