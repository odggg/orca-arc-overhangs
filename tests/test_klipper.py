"""Synthetic regression for the reported layer-30 Klipper bridge; no private model."""
import re
import runpy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "test-deps"), str(ROOT / "dist")]
import arc_overhang as a
fixture = runpy.run_path(str(ROOT / "tests.py"))["fixture"]
TRAVEL = (ROOT / "examples/klipper_bridge_travel.gcode").read_text()


def screenshot_fixture():
    source = fixture("legacy")
    source = re.sub(r"([XY])([0-9.]+)", lambda m: m[1] + f"{float(m[2]) + (94 if m[1] == 'X' else 20):g}", source)
    source = source.replace("G1 Z0.2", "G1 Z5.8").replace("G1 Z0.4", "G1 Z6")
    source = source.replace(";LAYER_CHANGE", ";LAYER_CHANGE\n" * 28 + ";LAYER_CHANGE", 1)
    lines, inside, strokes = [], False, 0
    for line in source.splitlines(True):
        if line.startswith(";TYPE:"):
            inside = line.strip() == ";TYPE:Bridge"
        lines.append(line)
        if inside and "E0.15" in line:
            strokes += 1
            if strokes in (4, 24):
                lines.append(TRAVEL)
    return ("SET_VELOCITY_LIMIT VELOCITY=250 ACCEL=3000 SQUARE_CORNER_VELOCITY=5 MINIMUM_CRUISE_RATIO=0.5\n"
            + "".join(lines).replace(";TYPE:Sparse infill", "SET_VELOCITY_LIMIT ACCEL=6000\n;TYPE:Sparse infill")
            + ";TYPE:Custom\nG1 F1300\n")


def limits_at_moves(text):
    """Independent oracle for effective Klipper limits, not the plugin's modal parser."""
    limits, result = {}, {}
    for index, line in enumerate(text.splitlines()):
        code = line.split(";", 1)[0].strip().upper()
        if code.startswith("SET_VELOCITY_LIMIT "):
            limits.update({key: float(value) for key, value in re.findall(r"([A-Z_]+)=([+\-0-9.E]+)", code)})
        elif code.startswith("M204 "):
            values = {k: float(v) for k, v in re.findall(r"([SPT])([+\-0-9.]+)", code)}
            if "S" in values:
                limits["ACCEL"] = values["S"]
            elif "P" in values and "T" in values:
                limits["ACCEL"] = min(values["P"], values["T"])
        if re.match(r"G[01](?=\s|[XYZEF]|$)", code):
            result[index] = dict(limits)
    return result


