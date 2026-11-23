SET_VELOCITY_LIMIT ACCEL=11000 ; adjust VELOCITY_LIMIT(accel/jerk)
G1E-.6F1800 ; retract
G1Z6.1F36000 ; normal lift Z
G1X113.47Y36.354Z6.1 ; move to first infill (bridge) point
G1Z6 ; reset Z after contouring
G1E.6F1800 ; unretract
SET_VELOCITY_LIMIT ACCEL=3000 ; adjust VELOCITY_LIMIT(accel/jerk)
