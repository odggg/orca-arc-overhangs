# Third-party notices
This adaptation is distributed under GNU GPL version 3; see LICENSE.

Original concept and implementation:
Steven McCulloch â€” https://github.com/stmcculloch/arc-overhang

PrusaSlicer integration:
Nicolai Wachenschwan â€”
https://github.com/nicolai-wachenschwan/arc-overhang-prusaslicer-integration

OrcaSlicer / SoftFever integration:
Kelsch â€” https://github.com/Kelsch/arc-overhang-orcaslicer-integration
Reference commit: 0693ef29a0eb3e96fdc336841cd714e071f3ed9a

The original softfever_slicer_post_processing_script.py and its LICENSE
are included unchanged in upstream/. The Arc class and geometric helper
functions are adapted from that file, retaining the concentric-circle and
breadth-first filling approach.

Changes dated 2026-10-24:
- Native Orca 2.5 capability registration and PEP 723 / wheel packaging.
- Noninteractive processing and host-owned configuration page.
- Modal G-code parser supporting modern and legacy Orca feature comments.
- Geometry reconstructed from extrusion segments rather than travel paths.
- Bounded per-feature replacement and current-contour clipping.
- Coverage threshold, independent wall overlap and arc spacing.
- Deterministic start selection; cancellation checkpoints.
- Removed plotting, console input and global warning-hook mutation.
- Fixed integer-index handling and zero-length-vector handling in helpers.
- Explicit retraction, G-code state restoration and atomic output.
- Regression tests and installation documentation.

Runtime dependencies are obtained by OrcaSlicer and are not bundled here:
NumPy (BSD-3-Clause) and Shapely (BSD-3-Clause, with GEOS notices in the
upstream distribution). OrcaSlicer itself is a separate project.

Version 0.2.0 adds an Orca Pages capability, shared configuration access,
request/reply messaging and regression tests for the new main-window tab.

Version 0.2.1 fixes UTF-8 BOM decoding, native sandboxed configuration actions
and asynchronous save acknowledgement, G2/G3 geometry analysis, M73 handling,
scarf contour recovery and geometric detection without wall role tags.
Runtime tests read the user's installed Orca JavaScript bridge; that third-party
file is not copied into this distribution.

Version 0.2.2 fixes retraction bookkeeping during XY extrusion and wipe rounding.

Version 0.2.3 translates the plugin UI and runtime messages to English.
