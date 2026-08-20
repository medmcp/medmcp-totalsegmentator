---
name: segment-anatomy
description: Workflow for segmenting anatomical structures and measuring their volumes on CT or MR with TotalSegmentator
---

# Anatomy segmentation & volumetry workflow

`segment_anatomy` labels anatomical structures in a CT or MR volume and can write a
per-structure **volume CSV**. The default task `total` covers 117 structures on
whole-body CT; `total_mr` is the 50-structure MR counterpart; around 30 focused tasks
cover anatomy the whole-body models miss or segment less well.

## When to use

- The user wants organs, bones, muscles or vessels labelled on a CT or MR volume.
- The user wants a **volume** or a measurement for a specific structure (liver volume,
  spleen volume, muscle area).
- The user wants a mask to feed another tool (cropping, radiomics, dose planning).

## Steps

1. **Resolve anatomy to a task before running anything.** If the user named a
   structure rather than a task, call `find_structures` first. Several tasks segment
   the same structure at different scope: the liver appears in `total`, but Couinaud
   segments need `liver_segments` and lesions need `liver_lesions`. Picking the
   general model when the user wanted the specific one produces a confident,
   useless answer. `list_segmentation_tasks` shows everything available.
2. **Match the modality.** CT tasks and MR tasks are not interchangeable — a task
   name ending in `_mr` is the MR variant. `segment_anatomy` checks the volume's
   intensity range and returns a `warnings` entry if it looks like the wrong
   modality, but it does **not** block: relay the warning and confirm before
   accepting the result.
3. **Run `segment_anatomy`** with `device="auto"`. Check the resolved `device` in the
   result — if it fell back to `cpu`, say so, because runtime changes from about a
   minute to many minutes.
4. **Report the requested structure.** When the user asked for a specific volume, read
   the CSV at `volumes_path` and report the matching rows (values in **mm³**). Offer
   the full CSV rather than dumping every row.

## Narrowing a whole-body run

On `total` / `total_mr` only, pass `structures=[...]` to segment just what was asked
for. It crops the volume to that region first, so it is substantially faster than a
full run — the right default when the user wants one organ. Names must match the
task's spelling exactly (`kidney_left`, not "left kidney"); `list_task_structures`
gives the exact list. On any other task `structures` is rejected: those tasks are
already specific.

## Gotchas

- **DICOM input needs converting first.** These tools take NIfTI. If the user points
  at a DICOM series, convert it with the DICOM stack before segmenting.
- **`speed` trades away small structures.** `"fast"` (3 mm) and `"fastest"` (6 mm) are
  for triage and for CPU runs. Anything small — adrenal glands, vessels, nodules —
  needs `"standard"`. Never quote a volume measured at `"fastest"` as a real number
  without saying which resolution produced it.
- **Output is one multilabel volume by default** (`*_dseg.nii.gz`), which the
  workspace viewer renders directly as a labelled overlay — offer to open it. The
  label index → name mapping is the CSV at `labels_path`. Only pass
  `separate_masks=True` when a downstream tool actually needs one file per structure.
- **Comparing volumes across subjects** — raw mm³ scales with body size. For cohort
  comparisons normalise (e.g. by height, or by a reference structure) and say which
  normalisation you used.
- **Some structures need a license and are not installed.** `find_structures` reports
  those under `unavailable` with the reason (body-composition tissue types, brain
  structures, coronary arteries, face masking, and the non-commercial aneurysm
  model). Relay that verbatim — do not substitute a different task and present it as
  the thing that was asked for.
- **These are estimates, not clinical findings.** TotalSegmentator is not a medical
  device. Present output as a research measurement, and never as a diagnosis.
