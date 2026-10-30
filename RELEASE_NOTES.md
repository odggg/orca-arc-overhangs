# Arc Overhang

Print suitable overhang regions with concentric arc toolpaths using OrcaSlicer's native slicing pipeline.

## Features
- Arc Overhang tab in the main window.
- Adjustable speed, spacing, flow, wall anchoring and retraction.
- Process preset configuration and global defaults.
- G2/G3 input support: Arc Fitting can remain enabled.
- Unsuitable bridge regions stay unchanged.

## Setup
Enable both Pages and Slicing Pipeline capabilities. In advanced mode, select Arc Overhang under Process > Others > Slicing Pipeline Plugin and save the process preset. Disable support for the intended arc overhang area.

The plugin modifies G-code during export. Reopen exported G-code to inspect the result; the original slicing preview does not show these changes.

## Compatibility and status
Experimental version 0.2.4. Requires OrcaSlicer 2.5.0 or later with native Python plugin support.
Initial release target: Windows x86-64. API checked against v2.5.0-alpha; later API changes may need adjustments.

Requires absolute XYZ (G90), relative extrusion (M83), single-tool text G-code and reconstructable contours.
NumPy and Shapely are installed by Orca. No physical print has been validated.

## Credits
Based on Kelsch's Orca integration and work by Nicolai Wachenschwan and Steven McCulloch.
Independent adaptation; not an official OrcaSlicer project. GNU GPL version 3.

Original integration: https://github.com/Kelsch/arc-overhang-orcaslicer-integration

## Changes in 0.2.4

Release identifier and package filenames updated for Orca Cloud. Plugin behavior is unchanged from the current GitHub source.

## Changes in 0.2.3

All plugin UI labels, help text, status messages, errors and skip reasons are now English. Configuration keys, saved settings and printing behavior remain unchanged.

## Retraction fixes retained from 0.2.2

Fix retraction tracking during XY extrusion and tiny wipe rounding residue. Genuine unrecovered retraction remains protected.

## Assets

Install dist/arc_overhang.py from the source ZIP or install through the catalog. Install one variant only.
