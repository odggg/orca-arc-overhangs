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

Validation: nine lifecycle integration tests cover automatic generation, unchanged
source bytes, disabled/error/binary input, invalidation, revision polling, resolved
settings and a stale in-flight result. The browser test exercises live preview
refresh without discarding an unsaved setting and checks that no visible UI text
requests an export. Existing 70 engine tests and native configuration-bridge tests
pass. The installed Orca binary contains the required lifecycle symbols.

Still required before release: an actual GUI slice with the plugin installed on
the supported Orca build, including any file-access permission behavior and timing.
The computer-control helper failed to start during development, so this host test
is not claimed. The existing eight-region simplified snapshot limit remains;
full layer navigation and print-progress animation are a separate pending change.
Third-party postprocessors that change the G-code later can differ from this
read-only preview. The lifecycle callback currently adds its calculation time to
slicing; cancellation invalidation is checked when observable by the plugin.
