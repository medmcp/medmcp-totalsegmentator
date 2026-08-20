# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The scaffolding docs match what a real stack ends up looking like. `CONTRIBUTING.md`
  told contributors to add an entry to `skills/<pkg>/references/TOOLS.md`, a file that
  exists in no stack and not in this template either, and it documented neither the
  versioning policy nor the all-contributors bot — even though `.all-contributorsrc`
  and the README markers ship here ready for it. The README's weights section is now
  a bundled-tools table plus a citation section, matching `NOTICE`, which already asked
  for both. `scripts/rename.sh` names `NOTICE` in its closing checklist, which it
  never did.

### Added

- A test asserting `server_config()` still satisfies the core's autodiscovery
  contract, and a commented `startup_timeout_sec` beside it. A stack that answers
  too slowly is dropped with no tools and no error, which is a miserable thing to
  debug from the far side.

- Shared-file sync: `scripts/shared-files.txt` lists what every stack inherits from
  this template, `scripts/sync-from-template.sh` pulls those files into a stack, and
  a **Template drift** workflow reports when one has diverged. Four such drifts had
  already accumulated across the stacks, unnoticed.
- `NOTICE`, `certs/` (+ `.gitignore` rules) and `.all-contributorsrc`, so a scaffolded
  stack starts with attribution, proxy-friendly builds and contributor credit rather
  than acquiring them one repo at a time.

### Changed

- README carries the all-contributors markers and points at `NOTICE` from the
  licence section, so `.all-contributorsrc` has somewhere to render and the
  attribution file is actually discoverable.

- `CODEOWNERS` is gone. Every stack repo shipped the same fully commented-out
  file behind a "replace before the repo goes public" note, so it assigned no
  ownership and requested no reviews. With two maintainers who already watch
  these repos it earns nothing today, and under code-owner-gated branch
  protection it would mean neither maintainer could merge without the other. It
  is three lines to reinstate when there are outside contributors or genuinely
  separate areas of ownership.
- Docs and build files refer to the core repo as `medmcp`, not the pre-rename
  `medmcp-dev`.

- `rename.sh` now finishes the job: it strips the `TEMPLATE-ONLY` sections from
  README/CONTRIBUTING, points the image workflow at the new stack and enables
  publishing, and removes itself. `medmcp-dicom` shipped the template's "creating a
  new package" instructions because these were left to the reader.
- README follows the same shape as the published stacks (tool inventory, skill
  inventory, development, contributing, license), so a scaffolded repo starts
  consistent instead of being reshaped later.
- The image workflow takes a `concurrency` group. Two merges landing close together
  could otherwise leave `:main` built from the older commit, silently (medmcp#109).

- Container scaffold: `Dockerfile` + `.dockerignore` + `.devcontainer` + `just docker-build`; `org.medmcp.stack` label; `rename.sh` also renames the Dockerfile and devcontainer.json; dev-container-first contributor docs.

- Initial template scaffold: pyproject + uv, ruff + pyright strict, pytest, just, pre-commit
- GitHub Actions CI workflow (lint, format-check, pyright, pytest on py3.12 / 3.13)
- Contributor docs: README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY
- Issue and PR templates with medical-context PHI warnings
- Rename helper script for one-shot placeholder replacement
