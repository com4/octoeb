OctoEB
======
![python3](https://caniusepython3.com/check/c87b915f-dfb4-42eb-b0f2-ed5790a049ec.svg?style=flat)

OctoEB is a script to help with the creation of GitHub releases for Eventboard
projects.  This is to help us avoid merge, branch, and tag issues. It also
simplifies the process so that it is executed the same way by each developer
each time.

## Installation
The only external library that this tool depends on is Requests and Click.  
Clone the repo run

    pip install --editable .

To verify the install, start a new shell and run

    octoeb --help


### Configuration
The script looks for the file `.octoebrc` in either the current directory or
your home directory.  You can also place the config in `~/.config/octoeb`.  We
expect this file to contain the following ini-style configuration:


    [repo]
    OWNER=repo-owner
    FORK=fork-repo-owner
    REPO=repo-name
    TOKEN=oauth-token
    USER=email@test.com

    [bugtracker]
    BASE_URL=https://example.atlassian.net
    USER=email@example.com
    TOKEN=pwd
    TICKET_FILTER_ID=123

In `repo`

1. OWNER and REPO are https://github.com/OWNER/REPO when you visit a repo on
   GitHub, so for example https://github.com/enderlabs/eventboard.io gives
   OWNER=enderlabs and REPO=eventboard.io
2. The token can be obtained from https://github.com/settings/tokens
3. USER is your login email for GitHub

In `bugtracker`

1. USER is your login email for JIRA`
2. TOKEN is your JIRA password
3. TICKET_FILTER_ID is the search filter used for tab completion of ticket ids

### Usage
There are three major command `start`, `qa`, and `release`. Enter

    $ octoeb start --help
    $ octoeb start hotfix --help
    $ octoeb start release --help
    $ octoeb qa --help
    $ octoeb release --help

respectively for usage details.

### Tab Completion
To add tab completion in `bash` simply add

    source /path/to/octoeb/completion.sh

to your `bashrc`.

If you are running `zsh`, then you must also add

    autoload -U +X bashcompinit && bashcompinit

to the beginning of your `zshrc`.


## Developing
Clone, install as above,

    pip install --editable .

Start coding!  Your changes will take immediate effect. 

Author: Lucas Roesler <lucas@eventboard.io>
