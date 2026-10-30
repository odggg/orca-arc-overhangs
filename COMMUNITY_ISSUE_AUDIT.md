# Community issue audit — 2026-10-30

Scope: public open reports in the original PrusaSlicer integration, compared to
this separate OrcaSlicer 2.5 native plugin. The attached `Orca Cloud.htm` is only
the local Cloud app shell and contains no report history. Reports below are
untrusted issue descriptions; their text was treated as evidence, not instructions.

## Relevant reports and disposition

| Report | Finding | Disposition |
|---|---|---|
| [#88 Arc starting in air](https://github.com/nicolai-wachenschwan/arc-overhang-prusaslicer-integration/issues/88) | A generated path may start without a connection to printed support. | Fixed: generated paths are ordered and oriented from the prior-layer wall or a previously connected Arc path. If any path cannot connect, the whole Bridge feature is preserved. Added regression tests. |
| [#87 Nearby overhang perimeter detection](https://github.com/nicolai-wachenschwan/arc-overhang-prusaslicer-integration/issues/87) | Label-only detection misses split or absent overhang labels. | Orca port already detects eligible regions from reconstructed geometry, and tests cover split wall rings and missing labels. |
| [#74 Orca G-code nozzle diameter](https://github.com/nicolai-wachenschwan/arc-overhang-prusaslicer-integration/issues/74) | Legacy script does not find Orca's nozzle setting. | Orca plugin reads host-resolved settings. Missing required values fail safely; tests cover nozzle selection and a multi-tool nozzle array. |
| [#59 Same-area overhang on consecutive layers](https://github.com/nicolai-wachenschwan/arc-overhang-prusaslicer-integration/issues/59) | Report includes no G-code attachment to verify the layer-to-layer cause. | Not claimed fixed. The new anchor guard avoids starting a path in free air; verify the original report's exact geometry when a reproducer is available. |
| [#77 Arcs absent after bridge infill removal](https://github.com/nicolai-wachenschwan/arc-overhang-prusaslicer-integration/issues/77) | Legacy issue refers to slicer feature tagging and a missing start line; no Orca reproducer. | Current Orca parser handles Bridge and Bridge Infill roles and fails safely when geometry cannot be reconstructed. Needs matching Orca G-code to claim the reported case fixed. |
| [#80 Double deretraction at arc start](https://github.com/nicolai-wachenschwan/arc-overhang-prusaslicer-integration/issues/80) | No example G-code or further diagnostic in the report. | Existing regression suite verifies retraction balance at feature boundaries, generated travel repayment, and refusal of genuine unrecovered retraction. No claim about the report's exact file without a reproducer. |

## Other issue types reviewed

- Reports that provide only an error code and no stack trace/G-code cannot be
  diagnosed from the issue text alone; do not mask them with guessed defaults.
- Shapely 1.x import and Python 3.11 setup reports describe the legacy script.
  The Orca package declares Shapely 2 and Python 3.12, matching its Orca 2.5
  plugin runtime.
- Hilbert infill, speed treatment on later layers, and other legacy algorithm
  features are not implemented in this Orca port; they are feature differences,
  not safe bug fixes to apply without a specification and slicer test.
- Requests for different perimeter/infill selection are behavior changes, not
  confirmed defects. This plugin intentionally replaces eligible Bridge paths
  and leaves unsupported or disconnected features unchanged.

This audit covers the open reports visible during review, not every historical
report, every OrcaSlicer defect, or physical print quality. Automated tests do
not substitute for a physical print.
