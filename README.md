# medmcp-totalsegmentator

Whole-body anatomy segmentation for the [medmcp](https://github.com/medmcp) ecosystem —
a **distributable Python package** exposing [TotalSegmentator](https://github.com/wasserth/TotalSegmentator)
as an **MCP (Model Context Protocol) server** over stdio. A local LLM invokes the
registered tools by name to segment structures on CT and MR volumes.

> [!WARNING]
> MedMCP and its ecosystem are research software under active development and are
> **not licensed for clinical use**. TotalSegmentator is not a medical device and its
> output is an estimate, not a clinical finding.

---

## Tool inventory

| Tool name | Description | Inputs | Outputs |
|---|---|---|---|
| `segment_anatomy` | Segment anatomical structures on a CT or MR volume | `input_path: Path`, `output_dir: Path?`, `task: str = "total"`, `structures: list[str]?`, `speed: "standard"\|"fast"\|"fastest"`, `device: "auto"\|"cuda"\|"mps"\|"cpu"`, `separate_masks: bool`, `compute_volumes: bool` | Multilabel `*_dseg.nii.gz` (or a directory of binary masks), a label→structure CSV, a per-structure volume CSV (mm³), the resolved device, and warnings |
| `list_segmentation_tasks` | List every available task with its modality and structure count | — | 31 tasks |
| `list_task_structures` | Exact structure names a task produces, in label order | `task: str` | Structure list |
| `find_structures` | Find which tasks produce a named structure | `query: str` | Matching structures → tasks, plus any matches only a non-bundled model could produce |

Segmentation runs in a **subprocess**. TotalSegmentator prints to stdout
unconditionally, and stdout belongs to the MCP framing — in-process, its banner would
corrupt the session. It also keeps the server's import free of torch, so tool
discovery answers in well under a second instead of racing the agent's start-up budget.

### Bundled tools

| Tool / weights | Used by | Source | License |
|---|---|---|---|
| TotalSegmentator | `segment_anatomy` | [upstream](https://github.com/wasserth/TotalSegmentator), weights baked into the image | [Apache-2.0](https://github.com/wasserth/TotalSegmentator/blob/master/LICENSE) |
| nnU-Net | segmentation engine | [upstream](https://github.com/MIC-DKFZ/nnUNet), dependency | [Apache-2.0](https://github.com/MIC-DKFZ/nnUNet/blob/master/LICENSE) |

### Which tasks are available, and why not all of them

TotalSegmentator's **code** is Apache-2.0, but its **weights are not uniformly so**.
This stack bundles only the tasks upstream publishes under Apache-2.0 — 31 of them,
42 weight datasets, ~8.8 GiB — so the image stays redistributable under a single,
unambiguous license.

Not bundled, and not reachable from the tools:

- **License-gated tasks** (`tissue_types`, `brain_structures`, `face`,
  `coronary_arteries`, `heartchambers_highres`, `appendicular_bones`, …). Their
  weights come from the upstream license backend and need a
  [license number](https://backend.totalsegmentator.com/license-academic/) — free for
  non-commercial use, paid for commercial use.
- **`brain_aneurysm`** — CC BY-NC 4.0 with *no* commercial license available. Upstream
  does not list it in `commercial_models`, so filtering on its `requires_license()`
  predicate alone would quietly pull a non-commercial model into an Apache-2.0 image.
  It is excluded by name.
- **`total_v3`** — declared upstream, but its weights release is not published yet
  (every asset URL 404s). `total` segments the same 117 classes.

`find_structures` reports structures that only an excluded model could produce, with
the reason, rather than silently returning "no match".

The policy lives in [`tools/_catalog.py`](src/medmcp_totalsegmentator/tools/_catalog.py)
and is asserted by [`tests/test_licensing.py`](tests/test_licensing.py) — including
that every bundled weights URL points at the public GitHub release. The container
build reads its download list from that same module, so the image cannot ship a
different set than the tools offer.

### Citation

Results produced with this stack should cite the underlying work, not this package:

- **TotalSegmentator** — Wasserthal J, et al. TotalSegmentator: Robust Segmentation of
  104 Anatomic Structures in CT Images. *Radiology: Artificial Intelligence* 5(5)
  (2023). [doi:10.1148/ryai.230024](https://doi.org/10.1148/ryai.230024)
- **TotalSegmentator MRI** (for `*_mr` tasks) — D'Antonoli TA, et al. *Radiology*
  314(2) (2025). [doi:10.1148/radiol.241613](https://doi.org/10.1148/radiol.241613)
- **nnU-Net** — Isensee F, et al. *Nature Methods* 18:203-211 (2021).
  [doi:10.1038/s41592-020-01008-z](https://doi.org/10.1038/s41592-020-01008-z)

Individual tasks carry further citation requirements for the datasets they derive
from; see the upstream README's task list.

Full third-party attribution belongs in [`NOTICE`](NOTICE).

### Hardware requirements

- `segment_anatomy`: CUDA GPU recommended. A whole-body CT at `speed="standard"`
  (1.5 mm) is roughly a minute on a modern GPU; on CPU it runs into many minutes, so
  prefer `speed="fast"` or a `structures` subset there. The tool reports the resolved
  device and warns when it falls back to CPU.
- Disk: the image carries ~8.8 GiB of weights on top of the shared CUDA base.
- The discovery tools (`list_*`, `find_structures`) are pure data lookups — no GPU, no
  model load.

### Telemetry is disabled

Upstream POSTs anonymous run metadata (platform, Python version, CUDA availability,
task, license number) to `stats.totalsegmentator.com`, and offers no environment
variable to turn it off — the config file is the only lever. The image writes
`send_usage_stats: false` at build time, and the subprocess runner re-asserts it at
run time for host-native development. Container stacks also run `--network none`, but
the send is wrapped in `try/except` and so fails *silently*, which makes the sandbox
alone the wrong thing to rely on.

---

## Skill inventory

| Skill | What it is for |
|---|---|
| `segment-anatomy` | Choosing the right task for the anatomy asked about, matching modality, and reporting structure volumes |

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

Files shared with [medmcp-totalsegmentator](https://github.com/medmcp/medmcp-totalsegmentator) are
listed in `scripts/shared-files.txt`. The **Template drift** workflow reports when
one of them diverges; `./scripts/sync-from-template.sh` pulls them back. A change
that belongs in every stack goes in the template, not here.

---

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
