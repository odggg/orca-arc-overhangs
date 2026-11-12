# Arc Overhang 0.3.1

An independent graphical workbench for the existing Arc and Wave engine.

- New Overview, Fine tuning and How it works views.
- Essential settings first, all 60 controls retained, and mode-specific advanced
  sections that keep the other mode's saved values.
- Local 2D snapshots of generated support from the last export, with region
  selection, layer/tool information and a notice when settings have changed.
- Original explanatory SVG graphics, clearly separate from export data.
- A sticky save bar, asynchronous save confirmation, read-only feedback,
  accessible keyboard focus, responsive layout and light/dark themes.
- No added network calls, remote assets or activation requirements.
- One universal `py3-none-any.whl` package.

This update preserves the existing print order choices and toolpath generation.
The snapshot is simplified and limited to eight regions; reopen the exported
G-code for complete inspection. It does not monitor unsaved model edits.

Arc concept: Steven McCulloch, Nicolai Wachenschwan and Kelsch. Thanks to
**@persano** for PR #1 and the earlier Wave/Hilbert improvements.
