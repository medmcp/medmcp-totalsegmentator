# syntax=docker/dockerfile:1
#
# medmcp-template — stack packaged as a fixed-environment MCP stdio server.
# Derives from the shared `medmcp-base` image (built in the medmcp core repo:
# `just docker-base`). CPU stacks just use it; GPU stacks request the GPU in their
# stacks.d manifest (`--device nvidia.com/gpu=all`, CDI). Add any system packages
# or baked model weights your tools need before `uv sync`.
ARG BASE_IMAGE=medmcp-base:dev
FROM ${BASE_IMAGE} AS runtime

# Stack metadata for one-click install/discovery (read via `docker inspect`, never
# by executing the image). Keep name/skills_path in sync with the package; set
# "gpu": true for GPU stacks (the core then launches with --device nvidia.com/gpu=all).
LABEL org.medmcp.stack='{"name": "medmcp-template", "gpu": false, "tool_timeout_sec": 1800, "skills_path": "/app/src/medmcp_template/skills"}'

WORKDIR /app

# Frozen install from the committed lock (build-time network; runtime offline).
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH=/app/.venv/bin:$PATH \
    UV_NO_SYNC=1

# stdio MCP server. tini reaps the process and forwards signals; stdio passes through.
ENTRYPOINT ["tini", "--", "medmcp-template"]
