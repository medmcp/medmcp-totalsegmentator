# Contributing

Thanks for your interest in contributing to a medmcp ecosystem package.

This file lives in [medmcp-template](https://github.com/medmcp/medmcp-template) and is copied into every downstream repo. If you're reading it inside `medmcp-dicom`, `medmcp-neuro`, etc., the same workflow applies — only the repo name differs.

<!-- TEMPLATE-ONLY:START -->
<!-- Everything between these markers is scaffolding instructions for
     someone creating a stack FROM this template. `scripts/rename.sh`
     deletes it, so a scaffolded repo never ships it. -->
## Creating a new package from this template

### 1) Create a new repo from this template

Click **Use this template** on the [medmcp-template](https://github.com/medmcp/medmcp-template) page to create your new repository (e.g. `medmcp-dicom`).

### 2) Run the rename helper

```bash
./scripts/rename.sh medmcp-dicom   # replaces medmcp-template / medmcp_template everywhere
rm scripts/rename.sh
```

### 3) Finish the setup

- Update `pyproject.toml`: description, keywords, and project URLs.
- Replace `README.md` with content specific to your package.
- Verify that `server_config()` in `server.py` returns the correct `name` and `command` — the local agent uses this for autodiscovery via the `[medmcp.stacks]` entry point.

---

<!-- TEMPLATE-ONLY:END -->
## Get started!

Ready to contribute? Here's how to set up your local development environment.

### 1) Create an issue on the GitHub repository

It's good practice to first discuss the proposed changes as the feature might already be implemented. Check the scope too — each medmcp package has a narrow focus (e.g. `medmcp-dicom` is *only* DICOM I/O, not neuro registration). If your idea spans multiple packages, say so in the issue so we can figure out where it belongs.

### 2) Fork the repository on GitHub

Click **Fork** on the repository page to create your fork.

### 3) Clone your fork locally

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
```

### 4) Develop in the dev container (recommended)

The recommended way to work on a medmcp package is **inside the dev container**
(`.devcontainer/`) — it gives everyone the same toolchain (Python 3.12 + uv,
`just`, git, Docker CLI) and matches the deployment image. It derives from the
shared `medmcp-base` image, so build that once from the core repo first
(`just docker-base` in a `medmcp` checkout). Then:

- **PyCharm** (unified PyCharm, 2024.2+; Docker integration is a Professional
  feature): open this project, open `.devcontainer/devcontainer.json`, and use the
  **Dev Container** gutter action. Point PyCharm's Docker integration at your
  (rootless) Docker socket.
- **VS Code:** **Dev Containers: Reopen in Container** (the Dev Containers extension).
- **CLI:** `devcontainer up --workspace-folder .`.

`uv sync` runs automatically on first start. You can build/test the stack's
container image (on the host or from inside) with `just docker-build`; the medmcp
core launches it via a `stacks.d/<stack>.toml` manifest.

### 5) Local install (alternative)

[uv](https://docs.astral.sh/uv/) is required for development. You can install it with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

We provide simple [just](https://just.systems/) commands to set up the rest of the development environment. Just can be installed with:

```bash
uv tool install rust-just
```

You can now install all dependencies with:

```bash
just setup
```

This command (1) checks if [uv](https://docs.astral.sh/uv/) is available and if necessary installs it; (2) runs `uv sync`; (3) installs pre-commit hooks.

Without `just`, the fallback is:

```bash
uv sync
uv run pre-commit install
```

### 6) Running checks locally

Before pushing, make sure all checks pass — these are the same checks that run in CI:

```bash
uv run ruff check          # lint
uv run ruff format --check # formatting
uv run pyright             # type-checking (strict mode)
uv run pytest              # tests
```

Or run the full suite at once:

```bash
just check
```

To auto-fix lint and formatting issues:

```bash
uv run ruff check --fix
uv run ruff format
```

## Code style

- **Formatter / linter**: [Ruff](https://docs.astral.sh/ruff/). Line length 100, target Python 3.12.
- **Type checker**: [Pyright](https://github.com/microsoft/pyright) in **strict mode**. All code must be fully typed; no `Any` escapes without a comment explaining why.
- **Docstrings**: [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings). Public functions, classes, and modules are documented; trivial helpers can be skipped.
- **Pre-commit hooks** enforce formatting, trailing-whitespace, and YAML/TOML validity on every commit.

## Adding a tool

Each medmcp package exposes its functionality as MCP tools — plain typed Python functions that an LLM agent invokes by name. When adding one:

1. Add a typed function with a Google-style docstring to `src/<pkg>/tools/<group>.py` (one file per logical group of related tools). Return a plain `dict` of JSON-serialisable values that includes a `_render` key with natural-language display instructions for that result, and confine any filesystem writes to an `output_dir` argument.
2. Register it in `server.py` with `mcp.add_tool(your_function)`.
3. Add unit tests in the matching `tests/test_<group>.py` — call the function directly, no server needed. Skip tests that need an absent external binary with a fixture rather than failing. (The template ships `tests/test_tools.py` as a starting point.)
4. Add a row to the tool inventory table in `README.md`.
5. If the tool introduces or changes a multi-step workflow, add or update the relevant `skills/<task>/SKILL.md`.

**Write precise docstrings.** FastMCP derives the tool's `name`, `description`, and `inputSchema` directly from the function signature and docstring — the LLM reads them verbatim when deciding which tool to call and how.

**The `skills/` directory** contains an AgentSkill: free-form markdown that teaches the LLM *how to use* the tools — recommended workflow order, gotchas, output format. It is not auto-generated. Update `SKILL.md` whenever tool behaviour or the recommended workflow changes.

## Submitting changes

1. Create a feature branch from `main`:

   ```bash
   git checkout -b my-feature
   ```

2. Make small, focused commits with clear messages.
3. Push your branch and open a pull request against `main`.
4. CI runs on every PR — make sure all checks are green before requesting review.
5. Be responsive to review feedback; small PRs get merged fastest.

## Versioning

This package follows [Semantic Versioning](https://semver.org) (`MAJOR.MINOR.PATCH`). Because the package is consumed by an agent that calls tools by name, the public contract is each tool's **name, parameters, and result shape**:

- **MAJOR** — a breaking change to a tool's name, parameters, or result keys (anything a caller depends on), or removing a tool.
- **MINOR** — a new tool, a new optional parameter, or another backward-compatible addition.
- **PATCH** — backward-compatible bug fixes and internal changes.

The version lives in `pyproject.toml`. Record every notable change under the `[Unreleased]` heading in [CHANGELOG.md](CHANGELOG.md) (the format follows [Keep a Changelog](https://keepachangelog.com)). On release, `[Unreleased]` is renamed to the new version with a date and the release commit is tagged `vMAJOR.MINOR.PATCH`.

## Recognizing contributions

This project uses the [all-contributors](https://allcontributors.org) bot to credit everyone who helps — not just code, but documentation, ideas, bug reports, reviews, and more. The list lives in the README and is tracked in `.all-contributorsrc`; both ship with this template, ready for the bot to write into.

To add someone (or a new contribution type), comment on any issue or pull request:

```
@all-contributors please add @username for code, doc
```

The bot opens a pull request that updates `.all-contributorsrc` and the README contributor table — no local setup or CLI needed. Use the [emoji-key](https://allcontributors.org/docs/en/emoji-key) contribution types (e.g. `code`, `doc`, `bug`, `ideas`, `review`, `maintenance`), comma-separated.

## Reporting issues

Open a GitHub issue with:

- A clear description of the problem or feature request
- Steps to reproduce (for bugs)
- Python version and OS

**Important for medical software:** *Never* attach real patient data (PHI) to issues, logs, or PRs. Use anonymized or synthetic data only. If a bug only reproduces on real data you can't share, describe the file characteristics (modality, vendor, transfer syntax, dimensions) instead.

## Security

For security issues, please follow [SECURITY.md](SECURITY.md) — do **not** open a public issue for suspected vulnerabilities.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
