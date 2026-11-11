# Arc Overhang 0.3.0

Cumulative update from 0.2.4, integrating PR #1 with review corrections.

- Choose the print order: keep the previous layer-tail order (default), or respect
  the slicer wall/infill order while placing early Overhang walls after the support.
- Fix Hilbert being skipped on features that begin with retract/travel/unretract.
  Keep approach/departure Z hops, progress markers, and balanced retraction.
- Correct Hilbert density so lower density reduces the deposited material.
- Accept G17/helical Z-hop travel and M204 in otherwise eligible Bridge blocks.
- Add optional experimental Wave support with pattern, floor, flow, fan and
  temperature controls and a pasted-profile importer.
- Preserve active-tool settings, motion state, fan channels and acceleration when
  relocating blocks. Check actual Wave coverage and anchored starts.
- Update remaining-time estimates approximately after editing toolpaths.
- Build valid wheels for the supported platform tags and verify package contents.

The slicing preview precedes post-processing: reopen the exported G-code to inspect
changes. Hilbert applies to eligible internal solid infill above generated support;
top surfaces, sparse infill and ordinary Bridge infill are retained.

Physical print quality, cross-platform host installation, and Orca Cloud downloads
have not been validated here. The reported scale-factor and stock timelapse issues
remain unconfirmed. See VALIDATION.md for the checks performed.
