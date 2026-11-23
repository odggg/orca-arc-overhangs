# Arc Overhang 0.4.3

- Choose a material for starting points independently of Orca's filament profile.
- Request preview file access and offer a retry if access is denied.
- Fix skipped Klipper bridges with `SET_VELOCITY_LIMIT` and preserve motion limits when moving toolpaths.
- Recognize compact G-code moves such as `G1E-.6F1800`.
- Keep Orca's original paths when a bridge geometry error would otherwise abort the export.
