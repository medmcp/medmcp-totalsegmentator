# syntax=docker/dockerfile:1
#
# Dev container for medmcp-template — the shared medmcp-base + dev toolchain (uv
# is already in the base; add just, git, build tools, and the Docker CLI so the
# stack image can be built/tested from inside). No Node: stacks have no frontend.
# Python deps are synced at postCreate against the mounted source.
ARG BASE_IMAGE=medmcp-base:dev
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
        less \
        openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -fsSL https://just.systems/install.sh \
    | bash -s -- --to /usr/local/bin
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /workspaces/medmcp-template
