from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import logging


logger = logging.getLogger(__name__)


def create_release_channel(slack, name, topic, text, group_id=None):
    """Create a release channel in slack.

    If slacker is installed, and you have the token in your config, create a
    release channel and invite interested parties.

    Args:
        slack (slacker.Slacker): Slack api
        name (str): The name of the channel
        topic (str): The channel topic
        text (str): Text to post in the channel
        group_id (str): The group ID containing the list of users you want to
            invite to the newly created release channel.
    """

    resp = slack.channels.join(name)
    channel_id = resp.body['channel']['id']
    slack.channels.set_topic(channel=channel_id, topic=topic)

    if group_id:
        resp = slack.usergroups.users.list(group_id)
        for user_id in resp.body['users']:
            try:
                slack.channels.invite(channel_id, user_id)
            except Exception:
                logger.exception('Filted to invite users to the slack channel')

    slack.chat.post_message(name, text)
