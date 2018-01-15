import json
import twitter

from mastodon import Mastodon

from mtt import config

from mtt.credentials import check_credentials, setup_credentials
from mtt.mastodon_to_twitter import TwitterPublisher
from mtt.twitter_to_mastodon import MastodonPublisher
from mtt.utils import lgt


#
# First step: check credentials
#

if not check_credentials():
    setup_credentials()

lgt('Everything looks good; starting…')


#
# Read in credentials
#

with config.FILES['credentials_twitter'].open('r') as secret_file:
    TWITTER_CONSUMER_KEY = secret_file.readline().rstrip()
    TWITTER_CONSUMER_SECRET = secret_file.readline().rstrip()
    TWITTER_ACCESS_KEY = secret_file.readline().rstrip()
    TWITTER_ACCESS_SECRET = secret_file.readline().rstrip()

with config.FILES['credentials_mastodon_server'].open('r') as secret_file:
    MASTODON_BASE_URL = secret_file.readline().rstrip()


#
# Log in
#

mastodon_api = Mastodon(
    client_id=config.FILES['credentials_mastodon_client'],
    access_token=config.FILES['credentials_mastodon_user'],
    ratelimit_method='wait',
    api_base_url=MASTODON_BASE_URL
)
twitter_api = twitter.Api(
    consumer_key=TWITTER_CONSUMER_KEY,
    consumer_secret=TWITTER_CONSUMER_SECRET,
    access_token_key=TWITTER_ACCESS_KEY,
    access_token_secret=TWITTER_ACCESS_SECRET,
    tweet_mode='extended'  # Allows tweets longer than 140/280 raw characters
)

ma_account_id = mastodon_api.account_verify_credentials()["id"]
tw_account_id = twitter_api.VerifyCredentials().id

#
# Tweets / toots association
#

# Loads tweets/toots associations to be able to mirror threads
# This links the toots and tweets. For links from Mastodon to
# Twitter, the toot listed is the last one of the generated thread
# if the toot is too long to fit into a single tweet.
status_associations = {'m2t': {}, 't2m': {}}
try:
    with open('mtt_status_associations.json', 'r') as f:
        status_associations['m2t'] = json.load(f, object_hook=lambda d: {int(k): v for k, v in d.items()})
        status_associations['t2m'] = {tweet_id: toot_id for toot_id, tweet_id in status_associations['m2t'].items()}
except IOError:
    pass


#
# Sent toots/tweets list
#

# To avoid bouncing toots or tweets, we keep the ID of the status we sent to
# avoid re-sending them indefinitely.
# Unlike status_associations, this contains _every_ status sent including
# intermediate tweets if toots are too long.
sent_status = {'toots': [], 'tweets': []}


#
# Startup
#

if config.POST_ON_TWITTER:
    twitter_publisher = TwitterPublisher(
        name='Mastodon -> Twitter',
        mastodon_api=mastodon_api,
        twitter_api=twitter_api,
        ma_account_id=ma_account_id,
        tw_account_id=tw_account_id,
        status_associations=status_associations,
        sent_status=sent_status
    )

    twitter_publisher.start()

if config.POST_ON_MASTODON:
    mastodon_publisher = MastodonPublisher(
        name='Twitter -> Mastodon',
        mastodon_api=mastodon_api,
        twitter_api=twitter_api,
        ma_account_id=ma_account_id,
        tw_account_id=tw_account_id,
        status_associations=status_associations,
        sent_status=sent_status
    )

    mastodon_publisher.start()


if config.POST_ON_TWITTER:
    twitter_publisher.join()

if config.POST_ON_MASTODON:
    mastodon_publisher.join()
