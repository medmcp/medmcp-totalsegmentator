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

# libgomp1 is needed by the torch/scikit-image OpenMP paths. No libgl1/libglib2.0-0:
# those are only needed by the vtk import chain, which is pruned below.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Trust extra CA certs at build time behind a TLS-intercepting (MITM) proxy so
# uv/pip fetch through it. Drop the proxy root CA as a *.crt into ./certs/
# (gitignored; empty = no-op). UV_NATIVE_TLS makes uv use the system trust store.
# Runtime is offline, so no production impact.
COPY certs/ /usr/local/share/ca-certificates/medmcp-extra/
RUN update-ca-certificates
ENV UV_NATIVE_TLS=1

WORKDIR /app

# Dependencies, and the removal of the ones this stack never uses, in a SINGLE layer.
#
# The pruning has to share a layer with the install. Docker layers are additive, so
# uninstalling in a later layer reclaims nothing — it writes a whiteout over bytes that
# stay in the image, and the result is marginally *larger*. (A builder stage would also
# work, but it needs the whole environment twice on disk at once, which is a real
# constraint for an image this size.)
#
# What goes: TotalSegmentator's preview-rendering, HTML-reporting and radiomics
# dependencies — vtk alone is 341 MB. None is reachable from the segmentation path.
# They cannot be resolved away, because TotalSegmentator declares them as hard
# requirements.
#
# The list is empirically derived, and two candidates had to be put back: matplotlib
# (nnU-Net's trainer imports it at module scope) and the DICOM packages
# (totalsegmentator.nnunet imports dicom_io at module scope, though nothing here reads
# DICOM). tests/test_pruned_deps.py reads this list, blocks the modules and imports the
# segmentation chain, so an upstream release that starts importing one fails CI rather
# than the image.
# PRUNED-PACKAGES: vtk fury pygltflib dipy pyarrow xvfbwrapper imgkit xmltodict
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project \
 && uv pip uninstall --python /app/.venv/bin/python \
        vtk fury pygltflib dipy pyarrow xvfbwrapper imgkit xmltodict \
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

# Bake every Apache-2.0 weight so segmentation runs with `--network none`. The id list
# comes from the same _catalog module the tools use, so the image can never ship a
# different set than the tools offer — including the auxiliary coarse models
# TotalSegmentator pulls at run time for cropping, which are invisible in the task
# list but fatal to an offline run if missing.
#
# Only _catalog.py is copied in, ahead of the rest of the source, and the module is
# loaded from that file directly (it imports nothing of ours — only TotalSegmentator's
# pure-data maps). That keeps this layer's cache key to the one file that decides which
# weights are needed: with `COPY src` above it, editing any line of Python anywhere in
# the package re-downloaded all 9.8 GB.
COPY src/medmcp_totalsegmentator/tools/_catalog.py /tmp/catalog_probe.py
RUN /app/.venv/bin/python -c \
        "import importlib.util as u; s = u.spec_from_file_location('catalog_probe', '/tmp/catalog_probe.py'); m = u.module_from_spec(s); s.loader.exec_module(m); print('\n'.join(str(i) for i in m.weight_dataset_ids()))" \
        > /tmp/weight_ids.txt \
 && echo "baking $(wc -l < /tmp/weight_ids.txt) weight datasets" \
 && while read -r id; do \
        echo "--- dataset ${id}"; \
        retry /app/.venv/bin/python -c \
            "import sys; from totalsegmentator.libs import download_pretrained_weights as d; d(int(sys.argv[1]))" \
            "${id}"; \
    done < /tmp/weight_ids.txt \
 && rm -f /tmp/weight_ids.txt /tmp/catalog_probe.py \
 && find "${TOTALSEG_HOME_DIR}" -name '*.zip' -delete

# The source, and the project itself, last: everything above depends only on the lock
# and on _catalog.py, so a code change rebuilds seconds of work instead of re-fetching
# every weight archive.
#
# --no-deps, not `uv sync`: a sync would reconcile the environment against the lock and
# faithfully reinstall everything pruned above. The dependencies are already installed
# from that same lock, so only this package needs adding.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-deps --python /app/.venv/bin/python . \
 && find /app/.venv -name '__pycache__' -type d -prune -exec rm -rf {} +

ENV PATH=/app/.venv/bin:$PATH \
    UV_NO_SYNC=1

# stdio MCP server. tini reaps the process and forwards signals; stdio passes through.
ENTRYPOINT ["tini", "--", "medmcp-totalsegmentator"]
