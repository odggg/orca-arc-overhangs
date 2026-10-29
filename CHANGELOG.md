# Changelog

## 0.2.3 â€” 2026-10-24
- Repay tracked retraction during positive XY extrusion.
- Clear submicron wipe rounding residue after positive extrusion.
- Retain protection for genuinely unrecovered retraction at bridge boundaries.
- Add three regressions: 25 Python tests total.

## 0.2.1 â€” 2026-10-24
- Avoid lazy UTF-8 BOM codec imports that triggered repeated host permission prompts.
- Fix the sandboxed native configuration save button and asynchronous acknowledgement.
- Support G2/G3 input analysis, scarf contour recovery, M73 retention and geometric overhang detection.
- Show the last export report in the top tab.

## 0.2.0 â€” 2026-10-24
- Add a main-window Pages tab and shared configuration with preset override notices.

## 0.1.0 â€” 2026-10-24
- Initial experimental native OrcaSlicer 2.5 port with coverage checks and atomic export.

## 2026-10-29 local repair for 0.2.3

- Accept one distinct physical tool index even when it is non-zero; reject only multiple distinct physical tool indices.
- Keep Bambu virtual tool markers outside the physical-tool count.
- Add regression coverage for single-tool T1 and true multi-tool T1/T2 G-code.

