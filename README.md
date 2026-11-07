# Arc Overhang for OrcaSlicer 2.5

Native Arc Overhang plugin for OrcaSlicer 2.5, based on the integration by Kelsch, Nicolai Wachenschwan and Steven McCulloch. Current package version: 0.3.0 with the fixes recorded in [CHANGELOG.md](CHANGELOG.md).

## Current behavior

- Replace eligible, geometrically unsupported Bridge regions with concentric Arc paths.
- Keep the slicer's wall/infill order (including "Print infill first"); Overhang walls that would print before the Arcs are moved after them.
- Preserve material changes and use the active tool's nozzle, filament and flow settings.
- Support parameterless G10/G11 firmware retract commands.
- Choose Arc (default) or Wave overhang mode. Wave grows offset fronts outward from the supported edge, ported from [OrcaSlicer-WaveOverhangs](https://github.com/dennisklappe/OrcaSlicer-WaveOverhangs); it has now been printed once on a Bambu P1S with a good result. The exported G-code starts with the `WAVE_OVERHANG_BUILD` and `WAVE_OVERHANG_CONFIG` comment lines, so it can be uploaded to the waveoverhangs.com gallery.
- Adjust inner wall overlap independently from Arc spacing.
- Optionally select Hilbert infill for the next layer; the default keeps the slicer's pattern.

## Install and use

Use the generated wheel in [dist/](dist/) or the ZIP package in this repository. German setup and control descriptions are in [README_DE.md](README_DE.md). Check [VALIDATION.md](VALIDATION.md) for tested behavior and remaining limitations.

## Build and check

Requires Python 3.12 and Node.js for the UI bridge check.

```sh
python -m pip install -r requirements-dev.txt
python build_plugin.py
python tests.py
python test_audit.py
node test_tab.js
python package_release.py
```

Canonical source inputs are `adapter.py.in` and `upstream/`. `build_plugin.py` generates `dist/arc_overhang.py`; `package_release.py` creates the wheel and ZIP with a SHA-256 manifest. GitHub Actions runs the regression checks on pushes and pull requests.

## Project files

- `adapter.py.in`, `upstream/`: canonical adapter and upstream geometry.
- `dist/`, build scripts: generated plugin and distributable packages.
- `tests.py`, `test_audit.py`, `test_tab.js`, `test_ui.js`: regression and UI checks.
- `examples/`: synthetic G-code examples.
- `CHANGELOG.md`, `COMMUNITY_ISSUE_AUDIT.md`, `VALIDATION.md`: changes, reviewed reports and verification.

Private conversation exports, screenshots, local installation logs and printer files are retained in a separate local archive and are excluded from this repository's published history.

## License

GPL-3.0. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Orca setting required for both modes

The plugin only replaces extrusions Orca labels Bridge or Internal Bridge. Turn off **Extra perimeters on overhangs** (Quality tab, Overhangs section), otherwise Orca fills overhangs with extra walls and there is nothing to replace. Also set **Bridge counterbore holes** to **None** (Quality tab, Bridging section): "Partially bridged" makes Orca print supported straight strips, which the plugin leaves alone, while "None" leaves the hole as an overhang that gets arcs or waves.
