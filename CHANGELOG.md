# Changelog

## 0.3.0 — 2026-11-06
- Respect the slicer's wall/infill order again, including Orca's "Print infill first": Arcs stay where the Bridge they replace was and normal walls/infill are never moved. This reverts the 0.2.4 behavior that forced every wall to print before the Arcs and degraded quality.
- Only Overhang walls that the slicer printed before the Arcs of the same layer and tool run are moved, to just after the last Arc block, so they rest on the Arcs.
- Fix the extruder counter and feed restored after relocated blocks (previously taken before the block's final reset).
- Fix the next-layer Hilbert option doing nothing: Orca opens a feature with retract, travel and unretract, and the retraction/unretract guards rejected every such feature. Hilbert jumps now retract and unretract around travel.
- New optional **Wave** overhang mode (`overhang_mode`, default `arc`), a Python/Shapely port of the algorithm in OrcaSlicer-WaveOverhangs (current main, including its PRs #114-#121): wavefront propagation with min-new-area, max-iterations and minimum-length limits, narrow-neck slit splitting (`wave_min_width_mm`), anchor fallbacks for thin supports, corner taper (`wave_corner_*`), deterministic polyline reconnection, and the Smart, ZigZag and Monotonic patterns (`wave_pattern`). Arc mode is unchanged.
- Wave emission settings: `wave_speed_mm_s` (2), `wave_travel_speed_mm_s` (40), absolute `wave_flow_mm3_per_mm` (0.15), speed capped by the filament's max volumetric speed, optional fan override, nozzle temperature override and minimum wave time (dwell), each restored after the wave block. Defaults follow WaveOverhangs and are untested on a printer.
- Wave seeds and bridge heuristic: seeds are the grown anchoring outline clipped to the cover, with the library's boundary clip as fallback; `wave_instead_of_bridges` (default on) can be turned off to leave spans the library would bridge (anchored on both sides or mostly convex) as the slicer's original Bridge.
- Wave floor layers, applied as G-code edits on the layers above a wave: `wave_perimeter_speed_mm_s` (walls next to the wave), `wave_floor_layers`, `wave_floor_print_speed_mm_s`, `wave_floor_perimeter_speed_mm_s`, `wave_floor_speed_ramp` (linear return to normal speed), Hilbert floor (`wave_floor_use_hilbert`, `wave_floor_hilbert_layers`, `wave_floor_hilbert_density_percent`) and part/auxiliary fan overrides on those layers. Also `wave_end_retract_mm` (retraction between wave lines) and `wave_min_layer_time_s` (dwell at the end of a layer with waves).
- Not ported: wave-aware support generation and forcing solid shell layers (both need the slicer; the plugin only edits finished G-code, so floor settings change speed/pattern of the layers Orca already made solid, not how many exist).
- New `z_hop_mm` (default 0 = off, behavior unchanged): lift Z for the travel between Arcs/Waves so the nozzle does not drag across freshly printed lines. Idea from jforbestyr/bambu-arc-overhang.
- Settings page keeps unsaved edits when switching tabs or windows (draft kept until Save or Refresh).
- Wave settings use the WaveOverhangs names and units ("Wave line spacing" in mm, default 0.35), each with a plain-language hint and its `wave_overhang_*` name.
- The page and README say that "Extra perimeters on overhangs" must be off for both modes; the G90/M83 error now reports the G-code line.
- README and settings page recommend "Bridge counterbore holes" = None: with "Partially bridged" Orca prints supported strips that the plugin skips (a counterbore test sliced that way produced no waves).
- Fixed "Requires G90 and relative extrusion (M83)" when the Hilbert floor was on: the floor scan read the start G-code purge line (absolute E). Start G-code is now skipped.
- Hilbert floor: leftover infill pieces shorter than one line width are dropped instead of getting their own retract and travel.
- Print time: after editing, the plugin shifts the M73 remaining-time lines and the "model printing time / total estimated time" header by the time the new toolpaths add or remove (estimate from length and feed rate; arcs count as chords).
- "Import a WaveOverhangs profile" box: paste the `; wave_overhang_*` lines (or the `WAVE_OVERHANG_CONFIG` line) from a waveoverhangs.com gallery entry; the fields fill in and stay unsaved until Save.
- Bridges that contain Orca's acceleration changes (`M204`) were skipped as "State command inside bridge region", so some models (for example a counterbore) got no waves or arcs at all. `M204` lines are now kept and the bridge is replaced.
- New `wave_aux_fan_override` / `wave_aux_fan_percent`: auxiliary fan (M106 P2) while printing waves, restored afterwards. Imported from `wave_overhang_aux_fan_speed`.
- The profile import no longer reports `wave_overhang_min_angle`, `spacing_mode`, `seam_mode`, `debug_gcode` and `outer_perimeters` as missing. In WaveOverhangs the first three do nothing, `debug_gcode` only adds comments, and `outer_perimeters` is covered by the walls Orca already printed.
- "Minimum overhang area" and "Minimum overhang length" moved from the Arc section to "Both modes" with help text: they gate Wave mode too, and lowering them (for example to 1-5 mm2) turns small overhangs into waves.
- Orca's Z hop (a printer setting) writes `G17` and a helical `G3 ... Z` lift between bridge lines. Those bridges, and walls or infill containing the same lift, were rejected as "State command inside bridge region", so no arcs or waves appeared on printers with Z hop (reported on the H2D profile). `G17` is now accepted. Reproduced by slicing the reported project with Z hop 0.4 mm: 0 of 2 bridges replaced before, 1 of 2 after (the other has full support).
- Tests: infill-first order, default order, Hilbert on a feature that opens with a retraction, Wave mode, time estimate, wave aux fan, `M204` inside a bridge and the spiral Z lift (55 total).

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
