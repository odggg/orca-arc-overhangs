# Arc Overhang 0.4.8

- Stop replaying unchanged nozzle temperatures when moving Arc and overhang paths.
- Restore the correct nozzle temperature after `M109 R` commands.
- Accept RepRapFirmware `G10` and `M568` temperature commands without treating them as retractions.
