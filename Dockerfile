FROM python:3.6-alpine
MAINTAINER Tyler Britten

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# Copy Source and requirements
ADD ["requirements.txt", "__init__.py", "mtt/", "/usr/src/app/"]
RUN pip3 install --no-cache-dir -r requirements.txt && \
    touch mtt_mastodon_client.secret \
          mtt_mastodon_user.secret \
          mtt_mastodon_server.secret \
          mtt_twitter.secret

CMD ["python","-m","mtt" ]
