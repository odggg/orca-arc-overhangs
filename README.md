# Arc Overhang for OrcaSlicer 2.5

A local, rebuildable archive of the Arc Overhang plugin, including the 0.2.3 source and release files, the single-tool detection repair, regression tests, original working assets, relevant Orca logs, and the related Cloud chat context.

## Current repair

The parser now supports real multi-material tool changes. Each Bridge feature uses the active tool's nozzle, filament diameter, line width and flow ratio; the slicer's T commands remain in place. A single Bridge feature that changes tools internally is left untouched. Bambu virtual markers (T0, T255, T1000) remain handled separately.

The installed OrcaSlicer copy was registered as 0.2.2. Its original module and wheel are preserved under evidence/installed-v0.2.2/; the patched installed copy is preserved there too. The corrected 0.2.3 source is the canonical rebuild source in adapter.py.in plus upstream/.

## Rebuild

Use Python 3.12 and the packages in requirements-dev.txt.

    python build_plugin.py
    python -m pip install -r requirements-dev.txt
    python tests.py
    python package_release.py

The installable script is dist/arc_overhang.py. The wheel and Orca plugin ZIP are generated into dist/ and the repository root. The package includes a SHA-256 manifest.

## Repository layout

- adapter.py.in, upstream/: canonical source inputs.
- dist/, build_plugin.py, package_release.py: generated plugin and rebuild steps.
- tests.py, examples/, fixtures/: regression suite and saved G-code evidence.
- release/: earlier 0.1.0–0.2.3 packages as found in the prior workspace.
- evidence/: installed 0.2.2 originals, repaired files, and relevant log excerpt.
- docs/cloud-chat-transcript.md: export of the related cloud conversation and attachment notes.
- archive/legacy-workspace/: prior working files and both publish trees, excluding temporary browser profiles and vendored Python test dependencies.

This repository is local-only; no remote was configured. A Git bundle and ZIP snapshot are stored beside the repository.


The next-layer infill pattern is selectable: keep Orca’s original pattern by default, or use the optional Hilbert curve in eligible internal solid infill above replaced Arc regions. Hilbert can increase print time; unrelated infill is preserved.
