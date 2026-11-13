# Workbench extensions (development)

All print-affecting additions are opt-in. Existing profiles retain their current
output. No release is implied by this development branch.

## Inspect a slice

Select an overhang layer and region. The default view animates that support block.
Full layer playback includes the actual final walls, infill, other feature types,
support blocks, tool changes as tool metadata, and travel in their emitted order.
The view does not simulate tool docking macros or firmware acceleration.

Toggle individual path types and the previous layer. Switch to 3D orthographic
projection to inspect actual XYZ coordinates. Drag to orbit, Shift-drag to pan,
and scroll to zoom. The reset button restores the camera. 2D uses drag to pan.
Filtering affects visibility only; playback time still follows the entire sequence.

Only the selected layer and previous-layer context are transferred with a region
request. Geometry is excluded from polling catalogues. Stale replies remain
revision-scoped. Layers needed by multiple regions share context in memory.

Per-region results list the layer, outcome, geometric target area and generation
coverage or the reason the original region was kept. The selected preview also
reports the deposited footprint (union of nozzle-width strokes), path count and
estimated time change. Generation coverage is measured before optional endpoint
coasting. It is not a guarantee of physical support or adhesion. The model outline
is simplified; fitted G2/G3 paths are tessellated at 0.01 mm tolerance for display.

## Explanations and material starting points

Project-authored SVG drawings explain inner-wall overlap, path spacing, vertical
separation, print order and the local slowdown. They respond to settings and have
an optional replay that respects reduced-motion preferences. These are concepts,
not simulations of the current model.

Material suggestions are computed per tool from available filament family,
nozzle, layer height, fan limit and maximum volumetric flow. They are heuristics,
not calibrated presets. Applying a suggestion changes the draft only; it does
not enable removable floors or adaptive path ordering. Plugin settings are shared,
so multi-material users must review every tool before saving. Unknown materials
are explicitly labelled. No material data is sent over the network.

## Local slowdown

Set a positive number of layers above support and a speed percentage. Extrusion
paths are split at generated-support footprint boundaries; the original feed and
extruded volume are preserved outside those regions. Matching is per physical
tool. Travels, nonplanar extrusion and support blocks remain unchanged. Straight
segments retain their geometry; affected fitted arcs become linear segments with
0.01 mm chord tolerance. Explicit feed restoration prevents slowdown leaking into
later paths. Existing Wave floor settings are applied first; the additional
percentage therefore also scales an already reduced feed when both are enabled.

## Adaptive printing (experimental)

- Prefer stronger supported start candidates for Arc generation. Reorder eligible
  paths using deposited support and branch proximity, preserving the engine order
  if no attachment can be established.
- Limit support acceleration only when a previous M204 state can be restored.
- Override the known model-fan channel and optionally use separate cooling and
  flow for the first N paths. Unknown fan state is left unchanged.
- Reduce speed with distance from the first generated path. This is a geometric
  heuristic, not a thermal model. Volumetric limits include the adjusted flow.
- Optional minimum path time adds a dwell when printing a path finishes sooner.
- Coast only near isolated path ends, limited to 10% of the path length.
- Optional wipe follows the preceding polyline backwards after retracting; it
  never takes a straight shortcut across a curved path.
- Skip retract/lift only for short connectors contained in the deposited footprint.

Incoming extrusion mode, E coordinate, feed, fan and acceleration are restored.
These strategies need real prints across filament, nozzle and cooling conditions.

## Removable floors (experimental and conservative)

The original model Bridge paths are retained. A separate floor is inserted after
layer n-2, at Z = target layer Z - nominal layer height - peel gap, before the
intervening model layer exists. Its extrusion is scaled by the available vertical
height. Thus the original model's coordinates remain unchanged.

The planner requires uniform local layer heights, two earlier layers, supported
anchors, adequate coverage, a compatible tool and unretracted insertion state.
It checks the floor footprint against every tool's extrusion on the intervening
layer and against other floors. A collision or uncertain state leaves the model
unchanged with a reason. No tool switch is introduced.

This conservative mode currently serves clear undercut geometries. It can reject
ordinary overhangs whose continuous wall intersects the proposed floor anchoring;
it does not remove wall material to force a floor into place. Gap, adhesion and
peelability are not physically validated. Cancellation propagates without writing
partial output. UI snapshot failure does not invalidate successfully generated code.

## Validation before release

Automated tests cover layer roles, curves, previous-layer context, bounded metadata,
profile/tool selection, feed splitting and extrusion conservation, state restoration,
flow limits, removable insertion and collision rejection. Browser tests cover
context filters, 3D projection, whole-layer playback, draft suggestions, settings,
responsive layout, accessibility states and stale-result protection.

Still required: direct slicing in the supported Orca GUI and actual print tests.
The local native UI automation helper is unavailable in this development session.