class KlipperTests(unittest.TestCase):
    def test_compact_screenshot_moves_and_partial_limits(self):
        self.assertEqual(a.command("G1E-.6F1800"), ("G1", {"E": -.6, "F": 1800}))
        self.assertEqual(a.command("G1Z6.1F36000"), ("G1", {"Z": 6.1, "F": 36000}))
        self.assertEqual(a.command("set_velocity_limit accel=3e3 ; comment"), ("SET_VELOCITY_LIMIT", {"ACCEL": 3000}))
        source = screenshot_fixture()
        bridge = next(f for f in a.parse(source.splitlines(True)) if f.role == "bridge")
        self.assertEqual(bridge.layer, 29)
        self.assertEqual(sum(source.splitlines()[i].startswith("SET_VELOCITY_LIMIT") for i in range(bridge.moves[0].index, bridge.moves[-1].index + 1)), 4)
        self.assertEqual(bridge.moves[-1].after.z, 6)
        self.assertFalse(a.is_retracted(bridge.moves[-1].after))

    def test_screenshot_bridge_replaced_in_both_modes_and_orders(self):
        source = screenshot_fixture()
        original = a.parse(source.splitlines(True))
        expected_limits = limits_at_moves(source)
        for mode in ("arc", "wave"):
            for order in a.CHOICES["print_order"]:
                with self.subTest(mode=mode, order=order):
                    output, report = a.process_text(source, {"overhang_mode": mode, "print_order": order, "minimum_coverage_percent": 80})
                    self.assertEqual(report["replaced_features"], 1, report)
                    self.assertGreater(report["generated_arcs"], 5)
                    self.assertNotIn("State command inside bridge region", report["skip_reasons"])
                    self.assertEqual(a.process_text(output)[0], output)
                    actual = a.parse(output.splitlines(True))
                    actual_limits = limits_at_moves(output)
                    original_end, actual_end = original[-1].moves[-1].after, actual[-1].moves[-1].after
                    self.assertAlmostEqual(actual_end.e, original_end.e, places=6)
                    self.assertEqual(a.replace(actual_end, e=0), a.replace(original_end, e=0))
                    # Every untouched wall and infill extrusion keeps its effective limits.
                    by_line = {}
                    for f in actual:
                        for m in f.moves:
                            if a.segment(m) is not None:
                                by_line.setdefault(output.splitlines()[m.index], []).append(actual_limits[m.index])
                    for f in original:
                        if f.role == "bridge":
                            continue
                        for m in f.moves:
                            if a.segment(m) is not None:
                                self.assertIn(expected_limits[m.index], by_line[source.splitlines()[m.index]])
                    arc_moves = [m for f in actual if f.role == "bridge" for m in f.moves if a.segment(m) is not None]
                    self.assertTrue(arc_moves)
                    for m in arc_moves:
                        self.assertEqual(actual_limits[m.index], {"VELOCITY": 250, "ACCEL": 3000, "SQUARE_CORNER_VELOCITY": 5, "MINIMUM_CRUISE_RATIO": .5})

    def test_refined_arcs_use_and_restore_klipper_acceleration(self):
        for order in a.CHOICES["print_order"]:
            with self.subTest(order=order):
                output, report = a.process_text(screenshot_fixture(), {"print_order": order, "support_acceleration_mm_s2": 250})
                self.assertEqual(report["replaced_features"], 1, report)
                states = limits_at_moves(output)
                parsed = a.parse(output.splitlines(True))
                arc_moves = [m for f in parsed if f.role == "bridge" for m in f.moves if a.segment(m) is not None]
                self.assertTrue(arc_moves)
                for move in arc_moves:
                    self.assertEqual(states[move.index]["ACCEL"], 250)
                self.assertEqual(states[parsed[-1].moves[-1].index]["ACCEL"], 6000)
                self.assertNotIn("M204", output)

    def test_compact_move_time_matches_spaced_gcode(self):
        compact = ["G1X0Y0F600", "G1X10Y0F600", "G4P500"]
        spaced = ["G1 X0 Y0 F600", "G1 X10 Y0 F600", "G4 P500"]
        self.assertEqual(a.move_seconds(compact), [0, 1, .5])
        self.assertEqual(a.move_seconds(compact), a.move_seconds(spaced))

    def test_partial_limits_and_m204_restore_in_command_order(self):
        source = ("G90\nM83\n;LAYER_CHANGE\n;TYPE:Custom\n"
                  "SET_VELOCITY_LIMIT VELOCITY=180 ACCEL=3000 SQUARE_CORNER_VELOCITY=4 MINIMUM_CRUISE_RATIO=.4\n"
                  "M204 S700\nSET_VELOCITY_LIMIT VELOCITY=220\nG1 X1 Y1 Z6 E.1\n"
                  "SET_VELOCITY_LIMIT ACCEL=900\nG1 X2 Y1 E.1\n"
                  "M204 P400 T600\nG1 X3 Y1 E.1\n")
        moves = a.parse(source.splitlines(True))[0].moves
        expected = limits_at_moves(source)
        for move in moves:
            relocated = "".join(a.relocate_travel(move.after, a.configuration(), a.State()))
            actual = limits_at_moves(relocated)
            self.assertEqual(actual[max(actual)], expected[move.index])
        self.assertEqual(dict(moves[0].before.modal)["acceleration"], "M204 S700\n")
        self.assertEqual(dict(moves[1].before.modal)["acceleration"], "SET_VELOCITY_LIMIT ACCEL=900\n")

    def test_hilbert_and_retiming_preserve_motion_limits(self):
        source = ("G90\nM83\nSET_VELOCITY_LIMIT ACCEL=500 VELOCITY=250\n"
                  ";LAYER_CHANGE\nG1 Z6\n;TYPE:Internal solid infill\nG1 X11 Y11 F1800\n"
                  "G1 X19 Y11 E0.5\nSET_VELOCITY_LIMIT ACCEL=900\nG1 X19 Y19 E0.5\n")
        lines = source.splitlines(True)
        feature = a.parse(lines)[0]
        replacement = a.hilbert_feature_replacement(
            feature, lines, a.Polygon([(10, 10), (20, 10), (20, 20), (10, 20)]),
            a.configuration(), a.printer_settings(fixture().splitlines()), lambda: False)
        self.assertIsNotNone(replacement)
        for body in (replacement, a.retime_feature(feature, lines, lambda move: 10)):
            self.assertIsNotNone(body)
            output = "".join(lines[:feature.start] + body)
            state = limits_at_moves(output)
            self.assertEqual(state[max(state)], {"ACCEL": 900, "VELOCITY": 250})

    def test_overhang_wall_internal_limits_survive_relocation(self):
        source = screenshot_fixture().replace("G1 X124 Y50 E0.5\n;TYPE:Bridge",
                    "G1 X124 Y40 E0.25\nSET_VELOCITY_LIMIT ACCEL=1200\nG1 X124 Y50 E0.25\n;TYPE:Bridge")
        self.assertIn("SET_VELOCITY_LIMIT ACCEL=1200", source)
        original_limits = limits_at_moves(source)
        for order in a.CHOICES["print_order"]:
            output, report = a.process_text(source, {"print_order": order})
            self.assertEqual(report["replaced_features"], 1, report)
            actual_limits = limits_at_moves(output)
            for wall_line in ("G1 X124 Y40 E0.25", "G1 X124 Y50 E0.25"):
                self.assertEqual(actual_limits[output.splitlines().index(wall_line)],
                                 original_limits[source.splitlines().index(wall_line)])

    def test_unknown_or_invalid_commands_keep_original_bridge(self):
        for command in ("SET_VELOCITY_LIMIT ACCEL=3000 UNKNOWN=1", "SET_VELOCITY_LIMIT ACCEL_TO_DECEL=1500",
                        "SET_VELOCITY_LIMIT ACCEL=nan", "SET_VELOCITY_LIMIT ACCEL=1e999", "SET_VELOCITY_LIMIT ACCEL=0",
                        "SET_VELOCITY_LIMIT MINIMUM_CRUISE_RATIO=1", "SET_VELOCITY_LIMIT ACCEL={value}",
                        "SET_VELOCITY_LIMIT ACCEL=100 ACCEL=200", "SET_GCODE_OFFSET Z=1"):
            with self.subTest(command=command):
                source = screenshot_fixture().replace(TRAVEL, command + "\n" + TRAVEL, 1)
                output, report = a.process_text(source)
                self.assertEqual(report["replaced_features"], 0)
                self.assertEqual(report["skip_reasons"].get("State command inside bridge region"), 1)
                self.assertEqual(output, source)


if __name__ == "__main__":
    unittest.main()
