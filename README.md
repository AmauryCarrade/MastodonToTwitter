# Warning
This code is currently very un-maintained. If somebody who preferably actually 
uses it (I do not) wants to take over, I'd apperciate that  just let me know.

# MastodonToTwitter
Mastodon <-> Twitter cross-poster.

Requirements: Python 3.4 minimum, with two packages, python-twitter
version 3.2 upwards and Mastodon.py version 1.0.2 upwards:

    # Python 3
    pip3 install -r requirements.txt

For basic usage, just run the MastodonToTwitter.py script and
follow the on-screen prompts. To change the polling interval
or the instance of Mastodon the script talks to, edit the
settings in the script.

The script stores your credentials in a bunch of files ending
on .secret. The contents of these files let people access your
twitter and Mastodon accounts, so do not share them around.

There is also a `mtt_status_associations.json` file created. It
stores which tweet corresponds to which toot, and is used to
synchronize threads. You can delete it at any moment, but
if you do, old threads will no longer be synced. More importantly,
replies to old theads on the Twitter side will not be posted on
Mastodon at all.

To customize options, you can either modify directly the
`MastodonToTwitter.py` file, the configuration option being
at the top of the script (best option if you want to tweak
a few things and forget this), or create a `mtt_config.py`
file and copy the configuration variables you want to change
there (best option if you want to be able to update this using
`git pull` and don't want to alter the core files).


## Docker

To setup MastodonToTwitter first run the following command and follow instructions:
```
docker-compose run --rm mtt
```
Once setup you just need to run the following command in future.
```
docker-compose up -d
```


## Systemd

The `MastodonToTwitter.service.sample` file is a systemd service.
You can copy it to `MastodonToTwitter.service`, edit it to change the
install path, symlink it to `/etc/systemd/system/`, and then use
`systemctl start|stop|restart|status MastodonToTwitter` and
`journalctl -u MastodonToTwitter.service` to run this as a simple service.

The `MastodonToTwitter.service` file is in the `gitignore` file, so you will not have a problem when updating.


## Heroku

You can run this on a free heroku dynamo

Add heroku as a remote repository with `heroku git:remote -a your-app-here`

Create a `runtime.txt` file which contains:
```
python-3.6.1
```
Create a `Procfile` which contains
```
worker: python3 MastodonToTwitter.py
```
Commit and push your changes to heroku master.

Open a bash shell on heroku with `heroku run bash` and follow the basic usage
instructions to generate your tokens.

Exit bash and scale your heroku instance `heroku ps:scale worker=1` to get things going.
