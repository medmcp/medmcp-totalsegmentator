# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

First cut of `medmcp-totalsegmentator` — the whole-body anatomy stack for MedMCP. An
MCP server exposing TotalSegmentator's CT and MR segmentation as tools an agent calls
by name. All model weights are baked into the container image, so every tool runs with
networking denied.

**Not licensed for clinical use.** TotalSegmentator is not a medical device.

### Added

- `segment_anatomy` — segments anatomical structures on a CT or MR volume across 31
  tasks, from the 117-structure whole-body `total` model to focused models for
  vertebrae, liver segments, lung nodules, head and neck anatomy, and teeth. Writes a
  single multilabel `*_dseg.nii.gz` by default — one file the workspace viewer renders
  directly as a labelled overlay — plus a label→structure CSV and a per-structure
  volume CSV in mm³. `separate_masks=True` gives one binary mask per structure instead.
- `find_structures`, `list_segmentation_tasks` and `list_task_structures` — pure data
  lookups (no GPU, no model load) that let the agent resolve anatomy to a task before
  running anything. Picking the wrong task is the easiest way to get a confident,
  meaningless answer, so "segment the liver" resolves to a concrete task first.
- Shared device convention: `device="auto"` (the default) resolves to cuda > mps > cpu,
  and the resolved device is reported back, so an `auto` → CPU fallback is never silent.
  A CPU run also warns about runtime, which changes by an order of magnitude.
- Deterministic modality check: the input's intensity range is sniffed for Hounsfield
  units and a mismatch with the task's modality comes back as a warning. Running a CT
  task on an MR scan otherwise produces a plausible-looking, meaningless result. It
  warns and never blocks — the header cannot actually confirm modality.
- Container image: `Dockerfile` (`FROM medmcp-base`; torch pinned to the cu128 build at
  `2.7.1` so it runs on any host driver >= R570; ~8.8 GiB of weights baked across 42
  datasets), `org.medmcp.stack` label for one-click install. **arm64-clean**: every
  dependency resolves to a pure-Python or linux-aarch64 wheel, so unlike the neuro
  stack nothing compiles from source on aarch64.
- `segment-anatomy` skill covering task selection, modality matching, and volumetry.

### Fixed

- The arm64 image could not be built at all. TotalSegmentator requires `fury<2`, whose
  newest release caps `vtk` below 9.4 — and vtk only began publishing linux-aarch64
  wheels at 9.5.0, so the arm64 leg failed during dependency install. The cap is now
  lifted by an override; fury and vtk are only used by preview/rendering code that the
  segmentation path never imports. A test walks the lock with environment markers
  evaluated for linux/aarch64 and fails if any package that architecture actually
  needs has no aarch64 wheel and no sdist — checking each package's *latest* release on
  PyPI does not catch this, because a transitive cap can pin an older version.
- A one-line code change no longer re-downloads all 9.6 GB of weights when building the
  image. The weight-baking layer now depends only on the module that decides which
  weights are needed, rather than on the whole source tree.

### Security

- **Only Apache-2.0 weights are bundled**, so the image stays redistributable under a
  single unambiguous license. Tasks needing a TotalSegmentator license number are
  excluded, as is `brain_aneurysm` (CC BY-NC 4.0, no commercial license available) —
  which upstream does *not* flag in `commercial_models`, so filtering on its own
  `requires_license()` predicate would have pulled a non-commercial model into the
  image. The policy is enforced in one module and asserted by tests, including that
  every bundled weights URL points at the public GitHub release rather than the
  license backend. The container build reads its download list from that same module,
  so the image cannot ship a different set than the tools offer.
- **Upstream telemetry is disabled.** TotalSegmentator POSTs run metadata (platform,
  Python version, CUDA availability, task, license number) to
  `stats.totalsegmentator.com` and offers no environment-variable kill switch. The
  image writes `send_usage_stats: false` at build time and the runner re-asserts it at
  run time for host-native use. `--network none` blocks it in the container, but the
  send is wrapped in `try/except` and fails silently, so the sandbox alone was the
  wrong thing to rely on.
- Segmentation runs in a **subprocess**: TotalSegmentator prints to stdout
  unconditionally, and stdout belongs to the MCP framing. It also keeps torch out of
  the server's import path, so tool discovery answers in ~0.5 s rather than racing the
  agent's start-up budget — a stack that answers too slowly loads with no tools at all.
