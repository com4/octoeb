OctoEB
======

OctoEB is a script to help with the creation of GitHub releases for Eventboard
projects.  This is to help us avoid merge, branch, and tag issues. It also
simplifies the process so that it is executed the same way by each developer
each time.

## Installation
The only external library that this tool depends on is Requests.  Clone the
repo run

    pip install -r requirements

Run

    ./install.sh

To verify the install, start a new shell and run

    octoeb -h


## Configuration
The script looks for the file `.octoebrc` in either
your home directory or the current directory.  We expect this file to
contain the following ini-style configuration:


    [repo]
    OWNER=repo-owner
    REPO=repo-name
    TOKEN=oauth-token
    USER=email@test.com


1. OWNER and REPO are https://github.com/OWNER/REPO when you vist a repo on
   GitHub, so for example https://github.com/enderlabs/eventboard.io gives
   OWNER=enderlabs and REPO=eventboard.io
2. The token can be obtained from https://github.com/settings/tokens
3. USER is your login email for GitHub


## Usage
There are three major command `start`, `qa`, and `release`. Enter

    $ octoeb start -h
    $ octoeb qa -h
    $ octoeb release -h

respectively for usage details.


Author: Lucas Roesler <lucas@eventboard.io>
