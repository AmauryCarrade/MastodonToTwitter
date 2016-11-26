# MastodonToTwitter
Mastodon -> Twitter cross-poster.

Requirements:

    # Python 2
    pip install Mastodon.py python-twitter

    # Python 3
    pip3 install Mastodon.py python-twitter

For basic usage, just run the MastodonToTwitter.py script and
follow the on-screen prompts. To change the polling interval 
or the instance of Mastodon the script talks to, edit the 
settings in the script.

The script stores your credentials in a bunch of files ending
on .secret. The contents of these files let people access your
twitter and Mastodon accounts, so do not share them around.
