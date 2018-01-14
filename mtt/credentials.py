import getpass
import sys
import twitter

from builtins import input
from mastodon import Mastodon
from mastodon.Mastodon import MastodonError

from mtt import config


def check_credentials():
    '''
    Checks if the credentials are available for use.
    '''
    for key, file in config.FILES.items():
        if not key.startswith('credentials_'):
            continue
        if not file.exists() or file.size == 0:
            return False

    return True


def setup_credentials():
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
                consumer_key=TWITTER_CONSUMER_KEY,
                consumer_secret=TWITTER_CONSUMER_SECRET,
                access_token_key=TWITTER_ACCESS_KEY,
                access_token_secret=TWITTER_ACCESS_SECRET
            )

            verification = twitter_api.VerifyCredentials()
            if verification is None:
                raise RuntimeError
        except:
            twitter_works = False

        if not twitter_works:
            print("Hmm, that didn't work. Check if you copied everything correctly")
            print("and make sure you are connected to the internet.")
            print("\n")

    print("Great! Twitter access works! With mastodon, the situation is a bit easier,")
    print("all you'll have to do is enter your username (that you log in to mastodon")
    print("with, this is usually your e-mail) and password.")
    print("\n")

    mastodon_works = False
    while not mastodon_works:
        MASTODON_BASE_URL = 'https://' + input("Mastodon server (press Enter for mastodon.social): https://").strip()
        MASTODON_USERNAME = input("Mastodon Username (e-mail): ").strip()
        MASTODON_PASSWORD = getpass.getpass("Mastodon Password: ").strip()

        if MASTODON_BASE_URL == 'https://':
            # The Mastodon instance base URL. By default, https://mastodon.social/
            MASTODON_BASE_URL = "https://mastodon.social"

        print("\n")
        if config.FILES['credentials_mastodon_server'].exists() and config.FILES['credentials_mastodon_server'].size > 0:
            print("You already have Mastodon server set up, so we're skipping that step.")
        else:
            print("Recording Mastodon server...")
            try:
                config.FILES['credentials_mastodon_server'].write_text(MASTODON_BASE_URL)
            except OSError as e:
                print("... but it failed.", e)
                mastodon_works = False
                continue

        print("\n")
        if config.FILES['credentials_mastodon_client'].exists() and config.FILES['credentials_mastodon_client'].size > 0:
            print("You already have an app set up, so we're skipping that step.")
        else:
            print("App creation should be automatic...")
            try:
                Mastodon.create_app(
                    "MastodonToTwitter",
                    to_file=config.FILES['credentials_mastodon_client'],
                    scopes=["read", "write"],
                    api_base_url=MASTODON_BASE_URL
                )
            except Exception as e:
                print("... but it failed. That shouldn't really happen. Please retry ")
                print("from the start, and if it keeps not working, submit a bug report at")
                print("http://github.com/halcy/MastodonToTwitter .")
                print(e)
                continue
            print("...done! Next up, lets verify your login data.")
        print("\n")

        try:
            mastodon_works = True
            mastodon_api = Mastodon(
                client_id=config.FILES['credentials_mastodon_client'],
                api_base_url=MASTODON_BASE_URL
            )
            mastodon_api.log_in(
                username=MASTODON_USERNAME,
                password=MASTODON_PASSWORD,
                to_file=config.FILES['credentials_mastodon_user'],
                scopes=["read", "write"]
            )
        except MastodonError:
            mastodon_works = False

        if not mastodon_works:
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

    with config.FILES['credentials_twitter'].open('w') as secret_file:
        secret_file.write(TWITTER_CONSUMER_KEY + '\n')
        secret_file.write(TWITTER_CONSUMER_SECRET + '\n')
        secret_file.write(TWITTER_ACCESS_KEY + '\n')
        secret_file.write(TWITTER_ACCESS_SECRET + '\n')
