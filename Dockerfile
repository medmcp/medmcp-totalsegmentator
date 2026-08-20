# syntax=docker/dockerfile:1
#
# medmcp-totalsegmentator — whole-body CT/MR anatomy segmentation as a fixed-environment
# MCP stdio server. GPU (torch/nnU-Net). Launched by the core via
# `docker run -i --device nvidia.com/gpu=all`.
#
# Every weight baked into this image is Apache-2.0. The license-gated tasks and the
# CC BY-NC aneurysm model are deliberately absent — see tools/_catalog.py, which is
# also what drives the download list below, so the policy and the image cannot drift.
ARG BASE_IMAGE=medmcp-base:dev
FROM ${BASE_IMAGE} AS runtime

# Stack metadata for one-click install/discovery (read via `docker inspect`, never
# by executing the image).
LABEL org.medmcp.stack='{"name": "medmcp-totalsegmentator", "gpu": true, "tool_timeout_sec": 7200, "skills_path": "/app/src/medmcp_totalsegmentator/skills"}'

# libgomp1 is needed by torch/scikit-image OpenMP paths; libgl1 + libglib2.0-0 by the
# vtk/fury import chain TotalSegmentator pulls in (it imports them even on code paths
# that never render, so a missing libGL is an ImportError at tool call time).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Trust extra CA certs at build time behind a TLS-intercepting (MITM) proxy so
# uv/pip fetch through it. Drop the proxy root CA as a *.crt into ./certs/
# (gitignored; empty = no-op). UV_NATIVE_TLS makes uv use the system trust store.
# Runtime is offline, so no production impact.
COPY certs/ /usr/local/share/ca-certificates/medmcp-extra/
RUN update-ca-certificates
ENV UV_NATIVE_TLS=1

WORKDIR /app

# Frozen install from the committed lock (build-time network; runtime offline).
# Dependencies only, and before the source is copied, so editing one line of Python
# does not redo the multi-GB torch install.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project \
 && find /app/.venv -name '__pycache__' -type d -prune -exec rm -rf {} + \
 && find /app/.venv -name '*.a' -delete

# TotalSegmentator's downloader uses requests, which trusts certifi's bundle rather
# than the system store, so it also needs pointing at the updated bundle to fetch
# through a MITM proxy. Harmless without a proxy CA.
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Weights and config live at a fixed path rather than in a home directory, so they do
# not depend on which user the container runs as.
ENV TOTALSEG_HOME_DIR=/opt/totalsegmentator

# Turn the telemetry off *before* any TotalSegmentator code can run. Upstream POSTs
# run metadata (platform, python version, CUDA availability, task, license number) to
# stats.totalsegmentator.com, and offers no environment-variable kill switch — the
# config file is the only lever. `--network none` blocks the request anyway, but the
# send is wrapped in try/except and therefore fails silently, so relying on the
# sandbox alone would leave the stack phoning home the moment it ran anywhere else.
# statistics_disclaimer_shown is set too: that notice prints on first run regardless
# of quiet=True, and stdout belongs to the MCP framing.
RUN mkdir -p "${TOTALSEG_HOME_DIR}" \
 && printf '%s\n' '{"send_usage_stats": false, "statistics_disclaimer_shown": true}' \
    > "${TOTALSEG_HOME_DIR}/config.json"

# Model weights come from GitHub release assets, which intermittently answer 5xx.
# Unretried, one bad response kills the whole image build — and this build makes ~42
# of these requests, so the odds of hitting one are not small. Retry with linear
# backoff, per dataset, so a failure re-fetches one archive rather than restarting.
RUN printf '%s\n' '#!/bin/sh' \
      'n=0' \
      'until "$@"; do' \
      '  n=$((n+1))' \
      '  [ "$n" -ge 5 ] && { echo "retry: failed after $n attempts: $*" >&2; exit 1; }' \
      '  echo "retry: attempt $n failed; sleeping $((n*15))s" >&2' \
      '  sleep $((n*15))' \
      'done' \
    > /usr/local/bin/retry && chmod +x /usr/local/bin/retry

# The source, and the project itself: everything above depends only on the lock.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Bake every Apache-2.0 weight so segmentation runs with `--network none`. The id list
# comes from the same _catalog module the tools use, so the image can never ship a
# different set than the tools offer — including the auxiliary coarse models
# TotalSegmentator pulls at run time for cropping, which are invisible in the task
# list but fatal to an offline run if missing.
RUN /app/.venv/bin/python -c \
        "from medmcp_totalsegmentator.tools._catalog import weight_dataset_ids; print('\n'.join(str(i) for i in weight_dataset_ids()))" \
        > /tmp/weight_ids.txt \
 && echo "baking $(wc -l < /tmp/weight_ids.txt) weight datasets" \
 && while read -r id; do \
        echo "--- dataset ${id}"; \
        retry /app/.venv/bin/python -c \
            "import sys; from totalsegmentator.libs import download_pretrained_weights as d; d(int(sys.argv[1]))" \
            "${id}"; \
    done < /tmp/weight_ids.txt \
 && rm -f /tmp/weight_ids.txt \
 && find "${TOTALSEG_HOME_DIR}" -name '*.zip' -delete \
 && find /app/.venv -name '__pycache__' -type d -prune -exec rm -rf {} +

ENV PATH=/app/.venv/bin:$PATH \
    UV_NO_SYNC=1

# stdio MCP server. tini reaps the process and forwards signals; stdio passes through.
ENTRYPOINT ["tini", "--", "medmcp-totalsegmentator"]
