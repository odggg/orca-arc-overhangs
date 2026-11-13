# Release validation — 0.4.0 (2026-11-13)

111 Python tests, rendered browser checks, native configuration-bridge checks,
restricted-file-access execution and universal-wheel/source-package validation
passed for this implementation. The 0.4.0 version and package are rechecked during
release preparation. Existing default toolpaths retain their version-normalized
regression baselines.

Coverage includes complete layer/region navigation, final-path animation, 2D/3D
views, filters, stale responses, material draft suggestions, local feed splitting,
extrusion conservation, tool boundaries, optional path strategies and conservative
removable-floor insertion/rejection.

Native Orca GUI slicing and physical print validation are still outstanding.
Material starting points are heuristic. Removable floors need clear undercut
space and can reject ordinary overhangs whose walls intersect the proposed floor.
All new print strategies are opt-in. See docs/WORKBENCH.md for precise limits.

## Earlier validation records

# Release validation - 0.3.2 (2026-11-12)

Publishing automation only: 14 standard-library tests cover release asset selection,
wheel integrity, release-event authentication, secret redaction and redirects.
The existing 0.3.1 GitHub wheel passed a real download/integrity dry run. Manual
upload was rejected by OrcaCloud (HTTP 401); uploads now require a release event.
The plugin source differs from 0.3.1 only in version metadata; existing regression,
package and browser checks remain required for this release.

# UI validation — 0.3.1 (2026-11-12)

70 Python regressions, both configuration bridge checks, the restricted file-access
audit, and the rendered local Chrome tests passed.

The new workbench retains every configuration key, both existing order choices
and the existing engine. Additional tests cover unique controls, bounded actual
export snapshots, version-normalised G-code comparisons in Arc/Wave with both
orders, omission of geometry from pipeline logs, and a safe fallback if rendering
data cannot be prepared.

Rendered browser tests use an actual synthetic export report and the generated
HTML. They exercise light/dark schemes, a 390 px viewport, all saved keys, mode
visibility, order selection, Hilbert-floor notices, drafts/reload, read-only state,
text injection resistance and absence of outbound requests. The native Orca
JavaScript bridge is checked separately. UI generation also passes the restricted
file-access audit without reading runtime template files.

The displayed 2D result is a simplified snapshot of the last export, not a claim
of current unsaved model state. Physical print quality remains outside this UI
review. See [UX design notes](docs/UX_DESIGN.md) for the original implementation.

## Prior 0.3.0 integration record

# Validation — Arc Overhang 0.3.0

Last updated: 2026-11-11.

## PR #1 integration checks

- Reviewed all 23 commits and the complete diff at PR head
  `79c5d71c96512687ff48ac7fdaebef15b504ba27`, including source, UI, tests,
  build/package scripts, generated files and documentation.
- All 56 original Python tests passed before integration. After review corrections,
  **66 Python regression tests passed**. They cover both print orders, modern/legacy
  feature tags, tool-selection boundaries, E/feed and modal restoration, Hilbert
  retraction/Z/density, Wave coverage/anchoring, fan channels and flow-aware caps.
- Both settings views passed their save tests, including the dropdown. The native
  configuration test uses the installed Orca JavaScript bridge in a VM; it is not
  a claim of interactive end-to-end WebView testing.
- Arc, Wave and next-layer Hilbert passed the audit-hook test with every file open
  outside the G-code working directory denied.
- Two existing real Orca exports (8.5 MB and 5.3 MB) were tested in Arc/Wave mode
  with both `layer_tail` and `slicer`: **eight successful processing cases**.
  Each case replaced one eligible Bridge, retained one unsuitable Bridge, produced
  one Hilbert infill replacement, preserved the final machine state within G-code
  rounding, and was unchanged when processed a second time.
- The two files produced 88/92 Arc paths or 196/194 Wave paths respectively.
  Actual Wave coverage was about 99.68%/100%; disconnected or insufficiently
  covered generated paths are rejected by regression tests.
