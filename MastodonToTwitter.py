#!/usr/bin/env python3
# coding: utf-8

"""
Mastodon -> Twitter cross-poster
"""

import time
import re
import requests
import html
import tempfile
import os
import mimetypes
import sys
import getpass
from builtins import input

from mastodon import Mastodon
import twitter

# Enable repost on services
POST_ON_MASTODON = True
POST_ON_TWITTER = True

# Manage visibility of your toot. Value are "private", "unlisted" or "public"
TOOT_VISIBILITY = "unlisted"

# How long to wait between polls to the APIs, in seconds
API_POLL_DELAY = 30

# How often to retry when posting fails
MASTODON_RETRIES = 3
TWITTER_RETRIES = 3

# How long to wait between retries, in seconds
MASTODON_RETRY_DELAY = 20
TWITTER_RETRY_DELAY = 20

# Some helpers copied out from python-twitter, because they're broken there
URL_REGEXP = re.compile((
    r'('
    r'(?!(https?://|www\.)?\.|ftps?://|([0-9]+\.){{1,3}}\d+)'  # exclude urls that start with "."
    r'(?:https?://|www\.)*(?!.*@)(?:[\w+-_]+[.])'              # beginning of url
    r'(?:{0}\b|'                                                # all tlds
    r'(?:[:0-9]))'                                              # port numbers & close off TLDs
    r'(?:[\w+\/]?[a-z0-9!\*\'\(\);:&=\+\$/%#\[\]\-_\.,~?])*'    # path/query params
r')').format(r'\b|'.join(twitter.twitter_utils.TLDS)), re.U | re.I | re.X)

def calc_expected_status_length(status, short_url_length = 23):
    replaced_chars = 0
    status_length = len(status)
    match = re.findall(URL_REGEXP, status)
    if len(match) >= 1:
        replaced_chars = len(''.join(map(lambda x: x[0], match)))
        status_length = status_length - replaced_chars + (short_url_length * len(match))
    return status_length

