import html
import re
import time

from mastodon.Mastodon import MastodonError, MastodonAPIError

from mtt import config, lock
from mtt.utils import MTTThread, lgt


class MastodonPublisher(MTTThread):
    def __init__(self, mastodon_api, twitter_api, ma_account_id, tw_account_id,
                 status_associations, sent_status, group=None, target=None, name=None):
        super(MastodonPublisher, self).__init__(
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

        self.since_tweet_id = 0

    def init_process(self):
        try:
            self.since_tweet_id = self.twitter_api.GetUserTimeline()[0].id
            lgt('Tooting any tweet after tweet {}'.format(self.since_tweet_id))
        except IndexError:
            lgt('Tooting any tweet (user timeline is empty right now)')

    @staticmethod
    def _get_tweet_full_text(tweet):
        if 'extended_tweet' in tweet:
            if 'full_text' in tweet['extended_tweet']:
                return tweet['extended_tweet']['full_text']
            elif 'text' in tweet['extended_tweet']:
                return tweet['extended_tweet']['text']
        elif 'full_text' in tweet:
            return tweet['full_text']
        elif 'text' in tweet:
            return tweet['text']
        else:
            return ''

    def run(self):
        self.init_process()

        lgt('Listening for tweets…')

        for tweet in self.twitter_api.GetUserStream():
            if 'text' not in tweet and 'full_text' not in tweet:
                continue

            # Avoids a race condition.
            # We wait a little bit so toots sent to Twitter
            # can be marked as such before this run, avoiding
            # bouncing tweets/toots.
            time.sleep(config.STATUS_PROCESS_DELAY)

            tweet_id = tweet['id']

            if self.is_tweet_sent_by_us(tweet_id):
                continue

            is_retweet = False

            content = MastodonPublisher._get_tweet_full_text(tweet)

            if 'retweeted_status' in tweet:
                rt = tweet['retweeted_status']
                rt_content = MastodonPublisher._get_tweet_full_text(rt)

                content = f'\U0001f501 RT @{rt["user"]["screen_name"]}\n\n' \
                          f'{rt_content}\n\n' \
                          f'https://twitter.com/{rt["user"]["screen_name"]}/status/{rt["id_str"]}'

                tweet = rt
                is_retweet = True

            reply_to = None

            with lock:
                if 'in_reply_to_user_id' in tweet and 'in_reply_to_status_id' in tweet and tweet['in_reply_to_user_id']:
                    # If it's a reply, we keep the tweet if:
                    # 1. it's a reply from us (in a thread);
                    # 2. it's a reply from a previously transmitted tweet, so we don't sync
                    #    if someone replies to someone in two or more tweets (because in this
                    #    case the 2nd tweet and the ones after are replying to us);
                    # 3. it's a reply from another one but we retweeted it.

                    # If it's not a tweet in reply to us
                    if ((tweet['in_reply_to_user_id'] != self.tw_account_id
                         # or if it's a reply to us but not in our threads association
                         or tweet['in_reply_to_status_id'] not in self.status_associations['t2m'])
                        # or if it's a tweet from us but not a retweet
                       and not is_retweet):

                        # ... in all these cases, we don't want to transfer the tweet.
                        lgt(f'Skipping tweet {tweet_id} - it\'s a reply.')
                        continue

                    # A tweet can be a reply without previous tweet if we directly mentioned someone
                    # (starting the tweet with the mention).
                    if tweet['in_reply_to_status_id'] is not None:
                        reply_to = self.status_associations['t2m'].get(tweet['in_reply_to_status_id'])

            media_attachments = (tweet['media'] if 'media' in tweet
                                 else tweet['entities']['media'] if 'entities' in tweet and 'media' in tweet['entities']
                                 else tweet['extended_tweet']['entities']['media']
                                     if 'extended_tweet' in tweet and 'entities' in tweet['extended_tweet']
                                     and 'media' in tweet['extended_tweet']['entities']
                                 else [])

            urls = (tweet['urls'] if 'urls' in tweet
                    else tweet['entities']['urls'] if 'entities' in tweet and 'urls' in tweet['entities']
                    else tweet['extended_tweet']['entities']['urls']
                        if 'extended_tweet' in tweet and 'entities' in tweet['extended_tweet']
                        and 'urls' in tweet['extended_tweet']['entities']
                    else [])

            sensitive = tweet['possibly_sensitive'] if 'possibly_sensitive' in tweet else False

            content_toot = html.unescape(content)
            mentions = re.findall(r'@[a-zA-Z0-9_]*', content_toot)
            cws = config.TWEET_CW_REGEXP.findall(content) if config.TWEET_CW_REGEXP else []
            warning = None
            media_ids = []

            if mentions:
                for mention in mentions:
                    # Replace all mentions for an equivalent to clearly signal their origin on Twitter
                    content_toot = re.sub(mention, mention + '@twitter.com', content_toot)

            if urls:
                for url in urls:
                    # Un-shorten URLs
                    content_toot = re.sub(url['url'], url['expanded_url'], content_toot)

            if cws:
                warning = config.TWEET_CW_SEPARATOR.join([cw.strip() for cw in cws]) if config.TWEET_CW_ALLOW_MULTI else cws[0].strip()
                content_toot = config.TWEET_CW_REGEXP.sub('', content_toot, count=0 if config.TWEET_CW_ALLOW_MULTI else 1).strip()

            if media_attachments:
                for attachment in media_attachments:
                    # Remove the t.co link to the media
                    content_toot = re.sub(attachment['url'], '', content_toot)

                    attachment_url = (attachment['media_url_https'] if 'media_url_https' in attachment
                                      else attachment['media_url'])

                    media_ids.append(self.transfer_media(
                        media_url=attachment_url,
                        to='mastodon'
                    ))

            # Now that the toot is ready, we send it.
            try:
                retry_counter = 0
                post_success = False

                lgt(f'Sending toot "{content_toot.strip()}"…')

                while not post_success:
                    try:
                        if len(media_ids) == 0:
                            try:
                                post = self.mastodon_api.status_post(
                                    content_toot,
                                    visibility=config.TOOT_VISIBILITY,
                                    spoiler_text=warning,
                                    in_reply_to_id=reply_to
                                )
                                self.mark_toot_sent(post['id'])

                            except MastodonAPIError:
                                # If the toot we are replying to has been deleted while we were processing it
                                post = self.mastodon_api.status_post(
                                    content_toot,
                                    visibility=config.TOOT_VISIBILITY,
                                    spoiler_text=warning
                                )
                                self.mark_toot_sent(post['id'])

                            since_toot_id = post['id']
                            post_success = True

                        else:
                            try:
                                post = self.mastodon_api.status_post(
                                    content_toot,
                                    media_ids=media_ids,
                                    visibility=config.TOOT_VISIBILITY,
                                    sensitive=sensitive,
                                    spoiler_text=warning,
                                    in_reply_to_id=reply_to
                                )
                                self.mark_toot_sent(post['id'])

                            except MastodonAPIError:
                                # If the toot we are replying to has been deleted (same as before)
                                post = self.mastodon_api.status_post(
                                    content_toot,
                                    media_ids=media_ids,
                                    visibility=config.TOOT_VISIBILITY,
                                    sensitive=sensitive,
                                    spoiler_text=warning
                                )
                                self.mark_toot_sent(post['id'])

                            since_toot_id = post['id']
                            post_success = True

                    except MastodonError:
                        if retry_counter < config.TWITTER_RETRIES:
                            lgt('We were unable to send the toot. '
                                f'Retrying… ({retry_counter+1}/{config.TWITTER_RETRIES})')
                            retry_counter += 1
                            time.sleep(config.TWITTER_RETRY_DELAY)
                        else:
                            raise

                lgt('Toot sent successfully.')

                with lock:
                    self.associate_status(since_toot_id, tweet_id)
                    self.save_status_associations()

            except MastodonError:
                lgt(f'Encountered error after {config.TWITTER_RETRIES} retries. Not retrying.')

            # Broad exception to avoid thread interruption in case of network problems or anything else.
            except Exception as e:
                lgt('Unhandled exception happened - giving up on this toot.')
                lgt(e)
