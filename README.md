# Arc Overhang for OrcaSlicer 2.5

Native Arc Overhang plugin for OrcaSlicer 2.5, based on the integration by Kelsch, Nicolai Wachenschwan and Steven McCulloch. Current package version: 0.3.0 with the fixes recorded in [CHANGELOG.md](CHANGELOG.md).

## Install and use

Use [orca_arc_overhang-0.3.0-py3-none-any.whl](dist/orca_arc_overhang-0.3.0-py3-none-any.whl) or [the 0.3.0 ZIP](Arc_Overhang_OrcaSlicer_2.5_v0.3.0.zip). The stable single-file plugin is [dist/arc_overhang.py](dist/arc_overhang.py). German setup and control descriptions are in [README_DE.md](README_DE.md). Check [VALIDATION.md](VALIDATION.md) for tested behavior and remaining limitations.

The plugin edits G-code during export. The slicing preview does not show the change: reopen the exported file to inspect it.

## Required Orca settings (both modes)

The plugin only replaces extrusions Orca labels Bridge or Internal Bridge. If Orca fills an overhang entirely with extra walls, disable **Extra perimeters on overhangs** (Quality tab, Overhangs section) so that region can contain replaceable Bridge paths. For counterbore models, **Bridge counterbore holes → Partially bridged** can produce supported straight strips that the plugin intentionally retains. Try **None** (Quality tab, Bridging section) and inspect the exported G-code if generated support is wanted there.

## Current behavior

- Replace eligible, geometrically unsupported Bridge regions with concentric Arc paths.
- Select **Print order**: the default keeps the 0.2.4 order (normal walls/infill → Arcs/Waves → Overhang walls). The **Keep slicer order** option preserves normal wall/infill positions, including "Print infill first", and moves only early Overhang walls after the generated support. Neither option crosses a layer or tool-selection boundary.
- Preserve material changes and use the active tool's nozzle, filament and flow settings.
- Support parameterless G10/G11 firmware retract commands.
- Choose Arc (default) or Wave overhang mode. Wave grows offset fronts outward from the supported edge, ported from [OrcaSlicer-WaveOverhangs](https://github.com/dennisklappe/OrcaSlicer-WaveOverhangs). Wave mode is experimental; this review validates G-code processing, not physical print quality.
- Wave exports start with the `WAVE_OVERHANG_BUILD` and `WAVE_OVERHANG_CONFIG` comment lines, so they can be uploaded to the waveoverhangs.com gallery.
- Adjust inner wall overlap independently from Arc spacing.
- Optionally select Hilbert infill for the next layer; the default keeps the slicer's pattern.

## Build and check

Requires Python 3.12 and Node.js for the UI bridge check.

```sh
python -m pip install -r requirements-dev.txt
python build_plugin.py
python tests.py
python test_audit.py
node test_tab.js
python package_release.py
python test_package.py
```

Canonical source inputs are `adapter.py.in` and `upstream/`. `build_plugin.py` generates `dist/arc_overhang.py`, the `src/` mirrors and both HTML previews; `package_release.py` creates the wheel and ZIP with a SHA-256 manifest. GitHub Actions runs the regression checks on pushes and pull requests.

Private conversation exports, screenshots, local installation logs and printer files are retained in a separate local archive and are excluded from this repository's published history.

## License

GPL-3.0. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

The seven generated wheels use standard filenames and matching internal tags. Platform-specific host installation and the Orca Cloud download gate have not been verified by these local package tests. See [the PR #1 review](docs/PR1_REVIEW.md).
