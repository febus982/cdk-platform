FROM python:3.7-slim

ENV CDK_VERSION=1.50.0
ENV ISTIO_VERSION=1.6.4
ENV HELM_VERSION=3.2.4

WORKDIR /cdk_app
RUN apt-get update && \
    apt-get install -y curl && \
    curl -sL https://deb.nodesource.com/setup_12.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

ADD https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz .
RUN tar -zxvf helm-v${HELM_VERSION}-linux-amd64.tar.gz
RUN cp ./linux-amd64/helm /usr/local/bin

RUN npm install -g cdk@${CDK_VERSION}

COPY Pipfile /cdk_app
COPY Pipfile.lock /cdk_app

RUN pip3 install --upgrade pip && pip3 install --upgrade pipenv && pipenv sync

RUN curl -L https://istio.io/downloadIstio | sh - \
    && mkdir -p $HOME/.istioctl/bin \
    && cp istio-${ISTIO_VERSION}/bin/istioctl $HOME/.istioctl/bin/istioctl

COPY . /cdk_app
ENTRYPOINT ["./docker_entrypoint.sh"]
