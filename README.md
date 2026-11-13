# Arc Overhang for OrcaSlicer 2.5

Native Arc Overhang plugin for OrcaSlicer 2.5, based on the integration by Kelsch, Nicolai Wachenschwan and Steven McCulloch. Current package version: 0.4.1 with the fixes recorded in [CHANGELOG.md](CHANGELOG.md).

## Install and use

Use [orca_arc_overhang-0.4.1-py3-none-any.whl](dist/orca_arc_overhang-0.4.1-py3-none-any.whl) or [the 0.4.1 ZIP](Arc_Overhang_OrcaSlicer_2.5_v0.4.1.zip). The single-file plugin is [dist/arc_overhang.py](dist/arc_overhang.py). German setup and control descriptions are in [README_DE.md](README_DE.md). Check [VALIDATION.md](VALIDATION.md) for tested behavior and remaining limitations.

The preview calculates support automatically when Orca finishes slicing. Open the Arc Overhang tab to inspect the result; no manual file export is required for this view. Final G-code processing still runs through the configured pipeline. Native Orca GUI validation and physical print testing remain outstanding; see VALIDATION.md.

Version 0.4.1 also includes full-layer playback and filters, a 3D orthographic
view, per-region diagnostics, material starting points, local slowdown and opt-in
experimental print strategies. See [Workbench extensions](docs/WORKBENCH.md) for
controls, safety checks and known limits. New print strategies are opt-in and experimental.

## Required Orca settings (both modes)

The plugin only replaces extrusions Orca labels Bridge or Internal Bridge. If Orca fills an overhang entirely with extra walls, disable **Extra perimeters on overhangs** (Quality tab, Overhangs section) so that region can contain replaceable Bridge paths. For counterbore models, **Bridge counterbore holes → Partially bridged** can produce supported straight strips that the plugin intentionally retains. Try **None** (Quality tab, Bridging section) and inspect the exported G-code if generated support is wanted there.

## The graphical workbench

- **Overview** opens the full selected layer in 2D or 3D, including walls,
  infill and generated support. Individual support regions remain selectable.
- Path visibility, view options and layer/print playback sit in translucent,
  collapsible overlays inside the viewport. The narrow layout starts with the
  path legend collapsed. Light and dark themes are supported.
- **Fine tuning** groups advanced controls; **How it works** explains them with
  original schematics, separate from the actual sliced geometry.
- On Orca builds exposing `orca.host.preset.process.update`, valid tab edits
  apply to the active process after a short typing pause. Sidebar changes are
  polled back into the tab. Conflicting drafts require a reload instead of
  overwriting newer settings or a different profile.
- Applying writes the process's `print_plugin_config_overrides` through Orca's
  setting-change API, so the sidebar refreshes and Orca invalidates the old
  slice. Other plugins' overrides and global defaults are preserved.
- The preview shows an **Apply changes** action for pending edits and tells you
  to click **Slice plate** after applying. The public plugin API does not expose
  an action to start slicing: this is not a one-click reslice button.
- Older Orca builds without the process editor must use **Plugin Configuration**
  in the sidebar. The tab reports that limitation and refuses a misleading
  global-default save. Native host integration still needs an in-app test;
  mocked bridge tests do not establish compatibility with every Orca 2.5 build.

The preview includes layer/overhang selection, Play/Pause, Restart, a progress
slider, playback speed, nozzle position and optional travel paths. Motion follows
the generated G-code, with estimated movement timing. Geometry loads on demand.
No remote fonts, licence checks or network calls are added.

All UI code and graphics were created for this project. See [UX design notes](docs/UX_DESIGN.md).

## Current behavior

- Replace eligible, geometrically unsupported Bridge regions with concentric Arc paths.
- Select **Print order**: the default keeps the 0.2.4 order (normal walls/infill → Arcs/Waves → Overhang walls). The **Keep slicer order** option preserves normal wall/infill positions, including "Print infill first", and moves only early Overhang walls after the generated support. Neither option crosses a layer or tool-selection boundary.
- Preserve material changes and use the active tool's nozzle, filament and flow settings.
- Support parameterless G10/G11 firmware retract commands.
- Choose Arc (default) or Wave overhang mode. Wave grows offset fronts outward from the supported edge, ported from [OrcaSlicer-WaveOverhangs](https://github.com/dennisklappe/OrcaSlicer-WaveOverhangs). Wave mode is experimental; this review validates G-code processing, not physical print quality.
- Wave exports start with the `WAVE_OVERHANG_BUILD` and `WAVE_OVERHANG_CONFIG` comment lines, so they can be uploaded to the waveoverhangs.com gallery.
- Adjust inner wall overlap independently from Arc spacing.
- Optionally select Hilbert infill for the next layer; the default keeps the slicer's pattern.

## GitHub to OrcaCloud publishing

Published stable GitHub releases can upload their exact universal WHL and release notes to OrcaCloud automatically. Connect the repository once in OrcaCloud; no stored API key is needed. See [publishing setup and manual validation](docs/GITHUB_PUBLISHING.md).

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
pnpm install --frozen-lockfile --ignore-scripts
pnpm exec playwright install chromium
pnpm test:ui
```

Canonical source inputs are `adapter.py.in` and `upstream/`. `build_plugin.py` generates `dist/arc_overhang.py`, the `src/` mirrors and both HTML previews; `package_release.py` creates the wheel and ZIP with a SHA-256 manifest. GitHub Actions runs the regression checks on pushes and pull requests.

Private conversation exports, screenshots, local installation logs and printer files are retained in a separate local archive and are excluded from this repository's published history.

## License

GPL-3.0. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

New builds produce one standard universal wheel. NumPy and Shapely supply their own platform dependencies. Cross-platform host installation and the Orca Cloud download gate have not been verified by the local package tests. See [the PR #1 review](docs/PR1_REVIEW.md).
