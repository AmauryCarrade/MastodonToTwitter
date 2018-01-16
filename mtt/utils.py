import json
import mimetypes
import os
import re
import requests
import tempfile
import threading
import twitter

from datetime import datetime
from threading import Thread

from mtt import config, lock


class MTTThread(Thread):
    def __init__(self, mastodon_api, twitter_api, ma_account_id, tw_account_id,
                 status_associations, sent_status, group=None, target=None, name=None):
        super(MTTThread, self).__init__(
            group=group,
            target=target,
            name=name
        )

        self.mastodon_api = mastodon_api
        self.twitter_api = twitter_api
        self.ma_account_id = ma_account_id
        self.tw_account_id = tw_account_id
        self.status_associations = status_associations
        self.sent_status = sent_status

    def mark_toot_sent(self, toot_id):
        with lock:
            self.sent_status['toots'].append(str(toot_id))

    def mark_tweet_sent(self, tweet_id):
        with lock:
            self.sent_status['tweets'].append(str(tweet_id))

    def is_toot_sent_by_us(self, toot_id):
        with lock:
            return str(toot_id) in self.sent_status['toots']

    def is_tweet_sent_by_us(self, tweet_id):
        with lock:
            return str(tweet_id) in self.sent_status['tweets']

    def associate_status(self, toot_id, tweet_id):
        """
        Associates a tweet and a toot in the associations file.
        :param toot_id: The toot ID
        :param tweet_id: The tweet ID
        """
        self.status_associations['t2m'][tweet_id] = toot_id
        self.status_associations['m2t'][toot_id] = tweet_id

    def save_status_associations(self):
        try:
            with open('mtt_status_associations.json', 'w') as f:
                json.dump(self.status_associations['m2t'], f)
        except Exception:
            print('Encountered error while saving status associations file. Threads might be broken after MTT service '
                  'restarts. Check files permissions.')

    def transfer_media(self, media_url, to='twitter'):
        """
        Transfers a media from a network to another.

        :param media_url: The media URL.
        :param to: The destination ('twitter' or 'mastodon', else ValueError is raised)
        :return: The media ID on the destination platform.
        """
        lg('Medias', f'Downloading {media_url} from {"Mastodon" if to == "twitter" else "Twitter"}')

        media_file = requests.get(media_url, stream=True)
        media_file.raw.decode_content = True

        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(media_file.raw.read())
        temp_file.close()

        file_extension = mimetypes.guess_extension(media_file.headers['Content-type'])
        upload_file_name = temp_file.name + file_extension
        os.rename(temp_file.name, upload_file_name)

        temp_file_read = open(upload_file_name, 'rb')
        lg('Medias', f'Uploading {upload_file_name} to {"Twitter" if to == "twitter" else "Mastodon"}')

        if to == 'twitter':
            media_id = self.twitter_api.UploadMediaChunked(media=temp_file_read)
        elif to == 'mastodon':
            media_id = self.mastodon_api.media_post(upload_file_name)
        else:
            raise ValueError(f'Unknown platform "{to}"')

        temp_file_read.close()
        os.unlink(upload_file_name)

        return media_id


def lg(namespace, message):
    """
    Prints a log message.
    :param namespace: A namespace. If None, uses the current thread name.
    :param message: A message to be logged.
    """
    if namespace is None:
        namespace = threading.current_thread().name
    print(f'[{datetime.now():%d/%m/%Y %H:%M:%S}] [{namespace}] {message}')


def lgt(message):
    """
    Prints a log message namespaced with the current thread.
    :param message: A message to be logged.
    """
    lg(None, message)


def calc_expected_status_length(status, short_url_length=23):
    status_length = len(status)
    match = re.findall(config.URL_REGEXP, status)

    if match:
        replaced_chars = len(''.join(map(lambda x: x[0], match)))
        status_length = status_length - replaced_chars + (short_url_length * len(match))

    return status_length


def split_status(status, max_length, split=True, url=None, url_length=None):
    """
    Split toots, if need be, using Many magic numbers.

    status:     The status text to split
    max_length: The maximal length of each sub status
    split:      If true (default), will split in multiple status; else,
                will append the URL.
    url:        If split=False, the URL to append.
    url_length: The length of a Twitter URL (after some reduction).
    """
    content_parts = []

    if not url_length:
        url_length = 24

    max_length -= 6

    if calc_expected_status_length(status, short_url_length=url_length) > max_length:
        current_part = ''
        for next_word in status.split(' '):
            # Need to split here?
            if calc_expected_status_length(current_part + ' ' + next_word, short_url_length=url_length) > max_length:
                space_left = max_length - 5 - calc_expected_status_length(current_part, short_url_length=url_length) - 1

                if split:
                    # Want to split word?
                    if len(next_word) > 30 and space_left > 5 and not twitter.twitter_utils.is_url(next_word):
                        current_part = current_part + " " + next_word[:space_left]
                        content_parts.append(current_part)
                        current_part = next_word[space_left:]
                    else:
                        content_parts.append(current_part)
                        current_part = next_word

                    # Split potential overlong word in current_part
                    while len(current_part) > max_length - 5:
                        content_parts.append(current_part[:max_length - 5])
                        current_part = current_part[max_length - 5:]
                else:
                    space_for_suffix = len('… ') + url_length
                    content_parts.append(current_part[:-space_for_suffix] + '… ' + url)
                    current_part = ''
                    break
            else:
                # Just plop next word on
                current_part = current_part + ' ' + next_word

        # Insert last part
        if len(current_part.strip()) != 0 or len(content_parts) == 0:
            content_parts.append(current_part.strip())

    else:
        content_parts.append(status)

    parts = len(content_parts)
    if split and parts > 1:
        for i in range(parts):
            content_parts[i] += f' — {i + 1}/{parts}'

    return content_parts
