# Contributing

Run the checks in README.md before submitting changes.
Edit adapter.py.in and build_plugin.py rather than the generated dist/arc_overhang.py.
Keep the upstream source and license unchanged. Describe modifications in THIRD_PARTY_NOTICES.md.
Include a synthetic regression fixture for parser or geometry fixes.

For bugs, provide Orca version, OS, plugin version, error text, relevant settings and a minimal reproduction.
Remove account data, printer access codes and private paths from logs.

## Project files

- `adapter.py.in`, `upstream/`: canonical adapter and upstream geometry.
- `dist/`, build scripts: generated plugin and distributable packages.
- `tests.py`, `test_audit.py`, `test_tab.js`, `test_ui.js`: regression and UI checks.
- `examples/`: synthetic G-code examples.
- `CHANGELOG.md`, `COMMUNITY_ISSUE_AUDIT.md`, `VALIDATION.md`: changes, reviewed reports and verification.

UI sources live in `ui/` and are embedded by `build_plugin.py`; do not edit generated previews directly. Run `pnpm install --frozen-lockfile --ignore-scripts`, `pnpm exec playwright install chromium` and `pnpm test:ui` after `python tests.py` for rendered browser checks. Reference images and real printer data stay in ignored local evidence.