- Release checks validate seven standard wheels, filename/internal-tag agreement,
  source bytes, metadata, RECORD hashes, generated mirrors/previews and the ZIP's
  SHA-256 manifest. A local universal-wheel install/import is also checked.

Detailed source files and per-run data remain in the ignored local evidence folder.
The public review record is [docs/PR1_REVIEW.md](docs/PR1_REVIEW.md).

## Remaining limits

- No physical print was performed during this review; Wave and Hilbert remain
  experimental. Automated coverage does not prove adhesion or absence of curling.
- The reported "Scale factor must be non-zero" failure and stock H2D timelapse
  failure have not been reproduced or confirmed resolved.
- A supposed one-wall-only restriction was not established. The PR author's
  H2D Z-hop fix is covered by a regression, not a physical printer session here.
- Time adjustments are estimates from length/feed; input G2/G3 are counted as
  chords and acceleration is not simulated.
- No cross-platform Orca host installation or Orca Cloud upload/download test.
- Only suitable Bridge regions are replaced. Hilbert does not alter top surfaces,
  sparse infill or ordinary Bridge infill on the following layer.

## Historical verification before 0.3.0

The following notes describe earlier releases and their then-current limits.

# Validation - Arc Overhang (0.2.4 era)

Last updated: 2026-10-30. Version 0.3.0 changes are not covered here; see CHANGELOG.md.

## Retraction regression retained from 0.2.2
The current G-code reproduced the previous exception with an apparent
0.00027 mm retract balance at both bridge boundaries. The old tracker only
repaid that balance on E-only commands, allowing rounded wipe residue to
accumulate even during positive XY extrusion. Fixed tracking yields zero
balance at both bridges. Three new tests cover XY repayment, submicron wipe
rounding and protection of genuinely unrecovered retractions.

## Reproduced user issues
- Installed Orca log shows utf-8-sig codec reads and transient pycache writes
  under Program Files, followed by denied audit events and failed processing.
- The same log shows processing rejected existing G2/G3 toolpaths.
- Installed native configuration iframe is sandboxed with allow-scripts only.
  The old plugin used a submit form; the new UI uses an ordinary button.
- The actual host saveConfig() returns undefined and confirms asynchronously
  through onConfig(). The new UI waits for that confirmation.

## Completed checks
- 25 Python regression tests passed.
- Separate audit-hook test passed: BOM input was successfully transformed while
  every file open outside the current G-code directory was rejected.
- JavaScript tests use the actual installed Orca plugin-config-ui.js bridge:
  preset and global scopes, button action, native asynchronous confirmation,
  timeout, read-only state and numeric validation.
- Main tab messaging tests passed, including rejected saves and profile overrides.
- API checked against OrcaSlicer v2.5.0-alpha source.

## Actual current Orca file
A local copy of the current approximately 8 MB G-code was processed.
The source has 401 layers, a 0.6 mm nozzle, scarf seams and no Overhang-wall
feature labels. It contains one Bridge and one Internal Bridge feature.
Result:
- One feature replaced at Z 57.54 mm with 88 arc toolpaths.
- Algorithm reports 100% geometric region coverage.
- Other bridge retained when eligibility/coverage checks did not pass.
- Every injected XY point lies inside the reconstructed current footprint.
- Original prefix and suffix outside the replacement are byte-equivalent text.
- M73 message count and final modal machine state preserved.
- Real source and transformed G-code are not included in this source package.

This validates transformation of the current file, not physical print quality.

## Remaining limits
- No physical print has been performed.
- Native Orca WebView clicking and save persistence have not been exercised
  end to end; the installed JavaScript bridge was tested in a VM.
- A headless Edge regression attempt could not start successfully in this
  environment, so no browser-rendering claim is made.
- No cross-platform host installation/upload testing.

## English UI in 0.2.3
All plugin UI and runtime messages translated to English. Configuration keys and defaults unchanged. Regression suite rerun for this release.

