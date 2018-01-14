import html
import mastodon
import mimetypes
import os
import re
import requests
import tempfile
import time

from mastodon.Mastodon import MastodonError, MastodonAPIError

from mtt import config, lock
from mtt.utils import MTTThread, lg, lgt


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

    def run(self):
        self.init_process()

        lgt('Listening for tweets…')

        for tweet in self.twitter_api.GetUserStream():
            if 'text' not in tweet and 'full_text' not in tweet:
                continue

            tweet_id = tweet['id']
            with lock:
                if tweet_id in self.sent_status['tweets']:
                    continue

            content = tweet['full_text'] if 'full_text' in tweet else tweet['text']
            reply_to = None

            with lock:
                if 'in_reply_to_user_id' in tweet and 'in_reply_to_status_id' in tweet and tweet['in_reply_to_user_id']:
                    # If it's a reply, we keep the tweet if:
                    # 1. it's a reply from us (in a thread);
                    # 2. it's a reply from a previously transmitted tweet, so we don't sync
                    #    if someone replies to someone in two or more tweets (because in this
                    #    case the 2nd tweet and the ones after are replying to us)
                    if (tweet['in_reply_to_user_id'] != self.tw_account_id
                       or tweet['in_reply_to_status_id'] not in self.status_associations['t2m']):
                        lgt(f'Skipping tweet {tweet_id} - it\'s a reply.')
                        continue

                    reply_to = self.status_associations['t2m'][tweet['in_reply_to_status_id']]

            media_attachments = (tweet['media'] if 'media' in tweet
                                 else tweet['entities']['media'] if 'entities' in tweet and 'media' in tweet['entities']
                                 else [])

            urls = (tweet['urls'] if 'urls' in tweet
                    else tweet['entities']['urls'] if 'entities' in tweet and 'urls' in tweet['entities']
                    else [])

            sensitive = tweet['possibly_sensitive'] if 'possibly_sensitive' in tweet else False

            content_toot = html.unescape(content)
            mentions = re.findall(r'[@]\S*', content_toot)
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
                    content_toot = re.sub(url.url, url.expanded_url, content_toot)

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
                            except MastodonAPIError:
                                # If the toot we are replying to has been deleted while we were processing it
                                post = self.mastodon_api.status_post(
                                    content_toot,
                                    visibility=config.TOOT_VISIBILITY,
                                    spoiler_text=warning
                                )
                            since_toot_id = post["id"]
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
                            except MastodonAPIError:
                                # If the toot we are replying to has been deleted (same as before)
                                post = self.mastodon_api.status_post(
                                    content_toot,
                                    media_ids=media_ids,
                                    visibility=config.TOOT_VISIBILITY,
                                    sensitive=sensitive,
                                    spoiler_text=warning
                                )
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

                    self.sent_status['toots'].append(since_toot_id)

            except MastodonError:
                lgt(f'Encountered error after {config.TWITTER_RETRIES} retries. Not retrying.')

            # Broad exception to avoid thread interruption in case of network problems or anything else.
            except Exception as e:
                lgt('Unhandled exception happened - giving up on this toot.')
                lgt(e)
