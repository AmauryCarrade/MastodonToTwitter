#
# This is the MastodonToTwitter corssposter configuration file.
# You can configure the behavior of the crossposter here.
#
# Credentials are not stored here. To setup credentials, run the
# program once—they will be prompted at the first run. To update
# credentials, remove all *.secret files and run the program.
#

import os
import re
import twitter
import warnings

from path import Path

# Secrets can go in a config/ directory (so they can be mounted inside a
# docker image), or can go in the root of git repository (so we don't
# break things for existing users)
_PARENT_DIR = Path(os.path.dirname(os.path.realpath(__file__))).parent
if (ROOT_PATH / 'mtt_mastodon_server.secret').exists():
    warnings.warn(
        'Using config from the base of the git repository, but '
        'you might like to move this to a config/ subdirectory')
    ROOT_PATH = _PARENT_DIR
else:
    ROOT_PATH = _PARENT_DIR / 'config'

# Enable repost on services
POST_ON_MASTODON = True
POST_ON_TWITTER = True

# Should we slice long messages from Mastodon on Twitter, or cut them
SPLIT_ON_TWITTER = True

# If true and a toot needs to be split on Twitter, and if this toot starts with or ends with one or more hashtags,
# these hashtags will be added to every tweet posted and not only the first/last one.
DISTRIBUTE_HASHTAGS_ON_TWITTER = True

# Manage visibility of your toot. Value are "private", "unlisted" or "public"
TOOT_VISIBILITY = "public"

# Toots with the visibilities listed here will be transferred to Twitter, and only
# them. Possible values: 'public', 'unlisted', 'private', 'direct'.
# /!\ ADDING 'direct' HERE WILL TRANSFER ALL PRIVATE DIRECT MESSAGES TO TWITTER PUBLICLY.
TOOT_VISIBILITY_REQUIRED_TO_TRANSFER = ['public', 'unlisted']

# How often to retry when posting fails
MASTODON_RETRIES = 3
TWITTER_RETRIES = 3

# How long to wait between retries, in seconds
MASTODON_RETRY_DELAY = 20
TWITTER_RETRY_DELAY = 20

# The text to prepend to tweets, if the corresponding toot has a
# content warning. {} is the spoiler text.
# To disable content warnings from Mastodon to Twitter, set to None.
TWEET_CW_PREFIX = '[TW ⋅ {}]\n\n'

# The regex to match against tweet to extract a content warning.
# The CW spoiler text should be in the first capture group.
# The matching parts of the tweets will be removed and the CW found
# in the capture group #1 will be displayed as a CW in Mastodon.
# If multiple CW are found into the tweet, all will be added, separated
# by the separator below, in the Mastodon CW, and all will be removed from
# the original tweet. Except if TWEET_CW_ALLOW_MULTI is set to False, then
# only the first one will be considered.
# To disable content warnings from Twitter to Mastodon, set to None.
TWEET_CW_REGEXP = re.compile(r'(?:[\[(])(?:(?:(?:C|T)W)|SPOIL(?:ER)?)(?:[\s\-\.⋅,:–—]+)([^\]]+)(?:[\])])', re.IGNORECASE)  # noqa
TWEET_CW_ALLOW_MULTI = True
TWEET_CW_SEPARATOR = ', '

# Some helpers copied out from python-twitter, because they're broken there
URL_REGEXP = re.compile((
    r'('
    r'(?!(https?://|www\.)?\.|ftps?://|([0-9]+\.){{1,3}}\d+)'  # exclude urls that start with "."
    r'(?:https?://|www\.)*(?!.*@)(?:[\w+-_]+[.])'              # beginning of url
    r'(?:{0}\b|'                                               # all tlds
    r'(?:[:0-9]))'                                             # port numbers & close off TLDs
    r'(?:[\w+\/]?[a-z0-9!\*\'\(\);:&=\+\$/%#\[\]\-_\.,~?])*'   # path/query params
    r')').format(r'\b|'.join(twitter.twitter_utils.TLDS)), re.U | re.I | re.X)

# The files where credentials and other data are stored
FILES = {
    'credentials_twitter': ROOT_PATH / 'mtt_twitter.secret',
    'credentials_mastodon_client': ROOT_PATH / 'mtt_mastodon_client.secret',
    'credentials_mastodon_server': ROOT_PATH / 'mtt_mastodon_server.secret',
    'credentials_mastodon_user': ROOT_PATH / 'mtt_mastodon_user.secret',
    'status_associations': ROOT_PATH / 'mtt_status_associations.json'
}

# The delay to wait before a tweet or a toot is processed (seconds).
# This avoids race conditions.
# We wait a little bit so tweets sent to Mastodon (or the other way
# around) can be marked as such before this run, avoiding bouncing
# tweets/toots
STATUS_PROCESS_DELAY = 0.6
