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