# Boot-strap app and user information
if not os.path.isfile("mtt_twitter.secret"):
    print("This appears to be your first time running MastodonToTwitter.")
    print("After some configuration, you'll be up and running in no time.")
    print("First of all, to talk to twitter, you'll need a twitter API key.")
    print("\n")
    print("Usually, the application creator is supposed to make that, but with")
    print("an application that isn't a hosted service or a binary blob, with")
    print("the key in plain text, this is not easily possible.")
    print("\n")
    print("You'll need to register an app on https://apps.twitter.com/ .")
    print("You may have to add a phone number to your twitter account to be able")
    print("to do this.")
    print("\n")
    print("Once you are done (make sure to allow your app write permissions),")
    print("go to your apps 'Keys and Tokens' page and enter the info from there")
    print("here.")
    print("\n")

    twitter_works = False
    while not twitter_works:
        TWITTER_CONSUMER_KEY = input("Twitter Consumer Key (API Key): ").strip()
        TWITTER_CONSUMER_SECRET = input("Twitter Consumer Secret (API Secret): ").strip()
        TWITTER_ACCESS_KEY = input("Twitter Access Token: ").strip()
        TWITTER_ACCESS_SECRET = input("Twitter Access Token Secret: ").strip()

        print("\n")
        print("Alright, trying to connect to twitter with those credentials...")
        print("\n")

        try:
            twitter_works = True
            twitter_api = twitter.Api(
                consumer_key = TWITTER_CONSUMER_KEY,
                consumer_secret = TWITTER_CONSUMER_SECRET,
                access_token_key = TWITTER_ACCESS_KEY,
                access_token_secret = TWITTER_ACCESS_SECRET
            )
            twitter_api.VerifyCredentials()
        except:
            twitter_works = False

        if twitter_works == False:
            print("Hmm, that didn't work. Check if you copied everything correctly")
            print("and make sure you are connected to the internet.")
            print("\n")

    print("Great! Twitter access works! With mastodon, the situation is a bit easier,")
    print("all you'll have to do is enter your username (that you log in to mastodon")
    print("with, this is usually your e-mail) and password.")
    print("\n")

    mastodon_works = False
    while mastodon_works == False:
        MASTODON_BASE_URL = 'https://' + input("Mastodon server (press Enter for mastodon.social): https://").strip()
        MASTODON_USERNAME = input("Mastodon Username (e-mail): ").strip()
        MASTODON_PASSWORD = getpass.getpass("Mastodon Password: ").strip()

        if MASTODON_BASE_URL == 'https://':
            # The Mastodon instance base URL. By default, https://mastodon.social/
            MASTODON_BASE_URL = "https://mastodon.social"

        print("\n")
        if os.path.isfile("mtt_mastodon_server.secret"):
            print("You already have Mastodon server set up, so we're skipping that step.")
        else:
            print("Recording Mastodon server...")
            try:
                with open("mtt_mastodon_server.secret", "w") as mastodon_server:
                    mastodon_server.write(MASTODON_BASE_URL)
            except OSError as e:
                print("... but it failed.", e)
                sys.exit(-1)
                mastodon_works = False

        print("\n")
        if os.path.isfile("mtt_mastodon_client.secret"):
            print("You already have an app set up, so we're skipping that step.")
        else:
            print("App creation should be automatic...")
            try:
                Mastodon.create_app(
                    "MastodonToTwitter",
                    to_file = "mtt_mastodon_client.secret",
                    scopes = ["read", "write"],
                    api_base_url = MASTODON_BASE_URL
                )
            except Exception as e:
                print("... but it failed. That shouldn't really happen. Please retry ")
                print("from the start, and if it keeps not working, submit a bug report at")
                print("http://github.com/halcy/MastodonToTwitter .")
                print(e)
                sys.exit(-1)
            print("...done! Next up, lets verify your login data.")
        print("\n")

        try:
            mastodon_works = True
            mastodon_api = Mastodon(
                client_id = "mtt_mastodon_client.secret",
                api_base_url = MASTODON_BASE_URL
            )
            mastodon_api.log_in(
                username = MASTODON_USERNAME,
                password = MASTODON_PASSWORD,
                to_file = "mtt_mastodon_user.secret",
                scopes = ["read", "write"]
            )
        except:
            mastodon_works = False

        if mastodon_works == False:
            print("Logging in didn't work. Check if you typed something wrong")
            print("and make sure you are connected to the internet.")
            print("\n")

    print("Alright, then, looks like you're all set!")
    print("\n")
    print("Your credentials have been saved to three files ending in .secret in the")
    print("current directory. While none of the files contain any of your passwords,")
    print("the keys inside will allow people to access your Twitter and Mastodon")
    print("accounts, so make sure other people cannot accces them!")
    print("\n")
    print("The cross-poster will now start, and should post all your mastodon posts")
    print("from this moment on to twitter while it is running! For future runs, you")
    print("won't see any of these messages. To start over, simply delete all the .secret")
    print("files. Have fun tooting!")
    print("\n")

    with open("mtt_twitter.secret", 'w') as secret_file:
        secret_file.write(TWITTER_CONSUMER_KEY + '\n')
        secret_file.write(TWITTER_CONSUMER_SECRET + '\n')
        secret_file.write(TWITTER_ACCESS_KEY + '\n')
        secret_file.write(TWITTER_ACCESS_SECRET + '\n')

# Read in twitter credentials
with open("mtt_twitter.secret", 'r') as secret_file:
    TWITTER_CONSUMER_KEY = secret_file.readline().rstrip()
    TWITTER_CONSUMER_SECRET = secret_file.readline().rstrip()
    TWITTER_ACCESS_KEY = secret_file.readline().rstrip()
    TWITTER_ACCESS_SECRET = secret_file.readline().rstrip()

# Read in Mastodon server
with open("mtt_mastodon_server.secret", 'r') as secret_file:
    MASTODON_BASE_URL = secret_file.readline().rstrip()

# Log in and start up
mastodon_api = Mastodon(
    client_id = "mtt_mastodon_client.secret",
    access_token = "mtt_mastodon_user.secret",
    ratelimit_method="wait",
    api_base_url = MASTODON_BASE_URL
)
twitter_api = twitter.Api(
    consumer_key = TWITTER_CONSUMER_KEY,
    consumer_secret = TWITTER_CONSUMER_SECRET,
    access_token_key = TWITTER_ACCESS_KEY,
    access_token_secret = TWITTER_ACCESS_SECRET,
    tweet_mode = 'extended' # Allow tweets longer than 140 raw characters
)

