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

## Docker

To run this as a docker app, first run the app once to generate the mtt files, then build the docker container:
```
docker build -t "mastodontotwitter" .
```
Now you can run it:
```
docker run -d --name "mastodontotwitter" mastodontotwitter
```

## Systemd

The `MastodonToTwitter.service` file is a systemd service.
You can edit it to change the install path, copy it to `/etc/systemd/system/`,
and then use `systemctl start|stop|restart|status MastodonToTwitter` and
`journalctl -u MastodonToTwitter.service` to run this as a simple service

