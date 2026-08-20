# medmcp-totalsegmentator

Whole-body anatomy segmentation for the [medmcp](https://github.com/medmcp) ecosystem. Exposes an **MCP (Model Context Protocol) server** over stdio that an LLM agent can invoke to segment anatomical structures on CT and MR images, and to measure their volumes. Wraps [TotalSegmentator](https://github.com/wasserth/TotalSegmentator).

<p align="center">
  <a href="https://medmcp.ai"><b>medmcp.ai</b></a> ·
  <a href="https://github.com/medmcp/medmcp">Main repository</a>
</p>

> [!NOTE]
> **This repository is for developers** who build, extend, or run the TotalSegmentator stack from source. **If you just want to use MedMCP, you don't need this repo** — install the MedMCP app and add this stack through the workspace UI (one-click install). See [medmcp.ai](https://medmcp.ai) or the [main repository](https://github.com/medmcp/medmcp) to get started.

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

## Available tasks

`segment_anatomy` takes a `task`. `total` and `total_mr` are the general whole-body
models; the rest are focused models covering anatomy the whole-body models omit, or
segmenting it more accurately. Ask the agent for a structure by name and it will pick
the task for you (`find_structures`).

| Task | Modality | Structures | Segments |
|---|---|---|---|
| **Whole body** | | | |
| `total` | CT | 117 | Every major organ, bone, muscle and vessel in one pass — the default |
| `total_mr` | MR | 50 | The whole-body model for MR images |
| `body` | CT | 2 | Body outline: trunk, extremities, skin |
| `body_mr` | MR | 2 | Body outline for MR images |
| **Spine** | | | |
| `vertebrae_body` | CT | 2 | Vertebral bodies without the arch, plus intervertebral discs |
| `vertebrae_pp` | CT | 24 | Individually labelled vertebrae C1–L5; fewer errors than the `total` vertebrae |
| `vertebrae_pp_refined` | CT | 24 | As `vertebrae_pp`, with sharper borders; slower |
| `vertebrae_mr` | MR | 25 | Individually labelled vertebrae and sacrum on MR |
| **Chest** | | | |
| `lung_vessels` | CT | 4 | Pulmonary arteries, veins, airways and airway walls |
| `lung_vessels_LEGACY` | CT | 2 | Previous lung vessel model (vessels, trachea/bronchia) |
| `lung_nodules` | CT | 2 | Lung and lung nodules |
| `pleural_pericard_effusion` | CT | 3 | Pleural and pericardial effusion |
| `trunk_cavities` | CT | 4 | Abdominal and thoracic cavity, pericardium, mediastinum |
| `breasts` | CT | 1 | Breast tissue |
| **Abdomen** | | | |
| `liver_segments` | CT | 8 | The eight Couinaud liver segments |
| `liver_segments_mr` | MR | 8 | Couinaud liver segments on MR |
| `liver_vessels` | CT | 2 | Liver vessels and liver tumour |
| `liver_lesions` | CT | 1 | Liver lesions |
| `liver_lesions_mr` | MR | 1 | Liver lesions on MR |
| `kidney_cysts` | CT | 2 | Kidney cysts; more accurate than the ones inside `total` |
| `abdominal_muscles` | CT | 22 | Abdominal and trunk muscle groups (T4–L4 only) |
| **Head & neck** | | | |
| `head_glands_cavities` | CT | 19 | Eyes, lenses, optic nerves, salivary glands, pharynx, nasal cavity |
| `head_muscles` | CT | 11 | Masticatory muscles, tongue, digastric |
| `headneck_bones_vessels` | CT | 12 | Larynx, hyoid, cartilage, carotid arteries, jugular veins |
| `headneck_muscles` | CT | 23 | Neck and shoulder-girdle muscles |
| `craniofacial_structures` | CT | 7 | Mandible, skull, sinuses, upper and lower teeth |
| `teeth` | CT | 77 | Individual teeth by FDI number, jawbones, canals, implants, crowns |
| `oculomotor_muscles` | CT | 19 | Extraocular muscles, eyeballs, optic nerves, skull |
| `cerebral_bleed` | CT | 1 | Intracerebral haemorrhage |
| `ventricle_parts` | CT | 12 | Ventricle subdivisions (horns, body, trigone) |
| **Other** | | | |
| `hip_implant` | CT | 1 | Hip implants |

**Not included.** Some TotalSegmentator models need a licence number and are not part
of this stack: body-composition tissue types, brain structures, heart chambers,
coronary arteries, aortic sinuses, appendicular bones, thigh and shoulder muscles, and
face masking (for anonymisation), plus a brain-aneurysm model restricted to
non-commercial use. Ask for one of those structures and the agent will tell you which
model produces it and why it is unavailable here. Licences — free for non-commercial
use — come from [TotalSegmentator](https://backend.totalsegmentator.com/license-academic/).

## Skill inventory

Skills are SKILL.md files the agent loads on demand to follow multi-step workflows. They are bundled under `src/medmcp_totalsegmentator/skills/` and discovered automatically via `server_config()`.

| Skill name | Description |
|---|---|
| `segment-anatomy` | Workflow for anatomy segmentation and structure volumetry. Covers resolving a named structure to a task before running anything (several tasks segment the same anatomy at different scope), matching CT/MR modality, narrowing a whole-body run with `structures`, and reading a volume out of the CSV in mm³. |

---

### Bundled tools

| Tool / weights | Used by | Source | License |
|---|---|---|---|
| TotalSegmentator | `segment_anatomy` | [upstream](https://github.com/wasserth/TotalSegmentator), weights baked into the image | [Apache-2.0](https://github.com/wasserth/TotalSegmentator/blob/master/LICENSE) |
| nnU-Net | segmentation engine | [upstream](https://github.com/MIC-DKFZ/nnUNet), dependency | [Apache-2.0](https://github.com/MIC-DKFZ/nnUNet/blob/master/LICENSE) |

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
- Disk: the image is large — about 21.5 GB, most of it the CUDA/PyTorch stack and
  ~9.8 GB of model weights. It carries only what segmentation needs: TotalSegmentator's
  preview-rendering, HTML-reporting and radiomics dependencies are not installed.
- The discovery tools (`list_*`, `find_structures`) are pure data lookups — no GPU, no
  model load.
- **Runs fully offline.** Every model is baked into the image, nothing is downloaded at
  run time, and TotalSegmentator's usage reporting is switched off.

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
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://pfriedri.github.io"><img src="https://avatars.githubusercontent.com/u/101359393?v=4?s=100" width="100px;" alt="Paul Friedrich"/><br /><sub><b>Paul Friedrich</b></sub></a><br /><a href="https://github.com/medmcp/medmcp-totalsegmentator/commits?author=pfriedri" title="Code">💻</a> <a href="https://github.com/medmcp/medmcp-totalsegmentator/commits?author=pfriedri" title="Documentation">📖</a> <a href="https://github.com/medmcp/medmcp-totalsegmentator/pulls?q=is%3Apr+reviewed-by%3Apfriedri" title="Reviewed Pull Requests">👀</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://allcontributors.org) specification — contributions of any kind are welcome!

## License

[Apache 2.0](LICENSE). Third-party tools, model weights, and templates bundled by
this stack retain their own licenses and are attributed in [`NOTICE`](NOTICE).
