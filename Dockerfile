FROM python:3.7-slim

ENV CDK_VERSION=1.49.1

WORKDIR /cdk_app
RUN apt-get update && \
    apt-get install -y curl && \
    curl -sL https://deb.nodesource.com/setup_12.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g cdk@${CDK_VERSION}

COPY Pipfile /cdk_app
COPY Pipfile.lock /cdk_app

RUN pip3 install --upgrade pip && pip3 install --upgrade pipenv && pipenv sync

COPY . /cdk_app
ENTRYPOINT ["./docker_entrypoint.sh"]