## Community issue review (2026-10-30)
- Reviewed the open issue list in the original integration repository; most reports
  target its legacy Prusa post-processing script rather than this Orca 2.5 port.
- Added support anchoring and path ordering for generated arcs. Every path must
  begin on prior-layer wall support or on an already-connected arc. Otherwise
  that Bridge feature stays byte-for-byte unchanged. Regression covers path order,
  reversal, isolated paths, and an isolated path mixed into a valid group.
- Existing regression coverage verifies active-tool material settings and
  preserving tool changes between Bridge features. Updated README_DE.md to remove
  the obsolete statement that multi-material is unsupported.
- 34 Python regression tests pass after the anchor change and four-tool check.
- Inner wall overlap now expands the bridge region toward all wall rings. Its
  configured distance can exceed the outer wall width; a synthetic ring test
  verifies that the expanded region can reach a deeper inner wall. 34 tests pass.
- Remaining limitations: issues without a reproducible G-code sample cannot be
  safely claimed fixed. In particular, repeated same-area overhang reports need
  a matching model/G-code reproducer to verify the previous layer's actual wall
  support. Hilbert infill is now an optional, experimental setting for eligible
  internal-solid-infill regions on the layer after a replaced Arc feature. It is
  off by default and has not been physically print-validated. See
  COMMUNITY_ISSUE_AUDIT.md for the per-report review.
- The Orca Cloud Plugin Hub page supplied later by the user was identified, but
  its comments endpoint returned `missing_authorization` outside an authenticated
  browser session. The user then supplied a screenshot; visible comments and
  their dispositions are recorded in COMMUNITY_ISSUE_AUDIT.md.
- Firmware retraction: parameterless G10/G11 are tracked as a balanced firmware-retract state. The 39-test suite covers a balanced pair, preservation of a Bridge feature containing retract commands, and rejection of parameterized G10.
- Corrected layer-tail scheduling: 39 regressions pass, including modern/legacy ordering of normal walls/infill, Arcs and Overhang walls, preserved Overhang extrusion geometry and layer/end-code boundaries. Tool-selection boundaries remain fixed.


## Preview overlays and process synchronization (unreleased)

- Python regression suite: 117 tests passed, including process override preservation,
  same-key replacement, rejected writes, profile switches and sidebar conflicts.
- Rendered browser checks cover full-layer default, collapsed controls, camera isolation,
  automatic apply, reverse synchronization, invalid inputs and host errors, and light/dark
  layouts at desktop and 390 px widths. Mock bridge responses exercise the protocol.
- Orca source references: [preset editor](https://github.com/OrcaSlicer/OrcaSlicer/blob/main/src/slic3r/plugin/host/PluginHostPresets.cpp),
  [UI-thread dispatch](https://github.com/OrcaSlicer/OrcaSlicer/blob/main/src/slic3r/plugin/host/PluginHostUi.cpp),
  [slice invalidation](https://github.com/OrcaSlicer/OrcaSlicer/blob/main/src/libslic3r/Print.cpp).
  The latter invalidates slicing for `print_plugin_config_overrides` changes.
- Native Orca GUI validation is outstanding. The locally installed binary did not
  contain the `PresetEditor` binding name during inspection, so this installation
  may require an Orca update for automatic tab-to-process synchronization. Runtime
  capability detection refuses unsupported writes; it never falls back to global defaults.
- Manual host acceptance: change a valid tab setting, verify the same value in the
  sidebar, confirm Orca's old Preview needs a new slice, then change it in the sidebar
  and verify the tab. Test a profile switch during editing and verify other plugins'
  overrides. Click Slice plate and verify both previews rebuild.
- No public host method to start slicing was found. The inline action applies settings
  and gives an explicit Slice plate instruction; it does not claim to launch slicing.
- Published 0.4.0 wheel and source ZIP remain unchanged by this development work.
