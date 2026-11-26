"""Temperature and extrusion regressions for community firmware reports."""
import math
import re
import runpy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "test-deps"), str(ROOT / "dist")]
import arc_overhang as a
fixture = runpy.run_path(str(ROOT / "tests.py"))["fixture"]


def thermal_at_moves(text):
    """Independent oracle for the scalar commands in these fixtures."""
    temperatures, tool, result = {}, 0, {}
    for index, line in enumerate(text.splitlines()):
        body = line.split(";", 1)[0].strip()
        words = {key: float(value) for key, value in re.findall(r"([TPRS])([-+]?\d+(?:\.\d+)?)", body)}
        if re.fullmatch(r"T\d+", body):
            tool = int(body[1:])
        elif body.startswith(("M104 ", "M109 ")):
            value = words.get("S", words.get("R") if body.startswith("M109 ") else None)
            if value is not None:
                temperatures[int(words.get("T", tool))] = value
        elif body.startswith(("G10 ", "M568 ")) and "S" in words:
            temperatures[int(words["P"])] = words["S"]
        elif body.startswith("PRINT_START "):
            temperatures[tool] = float(body.split("EXTRUDER=", 1)[1])
        if body.startswith(("G0 ", "G1 ")):
            result[index] = dict(temperatures)
    return result


