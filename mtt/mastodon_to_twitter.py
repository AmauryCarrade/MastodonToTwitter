import html
import re
import time

from mastodon import StreamListener
from twitter import TwitterError
from urllib.parse import urlparse

from mtt import config, lock
from mtt.utils import MTTThread, lgt, split_status


class TwitterPublisher(MTTThread):
    def __init__(self, mastodon_api, twitter_api, ma_account_id, tw_account_id,
                 status_associations, sent_status, group=None, target=None, name=None):
        super(TwitterPublisher, self).__init__(
            group=group,
            target=target,
            name=name,
            mastodon_api=mastodon_api,
            twitter_api=twitter_api,
            ma_account_id=ma_account_id,
            tw_account_id=tw_account_id,
            status_associations=status_associations,
            sent_status=sent_status
        )

        self.account = mastodon_api.account(ma_account_id)

        self.since_toot_id = 0
        self.url_length = 24
        self.last_url_len_update = 0

        self.MEDIA_REGEXP = re.compile(re.escape(self.mastodon_api.api_base_url.rstrip("/")) + "\/media\/(\w)+(\s|$)+")

    def init_process(self):
        try:
            self.since_toot_id = self.mastodon_api.account_statuses(self.ma_account_id)[0]["id"]
            lgt(f'Tweeting any toot after toot {self.since_toot_id}')
        except IndexError:
            lgt('Tweeting any toot (user timeline is empty right now)')

        self.update_twitter_link_length()

    def update_twitter_link_length(self):
        if time.time() - self.last_url_len_update > 60 * 60 * 24:
            self.twitter_api._config = None
            self.url_length = max(self.twitter_api.GetShortUrlLength(False),
                                  self.twitter_api.GetShortUrlLength(True)) + 1
            self.last_url_len_update = time.time()
            lgt(f'Updated expected short URL length - it is now {self.url_length} characters.')

    @staticmethod
    def _are_same_accounts(first, other):
        """
        Checks if the two accounts are the same, i.e.
        - with the same ID;
        - from the same instance.
        :param first: An account (dict-like with at least an 'id' and an 'url' key).
        :param other: Another account (same).
        :return: True if both are the same.
        """
        if first['id'] != other['id']:
            return False

        # In case the ID is the same we check the instance
        # (we don't want to check only the profile URL as
        # it would break the sync if the username is changed)
        if '@' in first['url'] and '@' in other['url']:
            return first['url'].split('@')[0] == other['url'].split('@')[0]
        else:
            return first['url'] == other['url']

    def is_from_us(self, account):
        return self._are_same_accounts(self.account, account)

    def run(self):
        self.init_process()

        lgt('Listening for toots…')

        class TootsListener(StreamListener):
            def __init__(self, publisher):
                self.publisher = publisher

            def on_update(self, toot):
                # We only transfer our own toots, but the streaming endpoint receives the whole
                # timeline.
                if not self.publisher.is_from_us(toot['account']):
                    return

                # Avoids a race condition.
                # We wait a little bit so tweets sent to Mastodon
                # can be marked as such before this run, avoiding
                # bouncing tweets/toots.
                time.sleep(config.STATUS_PROCESS_DELAY)

                toot_id = toot["id"]

                if self.publisher.is_toot_sent_by_us(toot_id):
                    return

                if toot['visibility'] not in config.TOOT_VISIBILITY_REQUIRED_TO_TRANSFER:
                    lgt(f'Skipping toot {toot["id"]} - invalid visibility ({toot["visibility"]})')
                    return

                content = toot["content"]
                media_attachments = toot["media_attachments"]

                if toot['reblogged'] and 'reblog' in toot:
                    reblog = toot['reblog']
                    reblog_name = f'@{reblog["account"]["username"]}@{urlparse(reblog["account"]["url"]).netloc}'
                    content = f'\U0001f501 RT {reblog_name}\n' \
                              f'{reblog["content"]}\n\n' \
                              f'{reblog["url"]}'
                    media_attachments = reblog["media_attachments"]

                    toot = reblog

                # We trust mastodon to return valid HTML
                content_clean = re.sub(r'<a [^>]*href="([^"]+)">[^<]*</a>', '\g<1>', content)

                # We replace html br with new lines
                content_clean = "\n".join(re.compile(r'<br ?/?>', re.IGNORECASE).split(content_clean))
                # We must also replace new paragraphs with double line skips
                content_clean = "\n\n".join(re.compile(r'</p><p>', re.IGNORECASE).split(content_clean))
                # Then we can delete the other html contents and unescape the string
                content_clean = html.unescape(str(re.compile(r'<.*?>').sub("", content_clean).strip()))
                # Trim out media URLs
                content_clean = re.sub(self.publisher.MEDIA_REGEXP, "", content_clean)

                # Don't cross-post replies
                if len(content_clean) != 0 and content_clean[0] == '@':
                    lgt('Skipping toot "' + content_clean + '" - is a reply.')
                    return

                if config.TWEET_CW_PREFIX and toot['spoiler_text']:
                    content_clean = config.TWEET_CW_PREFIX.format(toot['spoiler_text']) + content_clean

                content_parts = split_status(
                    status=content_clean,
                    max_length=280,
                    split=config.SPLIT_ON_TWITTER,
                    url=toot['uri']
                )

                # Tweet all the parts. On error, give up and go on with the next toot.
                try:
                    reply_to = None

                    # We check if this toot is a reply to a previously sent toot.
                    # If so, the first corresponding tweet will be a reply to
                    # the stored tweet.
                    # Unlike in the Mastodon API calls, we don't have to handle the
                    # case where the tweet was deleted, as twitter will ignore
                    # the in_reply_to_status_id option if the given tweet
                    # does not exists.
                    if toot['in_reply_to_id'] in self.publisher.status_associations['m2t']:
                        reply_to = self.publisher.status_associations['m2t'][toot['in_reply_to_id']]

                    for i in range(len(content_parts)):
                        media_ids = []
                        content_tweet = content_parts[i]

                        # Last content part: Upload media, no -- at the end
                        if i == len(content_parts) - 1:
                            for attachment in media_attachments:
                                media_ids.append(self.publisher.transfer_media(
                                    media_url=attachment["url"],
                                    to='twitter'
                                ))

                            content_tweet = content_parts[i]

                        # Some final cleaning
                        content_tweet = content_tweet.strip()

                        # Retry three times before giving up
                        retry_counter = 0
                        post_success = False

                        lgt(f'Sending tweet "{content_tweet}"…')

                        while not post_success:
                            try:
                                if len(media_ids) == 0:
                                    reply_to = self.publisher.twitter_api.PostUpdate(
                                        content_tweet,
                                        in_reply_to_status_id=reply_to
                                    ).id

                                    self.publisher.mark_tweet_sent(reply_to)
                                    since_tweet_id = reply_to
                                    post_success = True

                                else:
                                    reply_to = self.publisher.twitter_api.PostUpdate(
                                        content_tweet,
                                        media=media_ids,
                                        in_reply_to_status_id=reply_to
                                    ).id

                                    self.publisher.mark_tweet_sent(reply_to)
                                    since_tweet_id = reply_to
                                    post_success = True

                            except TwitterError:
                                if retry_counter < config.MASTODON_RETRIES:
                                    retry_counter += 1
                                    time.sleep(config.MASTODON_RETRY_DELAY)
                                else:
                                    raise

                        lgt('Tweet sent successfully.')

                        # Only the last tweet is linked to the toot, see comment
                        # above the status_associations declaration
                        if i == len(content_parts) - 1:
                            with lock:
                                self.publisher.associate_status(toot_id, since_tweet_id)
                                self.publisher.save_status_associations()

                except Exception as e:
                    lgt("Encountered error after " + str(config.MASTODON_RETRIES) + " retries. Not retrying.")
                    print(e)

                # From times to times we update the Twitter URL length.
                self.publisher.update_twitter_link_length()

        # Compatibility with multiple versions of Mastodon.py
        try:
            self.mastodon_api.stream_user(TootsListener(self), run_async=False)
        except AttributeError:
            self.mastodon_api.user_stream(TootsListener(self), run_async=False)
