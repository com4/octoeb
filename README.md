OctoEB
======
![python3](https://caniusepython3.com/check/c87b915f-dfb4-42eb-b0f2-ed5790a049ec.svg?style=flat)

OctoEB is a script to help with the integration of Gitflow, Github, and Jira.
This is to help us avoid merge, branch, and tag issues. It also
simplifies the process so that it is executed the same way by each developer
each time.


The goal is to make this git branching strategy as semantic as possible on the commandline

![Teem Git Flow](https://s3-us-west-2.amazonaws.com/eventboard-docs/Teem+GitFlow+-+Page+1.png)

## Installation
The only external libraries that this tool depends on is Requests and Click.
Clone the repo and run

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

    [slack]
    TOKEN=xoxp-2343453243234-23423-234-aefeafaefaef
    GROUP_ID=S1JT6FNQR
    TOPIC_STR=Release ticket at https://example.atlassian.net/browse/{}

    [release]
    PREFIX=Boaty
    MAIN=McBoatFace

In `repo`

1. OWNER and REPO are https://github.com/OWNER/REPO when you visit a repo on
   GitHub, so for example https://github.com/enderlabs/octoeb gives
   OWNER=enderlabs and REPO=octoeb
2. The token can be obtained from https://github.com/settings/tokens
3. USER is your login email for GitHub

In `bugtracker`

1. USER is your login email for JIRA`
2. TOKEN is your JIRA password
3. TICKET_FILTER_ID is the search filter used for tab completion of ticket ids
4. RELEASE_TICKET_PROJECT is the project the release ticket should be created
   in.  Default is `MAN`
5. RELEASE_TICKET_TYPE is the type of ticket to use.  Default is `RELEASE`

In `slack`

Requires that you have the `slacker` python package installed.  If you do not,
a slack channel will not be created.

1. API_TOKEN is your slack API token. Obtain a token here:
   https://api.slack.com/custom-integrations/legacy-tokens
2. GROUP_ID indicated the group that will automatically be added to the
   release channel that is created.

In `release`

This section is optional, but allows you to control the release branch and
channel names, these names will match `prefix-main-version` and
`prefix_main_version` respectively per the configuration in this section.
By default, the prefix is empty and releases will be named, e.g.
`release-1.1.01`.

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