class FirmwareCompatibilityTests(unittest.TestCase):
    def test_startup_heater_off_is_not_replayed_around_support(self):
        source = "M104 S0\nPRINT_START EXTRUDER=245\n" + fixture() + "M104 S0 ; end print\n"
        for mode in ("arc", "wave"):
            for order in a.CHOICES["print_order"]:
                with self.subTest(mode=mode, order=order):
                    output, report = a.process_text(source, {"overhang_mode": mode, "print_order": order,
                                                            "wave_temperature_c": 235})
                    self.assertEqual(report["replaced_features"], 1, report)
                    self.assertEqual([line for line in output.splitlines() if line.startswith("M104")],
                                     ["M104 S0", "M104 S0 ; end print"])
                    self.assertTrue(output.endswith("M104 S0 ; end print\n"))
                    temperatures = thermal_at_moves(output)
                    for f in a.parse(output.splitlines(True)):
                        for m in f.moves:
                            if a.segment(m) is not None:
                                self.assertEqual(temperatures[m.index][0], 245)

    def test_m109_r_and_temperature_changes_survive_reordering(self):
        source = "M104 S0\nM109 R245\nM104 T1 S0\n" + fixture()
        source = source.replace("; FEATURE: Sparse infill", "M104 S250\n; FEATURE: Sparse infill")
        expected = thermal_at_moves(source)
        for order in a.CHOICES["print_order"]:
            with self.subTest(order=order):
                output, report = a.process_text(source, {"print_order": order})
                self.assertEqual(report["replaced_features"], 1)
                actual = thermal_at_moves(output)
                by_line = {}
                for f in a.parse(output.splitlines(True)):
                    for m in f.moves:
                        if a.segment(m) is not None:
                            by_line.setdefault(output.splitlines()[m.index], []).append(actual[m.index])
                            if f.role == "bridge":
                                self.assertEqual(actual[m.index], {0: 245, 1: 0})
                for f in a.parse(source.splitlines(True)):
                    if f.role == "bridge":
                        continue
                    for m in f.moves:
                        if a.segment(m) is not None:
                            self.assertIn(expected[m.index], by_line[source.splitlines()[m.index]])

    def test_rrf_g10_temperatures_are_not_firmware_retracts(self):
        source = "G10 P0 R170 S245\nG10 P1 R0 S0\nM116 P0\n" + fixture()
        source = source.replace("; FEATURE: Sparse infill", "G10 P0 S250\n; FEATURE: Sparse infill")
        for order in a.CHOICES["print_order"]:
            with self.subTest(order=order):
                output, report = a.process_text(source, {"print_order": order})
                self.assertEqual(report["replaced_features"], 1, report)
                self.assertIn("G10 P0 R170 S245\n", output)
                self.assertEqual(output.count("G10 P1 R0 S0\n"), 1)
                temperatures = thermal_at_moves(output)
                for f in a.parse(output.splitlines(True)):
                    for m in f.moves:
                        if a.segment(m) is not None:
                            self.assertFalse(m.before.firmware_retracted)
                            self.assertEqual(temperatures[m.index][0], 250 if f.role == "sparse infill" else 245)

    def test_rrf_partial_updates_and_multiple_heaters_are_preserved(self):
        source = "G90\nM83\nG10 P0 R170:175 S240:245\nM568 P0 S250:255 A2\nG10 P0 R180:185\n"
        source += "; CHANGE_LAYER\n;TYPE:Outer wall\nG1 X0 Y0 Z.2\nG1 X1 E.1\n"
        state = a.parse(source.splitlines(True))[0].moves[-1].after
        self.assertEqual(dict(state.modal), {"temperature:0": "G10 P0 S250:255\n",
                                             "standby_temperature:0": "G10 P0 R180:185\n",
                                             "heater_mode:0": "M568 P0 A2\n"})
        pre, post = a.wave_wrappers([], 0, [], a.configuration({"wave_temperature_c": 230}), state)
        self.assertFalse(any(line.startswith(("G10", "M104")) for line in pre + post))

    def test_rrf_wave_override_restores_active_temperature(self):
        source = "G10 P0 S245 R170\n" + fixture()
        output, report = a.process_text(source, {"overhang_mode": "wave", "wave_temperature_c": 235})
        self.assertEqual(report["replaced_features"], 1)
        self.assertIn("G10 P0 S235\n", output)
        temperatures = thermal_at_moves(output)
        inside = False
        for index, line in enumerate(output.splitlines()):
            if line == a.MARKER + "BEGIN": inside = True
            if line == a.MARKER + "END": inside = False
            if line.startswith("G1 X") and " E" in line:
                self.assertEqual(temperatures[index][0], 235 if inside else 245)

    def test_unsupported_g10_offsets_and_expressions_stay_protected(self):
        for cmd in ("G10 P0 X2", "G10 L2 P1 X0", "G10 P0 S245 X1", "G10 P0 S{var.temp}",
                    "G10 P0 S245 Q1", "G10 P0 P1 S245", "G10 P0.5 S245", "G10 S1", "G11 S1"):
            with self.subTest(cmd=cmd), self.assertRaises(a.UnsupportedGCode):
                a.parse((cmd + "\n").splitlines(True))

    def test_rrf_temperature_inside_bridge_is_not_discarded(self):
        source = fixture().replace("G1 X29.5 Y10.5 E0.15 F1200\n",
                                   "G1 X29.5 Y10.5 E0.15 F1200\nG10 P0 S245\n", 1)
        output, report = a.process_text(source)
        self.assertEqual(output, source)
        self.assertEqual(report["skip_reasons"], {"State command inside bridge region": 1})

    def test_rrf_temperature_does_not_clear_a_real_retract(self):
        source = "G10\nG10 P0 S245\n;TYPE:Bridge\nG1 X0 Y0\nG11\nG1 X1 Y0\n"
        moves = a.parse(source.splitlines(True))[0].moves
        self.assertTrue(moves[0].after.firmware_retracted)
        self.assertFalse(moves[1].after.firmware_retracted)

    def test_centauri_style_output_contains_relative_extrusion(self):
        # Synthetic model with the stock profile's explicit positioning and
        # heating sequence. This does not reproduce the reported hardware hang.
        source = "M104 S140\nG90\nM83\nG28\nM729\nM109 S245\nG92 E0\n" + fixture()
        for refined in (False, True):
            with self.subTest(refined=refined):
                output, report = a.process_text(source, {"initial_path_count": int(refined)})
                self.assertEqual(report["replaced_features"], 1)
                relative, inside, debt, strokes = False, False, 0.0, 0
                for line in output.splitlines():
                    body = line.split(";", 1)[0].strip()
                    if body == "M83": relative = True
                    if body == "M82": relative = False
                    if line == a.MARKER + "BEGIN": inside = True
                    if line == a.MARKER + "END": inside = False
                    if not inside or not body.startswith("G1 "): continue
                    words = {k: float(v) for k, v in re.findall(r"([XYZEF])([-+]?\d+(?:\.\d+)?)", body)}
                    self.assertTrue(all(math.isfinite(v) for v in words.values()))
                    if "E" not in words: continue
                    self.assertTrue(relative)
                    e = words["E"]
                    if "X" in words and "Y" in words:
                        self.assertGreater(e, 0)
                        self.assertLess(e, 1)
                        self.assertLess(debt, 1e-5)
                        strokes += 1
                    debt = max(0, debt - e)
                self.assertGreater(strokes, 20)
                self.assertLess(debt, 1e-5)


if __name__ == "__main__":
    unittest.main()
