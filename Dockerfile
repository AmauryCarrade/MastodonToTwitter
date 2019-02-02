FROM python:3.6-alpine
MAINTAINER Tyler Britten

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

RUN apk update && \
    apk upgrade && \
    apk add git build-base py3-cffi libffi-dev openssl-dev

# Copy Source and requirements
ADD ["requirements.txt", "__init__.py", "/usr/src/app/"]
RUN pip3 install -r requirements.txt

ADD "mtt" "/usr/src/app/mtt/"
CMD ["python","-m","mtt" ]
