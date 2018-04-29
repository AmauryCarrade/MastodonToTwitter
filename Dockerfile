FROM python:3.6-alpine
MAINTAINER Tyler Britten

WORKDIR /usr/src/app

# Copy Source and requirements
COPY . .
RUN apk add --no-cache git && \
    pip3 install --no-cache-dir -r requirements.txt && \
    touch mtt_mastodon_client.secret \
          mtt_mastodon_user.secret \
          mtt_mastodon_server.secret \
          mtt_twitter.secret

CMD ["python3","-m","mtt" ]
