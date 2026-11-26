# Firmware report investigation — 2026-11-26

## Nozzle temperature falls to zero

Reproduced on 0.4.7 with a startup `M104 S0` followed by a heating macro:
reordering the synthetic bridge added five more `M104 T0 S0` commands. The
same problem occurred with `M109 R245`, whose target was not tracked.

Relocation now compares the source and destination thermal state and does not
replay unchanged temperatures. `M109 R` updates the recorded target. Wave's
optional temperature override requires a known, positive restoration target;
it leaves unknown, zero and multi-heater targets unchanged. Original startup,
shutdown and inactive-tool commands stay intact. Custom macro internals are
not interpreted. The reporter's actual G-code has not been supplied.

## RepRapFirmware G10

The parser previously rejected every parameterized G10. Temperature-only
`G10 P… S… R…` and `M568 P… S… R… A…` now preserve per-tool active/standby
settings, including colon-separated heater lists. They do not change the
firmware-retraction flag. Coordinate offsets, expressions and unknown parameters
remain unsupported. Temperature changes inside a bridge preserve the original
bridge instead of discarding those commands.

References: [Duet G-code dictionary](https://docs.duet3d.com/User_manual/Reference/Gcodes),
[Marlin M109](https://marlinfw.org/docs/gcode/M109.html).

## Centauri Carbon freezing / paths shown as travel

Not reproduced. A synthetic model using the stock profile's G90/M83 and
M104/M109 sequence generates positive relative E moves with recovered
retractions in both the basic and refined Arc emitters. This is an output
check, not a physical Centauri print or validation of a third-party viewer.

The reported freeze remains open: the affected G-code, firmware version and
viewer name are needed to establish its cause. No extrusion-mode or path
changes were made on the assumption that this report shares the temperature
bug.

Profile inspected: [OrcaSlicer Centauri Carbon 0.4 nozzle](https://github.com/OrcaSlicer/OrcaSlicer/blob/main/resources/profiles/Elegoo/machine/ECC/Elegoo%20Centauri%20Carbon%200.4%20nozzle.json).

`tests/test_firmware_compatibility.py` checks the thermal state at actual
extrusions, both print orders, original heater-off commands, RRF updates,
Wave temperature restoration and generated extrusion/retraction balance.
