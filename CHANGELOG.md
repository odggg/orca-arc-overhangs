# Changelog

## Unreleased
- Respect the slicer's wall/infill order again, including Orca's "Print infill first": Arcs stay where the Bridge they replace was and normal walls/infill are never moved. This reverts the 0.2.4 behavior that forced every wall to print before the Arcs and degraded quality.
- Only Overhang walls that the slicer printed before the Arcs of the same layer and tool run are moved, to just after the last Arc block, so they rest on the Arcs.
- Fix the extruder counter and feed restored after relocated blocks (previously taken before the block's final reset).
- Fix the next-layer Hilbert option doing nothing: Orca opens a feature with retract, travel and unretract, and the retraction/unretract guards rejected every such feature. Hilbert jumps now retract and unretract around travel.
- New optional **Wave** overhang mode (`overhang_mode`, default `arc`): the bridge is filled with offset wavefronts grown from the supported edge instead of concentric arcs. Port of the wavefront propagation from OrcaSlicer-WaveOverhangs; narrow-neck splitting, corner taper, ZigZag chaining and wave-aware supports are not ported. Spacing is set by `wave_spacing_nozzle_ratio` (default 0.875).
- Tests: infill-first order, default order, and Hilbert on a feature that opens with a retraction and Wave mode (42 total).

## 0.2.4 — 2026-10-30
- Update plugin metadata, displayed version, package filenames and documentation to 0.2.4 for Orca Cloud.
- No toolpath or configuration behavior changes in this version bump.

## 0.2.3 â€” 2026-10-24
- Repay tracked retraction during positive XY extrusion.
- Clear submicron wipe rounding residue after positive extrusion.
- Retain protection for genuinely unrecovered retraction at bridge boundaries.
- Add three regressions: 25 Python tests total.

## 0.2.1 â€” 2026-10-24
- Avoid lazy UTF-8 BOM codec imports that triggered repeated host permission prompts.
- Fix the sandboxed native configuration save button and asynchronous acknowledgement.
- Support G2/G3 input analysis, scarf contour recovery, M73 retention and geometric overhang detection.
- Show the last export report in the top tab.

## 0.2.0 â€” 2026-10-24
- Add a main-window Pages tab and shared configuration with preset override notices.

## 0.1.0 â€” 2026-10-24
- Initial experimental native OrcaSlicer 2.5 port with coverage checks and atomic export.

## 2026-10-29 local repair for 0.2.3

- Accept one distinct physical tool index even when it is non-zero; reject only multiple distinct physical tool indices.
- Keep Bambu virtual tool markers outside the physical-tool count.
- Add regression coverage for single-tool T1 and true multi-tool T1/T2 G-code.


## 2026-10-29 local repair: unsupported overhangs only

- Replace Bridge features only when the geometry contains enough genuinely unsupported area.
- Preserve bridges supported by the lower-layer footprint, even when an Overhang-wall label is nearby.
- Add a regression test for fully supported Bridge paths.

## 2026-10-29 local repair: wall overlap control

- Reduce the default wall overlap from 0.8 mm to 0.2 mm.
- Account for the printed widths of the Arc path and wall so a 0 mm setting creates no overlap with the wall.
- Add geometry coverage checks for zero, normal and high overlap settings.

## 2026-10-30 local repair: multi-material support

- Track physical T-tool selection through G-code and retain tool changes.
- Select per-tool nozzle, filament, wall-width and flow values for each Bridge feature.
- Leave a Bridge feature unchanged if it switches tools internally.
- Add regression coverage for material-specific extrusion and preserved tool switches.


## 2026-10-30 local repair: optional next-layer Hilbert infill

- Add a selector to keep Orca's fill pattern or opt into Hilbert infill on the layer immediately after replaced Arc bridges.
- Limit replacement to solid internal infill overlapping the Arc zone; preserve sliced extrusion outside the zone.
- Keep the slicer pattern as the default because Hilbert can increase print time.
- Add selector, geometry, and setting-validation regressions.


## 2026-10-30 local repair: Arc ordering

- Insert generated Arcs before the first same-tool wall feature on that layer so the Arc support is laid down before inner, outer, and overhang walls.
- Remove the original Bridge extrusion at its original location while preserving progress markers and restore the slicer position at the insertion point.
- Add a regression for Arc-before-wall ordering.


## 2026-10-30 local repair: firmware retract commands

- Accept parameterless G10/G11 firmware retract/unretract commands and track their state separately from E-based retraction.
- Preserve Bridge features that cross firmware-retract commands or begin/end while firmware retraction is active, instead of failing the complete export.
- Keep parameterized G10/G11 and unrelated unsupported state commands rejected.
- Add regressions for balanced firmware retracts, safe Bridge preservation and unsupported parameterized commands.


## 2026-10-30 correction: finish the layer with Arcs and overhang walls

- Keep normal walls and infill first, then print generated Arcs and finish with Overhang wall paths. This supersedes the earlier Arc-before-all-walls placement.
- Relocate complete motion blocks with their original start coordinates, extrusion coordinate and feed; restore the state expected by subsequent G-code.
- Preserve tool-selection boundaries and end/layer commands. Unsupported relocation states keep the original slice.
- Verify modern/legacy feature tags, unchanged overhang geometry and layer/end-code boundaries.
