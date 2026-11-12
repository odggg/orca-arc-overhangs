# Automatic slice preview (development)

The Arc Overhang tab no longer asks the user to export a file. Its sequence is:
enable the pipeline, slice the plate, inspect the generated support in the tab.

Orca emits GCodeExportFinished after closing and renaming its internal slice file,
even for an ordinary slice with no user-requested export. The handler reads that
successful event's path and runs the same process_text engine in memory. It never
writes the internal file or opens a Save dialog. Resolved settings are copied during
pipeline callbacks; no live slicing-graph references are retained.

The tab polls a lightweight revision/state endpoint every 1.5 seconds while visible.
Geometry is sent only when the revision changes; polling preserves settings drafts.
Slice starts, relevant model/plate/preset edits, successful settings saves and failed
or cancelled slices invalidate old geometry. Generation checks prevent an older
calculation from overwriting a later invalidation. The preset configuration dialog
hides the preview panel because only the main plugin tab has the report bridge.

Source evidence:
- https://github.com/OrcaSlicer/OrcaSlicer/blob/main/src/libslic3r/GCode.cpp
- https://github.com/OrcaSlicer/OrcaSlicer/blob/main/src/slic3r/GUI/BackgroundSlicingProcess.cpp
- https://github.com/OrcaSlicer/OrcaSlicer/wiki/lifecycle_events

Validation: ten lifecycle integration tests cover automatic generation, unchanged
source bytes, disabled/error/binary input, invalidation, revision polling, resolved
settings and a stale in-flight result. The browser test exercises live preview
refresh without discarding an unsaved setting and checks that no visible UI text
requests an export. Existing 70 engine tests and native configuration-bridge tests
pass. The installed Orca binary contains the required lifecycle symbols.

Still required before release: an actual GUI slice with the plugin installed on
the supported Orca build, including any file-access permission behavior and timing.
The computer-control helper failed to start during development, so this host test
is not claimed. The layer player now includes every generated Arc/Wave block; the previous
eight-region, 240-path and 10,000-point cutoffs are removed.
Third-party postprocessors that change the G-code later can differ from this
read-only preview. The lifecycle callback currently adds its calculation time to
slicing; cancellation invalidation is checked when observable by the plugin.

## Layer selection and print playback

The main tab offers a layer dropdown/slider, a region dropdown with tool and path
count, and previous/next overhang buttons spanning all layers. The catalogue
contains metadata for every generated block. Only the selected block's geometry
is transferred to the page; replies are bound to the current slice revision.
Late replies after a selection or slice change are discarded.

Play/Pause, Restart, a scrubber, 1x/5x/20x/100x speed, a nozzle marker and optional
travel lines show the selected block. The current extrusion is orange and completed
paths are green. Changing regions, invalidating a slice or hiding the tab stops
playback. The complete region is shown initially; Play starts from the beginning.

Motion data is extracted after final G-code scheduling, with exact emitted XYZ,
feed rates, retraction/unretraction moves, Z hops, approach/return travels and
explicit G4 dwell times. Time is an estimate from distance/feed, not a firmware
simulation with acceleration or temperature-wait prediction. The view is 2D; Z is
reported numerically. Model walls/infill outside the selected block are not animated.
Layer outlines remain simplified for context; support paths are not downsampled.

Four additional tests compare final motion coordinates and timing in both print
orders and Arc/Wave modes, cover Z hop and dwell, verify cancellation, and retain
18 regions across nine layers with 301 paths each (over 10,000 points). Browser
checks cover twelve selectable regions, lazy loading, playback/scrubbing, pause,
completion, layer slider, stale replies, travel visibility and invalidation.
