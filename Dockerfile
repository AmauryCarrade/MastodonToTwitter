FROM python:3.5
MAINTAINER Tyler Britten

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy source
COPY ["MastodonToTwitter.py", "mtt_mastodon_client.secret", "mtt_mastodon_user.secret","mtt_twitter.secret", "mtt_mastodon_server.secret","./"]

CMD ["python","-u","MastodonToTwitter.py" ]
