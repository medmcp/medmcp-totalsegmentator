---
name: medmcp-template
description: >
  Placeholder skill — replace with your domain workflow guidance after scaffolding.
  Rename this directory and the `name` field above to the task this skill covers
  (e.g. `explore-data`, `segment-brain`, `register-volumes`).
license: Apache-2.0
compatibility: Requires the medmcp-template MCP server (console script medmcp-template).
---

## Workflow

<!-- Step-by-step instructions for the most common task. Be prescriptive.
     Each step should map to a concrete tool call or user interaction.  -->

1. Confirm the input file exists and is a supported format (NIfTI `.nii`/`.nii.gz` or DICOM).
2. Call the appropriate tool with the required parameters. Follow the `_render` field
   in the result — it contains per-call display rules and a required next action.
3. Multiple inputs: run step 2 per input in separate sections; do not merge results.

## Gotchas

- **Workspace confinement**: All output paths must be within the agreed workspace
  directory passed as `output_dir`. Never write outside it.
- **No PHI in responses**: Do not log, display, or forward patient identifiers.
  Describe files by characteristics (modality, dimensions, transfer syntax) only.
- **Optional keys**: Tools return plain dicts. Parse keys explicitly — do not assume
  field order or presence of optional keys.
- **Not for clinical use**: medmcp tools are research software. If the user describes
  a clinical decision context, flag this clearly before proceeding.
- **Errors**: report and stop; do not retry with modified inputs without asking the user.
