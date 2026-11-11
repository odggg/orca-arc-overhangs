# PR #1 review and integration — 2026-11-11

Reviewed contribution: [Respect slicer wall order, fix Hilbert infill, add Wave
mode](https://github.com/odggg/orca-arc-overhangs/pull/1), by persano.
Head: `79c5d71c96512687ff48ac7fdaebef15b504ba27` (23 commits, 30 changed files).

## Integrated behavior

The 0.3.0 contribution includes the retract-prefix Hilbert fix, start-G-code floor
scan fix, G17/helical Z-hop and M204 handling, optional Wave generation and floor
controls, pasted-profile import, draft settings retention, approximate M73 time
adjustment, and gallery-compatible header comments.

**Print order** has two explicit choices. `layer_tail` is the backward-compatible
default: normal walls/infill → Arcs/Waves → Overhang walls. `slicer` leaves normal
walls/infill at their sliced positions and only moves early Overhang walls after
the generated support. No scheduling operation crosses a layer or tool selection.

## Corrections made during review

- Reproduced lost Hilbert departure Z motion. Limit replacement to the extrusion
  span and preserve the original approach/departure, including firmware retracts.
- Reproduced increased material output at reduced Hilbert density. Apply density
  to extrusion volume as well as spacing; preserve progress markers.
- Normalize emitter items to physical G-code lines before scheduling. G92 E and
  the following feed restore must be parsed as separate commands.
- Preserve fan channels, per-tool nozzle targets and acceleration around moved
  blocks. Never restore another tool's temperature to the active tool. Include
  filament flow ratio when applying the Wave volumetric cap.
- Validate Wave starts against existing support/connected paths and calculate
  coverage from actual generated lines instead of trusting the swept region.
- Replace a tautological order assertion with an exact expected feature sequence;
  restore regression coverage for the previous order and add boundary/state tests.
- Repair the native-bridge test harness for the new DOM event/data attributes.
- Replace invalid renamed wheel aliases with proper wheel filenames, matching
  internal platform tags and regenerated RECORD hashes. Include all seven wheels
  in the release archive and validate their contents.
- Synchronize generated source mirrors and HTML previews during builds. Rebuild
  the synthetic example from the matching input; remove the incidental CLI log.
- Update documentation to describe both orders and separate tested processing
  from unverified physical quality and platform/cloud installation claims.

## Validation

The original 56 Python tests passed; the integrated version passes 66. Both UI
bridges, restricted-file-access checks for Arc/Wave/Hilbert, eight combinations of
real exports/mode/order, and package integrity checks are recorded in
[VALIDATION.md](../VALIDATION.md). Real printer files and detailed run data stay
local. No physical printer validation or Orca Cloud upload was performed.

The scale-factor and stock timelapse reports remain unconfirmed. No claim is made
that every printer/profile or material has been tested.
