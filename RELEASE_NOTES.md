# Arc Overhang 0.4.0

- Automatic preview after slicing: no manual export is needed to inspect generated support.
- Browse every Arc/Wave region by layer, height and tool, with previous/next navigation.
- Play, pause, restart and scrub the actual print sequence for a selected region or the entire layer, with adjustable speed and optional travel paths.
- Inspect full-layer context and the previous layer in 2D or an interactive 3D orthographic view; filter individual path types.
- View region areas, generation coverage, deposited footprints, estimated time changes and reasons for skipped regions.
- New parameter illustrations and material-based starting points that can be applied to a settings draft.
- Optional local slowdown above generated support, preserving extrusion and restoring normal feed outside the affected area.
- Optional stronger-anchor/branch ordering, support acceleration, initial flow and cooling, distance-based speed, minimum path time, endpoint coasting, curved wipes and short supported connectors.
- Experimental removable floors retain the original model paths and reject insufficient clearance, conflicting tools and intervening-layer collisions.
- Improved stale-preview handling and full-layer playback reset. Existing print defaults remain unchanged.

Validation: 111 Python tests plus browser, configuration-bridge, file-access and package checks. Native Orca GUI slicing and physical print tests remain outstanding. New print strategies are opt-in; removable floors currently require clear undercut space. Material suggestions are starting points, not calibrated profiles.

Only the universal py3-none-any WHL is attached. GitHub publishing uploads this same file to Orca Cloud automatically.

Thanks to @persano for the contributed print-order and Hilbert fixes, Wave mode and other improvements included in earlier releases. Arc concept and integration credits: Steven McCulloch, Nicolai Wachenschwan and Kelsch.