ma_account_id = mastodon_api.account_verify_credentials()["id"]
since_toot_id = mastodon_api.account_statuses(ma_account_id)[0]["id"]
print("Tweeting any toots after toot " + str(since_toot_id))
since_tweet_id = twitter_api.GetUserTimeline()[0].id
print("Tooting any tweets after tweet " + str(since_tweet_id))

# Set "last URL length update" time to 1970
last_url_len_update = 0

while True:
    # Fetch twitter short URL length, if needed
    if time.time() - last_url_len_update > 60 * 60 * 24:
        twitter_api._config = None
        url_length = max(twitter_api.GetShortUrlLength(False), twitter_api.GetShortUrlLength(True)) + 1
        last_url_len_update = time.time()
        print("Updated expected short URL length: Is now " + str(url_length))

    # Fetch new toots
    new_toots = []
    if POST_ON_TWITTER:
        new_toots = mastodon_api.account_statuses(ma_account_id, since_id = since_toot_id)
    if len(new_toots) != 0:
        since_toot_id = new_toots[0]["id"]
        new_toots.reverse()
        MEDIA_REGEXP = re.compile(re.escape(MASTODON_BASE_URL.rstrip("/")) + "\/media\/(\w)+(\s|$)+")

        print('Found new toots, processing:')
        for toot in new_toots:
            content = toot["content"]
            media_attachments = toot["media_attachments"]

            # We trust mastodon to return valid HTML
            content_clean = re.sub(r'<a [^>]*href="([^"]+)">[^<]*</a>', '\g<1>', content)
            content_clean = html.unescape(str(re.compile(r'<.*?>').sub("", content_clean).strip()))

            # Trim out media URLs
            content_clean = re.sub(MEDIA_REGEXP, "", content_clean)

            # Don't cross-post replies
            if len(content_clean) != 0 and content_clean[0] == '@':
                print('Skipping toot "' + content_clean + '" - is a reply.')
                continue

            # Split toots, if need be, using Many magic numbers.
            content_parts = []
            if calc_expected_status_length(content_clean, short_url_length = url_length) > 140:
                print('Toot bigger 140 characters, need to split...')
                current_part = ""
                for next_word in content_clean.split(" "):
                    # Need to split here?
                    if calc_expected_status_length(current_part + " " + next_word, short_url_length = url_length) > 135:
                        print("new part")
                        space_left = 135 - calc_expected_status_length(current_part, short_url_length = url_length) - 1

                        # Want to split word?
                        if len(next_word) > 30 and space_left > 5 and not twitter.twitter_utils.is_url(next_word):
                            current_part = current_part + " " + next_word[:space_left]
                            content_parts.append(current_part)
                            current_part = next_word[space_left:]
                        else:
                            content_parts.append(current_part)
                            current_part = next_word

                        # Split potential overlong word in current_part
                        while len(current_part) > 135:
                            content_parts.append(current_part[:135])
                            current_part = current_part[135:]
                    else:
                        # Just plop next word on
                        current_part = current_part + " " + next_word

                # Insert last part
                if len(current_part.strip()) != 0 or len(content_parts) == 0:
                    content_parts.append(current_part.strip())
            else:
                print('Toot smaller 140 chars, posting directly...')
                content_parts.append(content_clean)

            # Tweet all the parts. On error, give up and go on with the next toot.
            try:
                reply_to = None
                for i in range(len(content_parts)):
                    media_ids = []
                    content_tweet = content_parts[i] + " --"

                    # Last content part: Upload media, no -- at the end
                    if i == len(content_parts) - 1:
                        for attachment in media_attachments:
                            attachment_url = attachment["url"]

                            print('Downloading ' + attachment_url)
                            attachment_file = requests.get(attachment_url, stream=True)
                            attachment_file.raw.decode_content = True
                            temp_file = tempfile.NamedTemporaryFile(delete = False)
                            temp_file.write(attachment_file.raw.read())
                            temp_file.close()

                            file_extension = mimetypes.guess_extension(attachment_file.headers['Content-type'])
                            upload_file_name = temp_file.name + file_extension
                            os.rename(temp_file.name, upload_file_name)

                            temp_file_read = open(upload_file_name, 'rb')
                            print('Uploading ' + upload_file_name)
                            media_ids.append(twitter_api.UploadMediaChunked(media = temp_file_read))
                            temp_file_read.close()
                            os.unlink(upload_file_name)

                        content_tweet = content_parts[i]

                    # Some final cleaning
                    content_tweet = content_tweet.strip()

                    # Retry three times before giving up
                    retry_counter = 0
                    post_success = False
                    while post_success == False:
                        try:
                            # Tweet
                            if len(media_ids) == 0:
                                print('Tweeting "' + content_tweet + '"...')
                                reply_to = twitter_api.PostUpdate(content_tweet, in_reply_to_status_id = reply_to).id
                                since_tweet_id = reply_to
                                post_success = True
                            else:
                                print('Tweeting "' + content_tweet + '", with attachments...')
                                reply_to = twitter_api.PostUpdate(content_tweet, media = media_ids, in_reply_to_status_id = reply_to).id
                                since_tweet_id = reply_to
                                post_success = True
                        except:
                            if retry_counter < MASTODON_RETRIES:
                                retry_counter += 1
                                time.sleep(MASTODON_RETRY_DELAY)
                            else:
                                raise
            except:
                print("Encountered error after " + str(MASTODON_RETRIES) + " retries. Not retrying.")

        print('Finished toot processing, resting until next toots.')

    # Fetch new tweets
    new_tweets = []
    if POST_ON_MASTODON:
        new_tweets = twitter_api.GetUserTimeline(since_id = since_tweet_id, include_rts=False, exclude_replies=True)
    if len(new_tweets) != 0:
        since_tweet_id = new_tweets[0].id

        print('Found new tweets, processing:')
        for tweet in new_tweets:
            content = tweet.full_text
            media_attachments = tweet.media
            urls = tweet.urls
            sensitive = tweet.possibly_sensitive

            content_toot = content
            media_ids = []

            if urls:
                for url in urls:
                    # Unshorten URLs
                    content_toot = re.sub(url.url, url.expanded_url, content_toot)

            if media_attachments:
                for attachment in media_attachments:
                    # Remove the t.co link to the media
                    content_toot = re.sub(attachment.url, "", content_toot)

                    attachment_url = attachment.media_url

                    print('Downloading ' + attachment_url)
                    attachment_file = requests.get(attachment_url, stream=True)
                    attachment_file.raw.decode_content = True
                    temp_file = tempfile.NamedTemporaryFile(delete = False)
                    temp_file.write(attachment_file.raw.read())
                    temp_file.close()

                    file_extension = mimetypes.guess_extension(attachment_file.headers['Content-type'])
                    upload_file_name = temp_file.name + file_extension
                    os.rename(temp_file.name, upload_file_name)

                    print('Uploading ' + upload_file_name)
                    media_ids.append(mastodon_api.media_post(upload_file_name))
                    os.unlink(upload_file_name)

            try:
                retry_counter = 0
                post_success = False
                while post_success == False:
                    try:
                        # Toot
                        if len(media_ids) == 0:
                            print('Tooting "' + content_toot + '"...')
                            post = mastodon_api.status_post(content_toot, visibility=TOOT_VISIBILITY)
                            since_toot_id = post["id"]
                            post_success = True
                        else:
                            print('Tooting "' + content_toot + '", with attachments...')
                            post = mastodon_api.status_post(content_toot, media_ids=media_ids, visibility=TOOT_VISIBILITY)
                            since_toot_id = post["id"]
                            post_success = True
                    except:
                        if retry_counter < TWITTER_RETRIES:
                            retry_counter += 1
                            time.sleep(TWITTER_RETRY_DELAY)
                        else:
                            raise
            except:
                print("Encountered error after " + str(TWITTER_RETRIES) + " retries. Not retrying.")

        print('Finished tweet processing, resting until next tweets.')

    time.sleep(API_POLL_DELAY)
