# medmcp-template

Scaffolding template for packages in the [medmcp](https://github.com/medmcp) ecosystem — foundations (e.g. `medmcp-dicom`), stacks (e.g. `medmcp-neuro`), and supporting tools.

Each package built from this template is a **distributable Python package** that exposes an **MCP (Model Context Protocol) server** over stdio.
An LLM (e.g. a local Gemma4 instance) invokes the registered tools by name to perform medical image processing tasks.

Click **Use this template** on GitHub to scaffold a new package.

> [!WARNING]
> MedMCP and its ecosystem are research software under active development and are **not licensed for clinical use**.

---

## Tool inventory

<!-- Replace this table after scaffolding. One row per registered MCP tool. -->

| Tool name | Description | Inputs | Outputs |
|---|---|---|---|
| `add_numbers` | Placeholder — adds two floats | `a: float`, `b: float` | `{"result": float}` |

### Bundled tools

<!-- REPLACE THIS SECTION, and keep it in step with NOTICE.

A stack that wraps third-party software, or bakes pretrained weights into its
published image, redistributes them: each stays under its own license and most
carry citation requirements. List what you bundle, what uses it, where it comes
from, and under what licence — one row each — then mirror it in NOTICE.

| Tool / weights | Used by | Source | License |
|---|---|---|---|
| example-tool | `your_tool` | [upstream](https://example.org) package dependency (baked into the image) | [Apache 2.0](https://example.org/LICENSE) |
-->

N/A — placeholder package. It bundles no third-party tools and no pretrained
weights, so there is nothing to attribute yet.

### Citation

<!-- REPLACE THIS SECTION if your stack wraps published scientific methods.
Results produced with them should cite the underlying work, not this package:

- **Tool name** — Author A, et al. Title. *Journal* (Year). [doi:...](https://doi.org/...)
-->

N/A — placeholder package, no third-party methods to cite.

Full third-party attribution belongs in [`NOTICE`](NOTICE).

### Hardware requirements

<!-- Document GPU/CPU/RAM requirements per tool, e.g.:
- `brain_extract`: CUDA GPU recommended (≥8 GB VRAM), CPU fallback available (~3× slower)
- `register`: CPU-only, ≥16 GB RAM for typical T1w volumes
-->

N/A — placeholder package.

---

## Skill inventory

| Skill | What it is for |
|---|---|
| `<task-name>` | REPLACE ME — one line on the task this skill guides the agent through. |

Skills live in `src/<package>/skills/<task-name>/SKILL.md`: the workflow steps and
the gotchas for a task, not a description of the tools. The `name:` field must
match the directory name.

---

## Development

### Develop in the dev container (recommended)

This repo ships a dev container (`.devcontainer/`) with the full toolchain
(Python 3.12 + uv, `just`, git, Docker CLI). It derives from the shared
`medmcp-base` image, so build that once from the core repo first (`just docker-base`
in a `medmcp` checkout). Then open the repo with the **Dev Container** action in
PyCharm (2024.2+) or **Reopen in Container** in VS Code — `uv sync` runs on first
start. See the core repo's [CONTRIBUTING](https://github.com/medmcp/medmcp/blob/main/CONTRIBUTING.md)
for IDE specifics.

### Local install (alternative)

```bash
just setup     # install uv, sync dev environment, register pre-commit hooks
just check     # lint + format-check + typecheck + tests
just fix       # auto-fix lint and format
```

For local agent use, install the stack into its own uv tool environment:

```bash
uv tool install --editable .
```

The package registers itself via the `[medmcp.stacks]` entry point. The local
agent autodiscovers it on the next session — no manual config needed.

### Container image (deployment)

```bash
just docker-build           # build the stack image (FROM medmcp-base)
```

It is a stdio MCP server. The medmcp **core** launches it on demand via a
`stacks.d/<your-package>.toml` manifest (`docker run -i …`; GPU stacks add
`--device nvidia.com/gpu=all`, CDI), so deployment nodes need no host Python
install. Build both architectures — the core refuses to install a foreign-arch
image rather than failing later with "exec format error". Pin any GPU/CUDA build
in `pyproject.toml` against the fleet driver floor (CUDA 12.8 / driver R570).

### Staying in sync with the template

Files shared with [medmcp-template](https://github.com/medmcp/medmcp-template) are
listed in `scripts/shared-files.txt`. The **Template drift** workflow reports when
one of them diverges; `./scripts/sync-from-template.sh` pulls them back. A change
that belongs in every stack goes in the template, not here.

---

<!-- TEMPLATE-ONLY:START -->
<!-- Everything between these markers is scaffolding instructions for
     someone creating a stack FROM this template. `scripts/rename.sh`
     deletes it, so a scaffolded repo never ships it. -->

## What's in the box

| Area | Files | Notes |
|---|---|---|
| Build / deps | `pyproject.toml`, `.python-version` | uv-managed, Python ≥3.12, `mcp>=1.0` |
| MCP server | `src/medmcp_template/server.py` | FastMCP over stdio; `server_config()` enables autodiscovery; add tools here |
| Tool scaffold | `src/medmcp_template/tools/example.py` | One file per tool group; include `_render` key for format-critical tools |
| AgentSkill | `src/medmcp_template/skills/<task-name>/SKILL.md` | Workflow steps + gotchas; `name` field must match directory name |
| Dev workflow | `justfile`, `.pre-commit-config.yaml` | `just setup`, `just check`, `just fix` |
| Dev container | `.devcontainer/` | Recommended dev workflow (PyCharm / VS Code) — same toolchain as deployment |
| Container image | `Dockerfile`, `.dockerignore` | Ship the stack as a stdio MCP server image (`FROM medmcp-base`); `just docker-build` |
| CI | `.github/workflows/ci.yml` | Lint, format-check, pyright (strict), pytest on py3.12 / 3.13 |
| Contributor docs | `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` | |
| Issue management | `.github/ISSUE_TEMPLATE/*`, `PULL_REQUEST_TEMPLATE.md` | Medical-context-aware with PHI warnings |

---

## Using this template

### 1. Scaffold a new repo

Click **Use this template → Create a new repository** on GitHub, then clone locally.

### 2. Rename the placeholder package

```bash
./scripts/rename.sh medmcp-dicom
rm scripts/rename.sh
```

### 3. Update metadata

Edit `pyproject.toml`: set `description`, `keywords`, `authors`, and the `Homepage`/`Issues` URLs.

Confirm that `server_config()` in `server.py` returns the correct `name` and `command` — these must match the renamed console script so the local agent resolves the right binary during autodiscovery.

### 4. Implement your tools

- Add tool functions to `src/<your_package>/tools/`.
- Register them in `src/<your_package>/server.py` with `mcp.add_tool(your_tool)`.
- FastMCP derives the MCP `name`, `description`, and `inputSchema` from the function signature and docstring — keep docstrings focused on what the tool does and what it returns.
- For tools with specific output format requirements, include a `_render` key (str) in the return dict with display rules and a required next action (see `process_image` in `example.py`).

### 5. Update the AgentSkill

- Rename `src/<your_package>/skills/<your_package>/` to a task name (e.g. `explore-data`,
  `segment-brain`). Update the `name` field in `SKILL.md` to match the new directory name.
- Replace the placeholder workflow and gotchas with domain-specific guidance.
- **Do not add output format rules to SKILL.md** — those belong in the tool's `_render`
  return value. Keep the skill focused on workflow steps and gotchas only.

### 6. Install and activate

Install the package as a uv tool — the local agent autodiscovers it on the next session:

```bash
uv tool install ./medmcp-dicom          # local dev
# or
uv tool install medmcp-dicom            # from PyPI once published
```

The package declares itself via the `[medmcp.stacks]` entry point (written to `entry_points.txt` at install time). The agent scans all uv tool environments for this section, calls `server_config()` to retrieve the server name and command, and resolves the absolute binary path — no manual edits to `.vibe/config.toml` needed.

The AgentSkill in `src/<your_package>/skills/<task-name>/` is picked up by the agent alongside the MCP server — no separate install step needed.

### 7. Verify

```bash
just setup && just check
```

---

<!-- TEMPLATE-ONLY:END -->
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Short version: fork, `just setup`, `just check`, open a PR against `main`.

### Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://allcontributors.org) specification — contributions of any kind are welcome!

## License

[Apache 2.0](LICENSE). Third-party tools, model weights, and templates bundled by
this stack retain their own licenses and are attributed in [`NOTICE`](NOTICE).
