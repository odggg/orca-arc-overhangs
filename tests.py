import sys
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
ROOT = Path(__file__).parent
sys.path[:0] = [str(ROOT / "test-deps"), str(ROOT / "dist"), str(ROOT / "plugin")]
import arc_overhang as a

def ring(x0, y0, x1, y1, role="Outer wall"):
    return f"; FEATURE: {role}\nG1 X{x0} Y{y0} F1800\nG1 X{x1} Y{y0} E0.5\nG1 X{x1} Y{y1} E0.5\nG1 X{x0} Y{y1} E0.5\nG1 X{x0} Y{y0} E0.5\n"

def fixture(style="modern"):
    header = "G90\nM83\nG92 E0\n; nozzle_diameter = 0.4\n; filament_diameter = 1.75\n; layer_height = 0.2\n; outer_wall_line_width = 0.42\n"
    text = header + "; CHANGE_LAYER\nG1 Z0.2\n" + ring(10, 10, 20, 30)
    text += "; CHANGE_LAYER\nG1 Z0.4\n" + ring(10, 10, 30, 30)
    text += "; FEATURE: Overhang wall\nG1 X30 Y10\nG1 X30 Y30 E0.5\n"
    text += "; FEATURE: Bridge\nG1 X19 Y10.5 F1800\n"
    for i in range(48):
        y = 10.5 + i * 0.4
        xa, xb = (19, 29.5) if i % 2 == 0 else (29.5, 19)
        text += f"G1 X{xa} Y{y} F1800\nG1 X{xb} Y{y} E0.15 F1200\n"
    text += "; FEATURE: Sparse infill\nG1 X12 Y12 F9000\nG1 X15 Y15 E0.3 F2400\nM106 P2 S120\n"
    if style == "legacy":
        text = text.replace("; CHANGE_LAYER", ";LAYER_CHANGE").replace("; FEATURE: ", ";TYPE:")
    return text

class Tests(unittest.TestCase):
    def test_configuration_rejects_invalid(self):
        for cfg in ({"arc_speed_mm_s": 0}, {"points_per_circle": 81}, {"enabled": 1}, {"flow_multiplier": float("nan")}, {"made_up": 1}, {"max_centers": 1.5}, {"next_layer_pattern": "banana"}):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                a.configuration(cfg)

    def test_modern_and_legacy_arcs_and_idempotence(self):
        for style in ("modern", "legacy"):
            with self.subTest(style=style):
                source = fixture(style)
                output, report = a.process_text(source, {"minimum_coverage_percent": 80})
                self.assertEqual(report["replaced_features"], 1, report)
                self.assertGreater(report["generated_arcs"], 5)
                self.assertIn(a.MARKER, output)
                self.assertIn("G1 X15 Y15 E0.3 F2400", output)
                self.assertIn("M106 P2 S120", output)
                self.assertEqual(a.process_text(output)[0], output)
                original_end = a.parse(source.splitlines(True))[-1].moves[-1].after
                new_end = a.parse(output.splitlines(True))[-1].moves[-1].after
                self.assertAlmostEqual(original_end.e, new_end.e, places=6)
                self.assertEqual(a.replace(original_end, e=0), a.replace(new_end, e=0))
                self.assertNotIn("nan", output.lower())
                self.assertNotIn("inf ", output.lower())

    def test_hilbert_next_layer_selector_and_geometry(self):
        self.assertEqual(a.DEFAULTS["next_layer_pattern"], "slicer")
        self.assertEqual(a.configuration({"next_layer_pattern": "hilbert"})["next_layer_pattern"], "hilbert")
        page = a.config_page()
        self.assertIn('id="next_layer_pattern"', page)
        self.assertIn('value="hilbert"', page)
        poly = a.Polygon([(10, 10), (20, 10), (20, 20), (10, 20)])
        paths = a.hilbert_paths(poly, 0.5)
        self.assertTrue(paths)
        for line, spacing in paths:
            self.assertLessEqual(spacing, 0.5 + 1e-9)
            self.assertLess(line.difference(poly).length, 1e-6)
        source = ("G90\nM83\n; nozzle_diameter = 0.4\n; filament_diameter = 1.75\n"
                  "; layer_height = 0.2\n; outer_wall_line_width = 0.42\n; CHANGE_LAYER\nG1 Z0.2\n"
                  "; FEATURE: Internal solid infill\nG1 X11 Y11 F1800\n"
                  "G1 X19 Y11 E0.5\nG1 X19 Y19 E0.5\n")
        feature = a.parse(source.splitlines(True))[0]
        replacement = a.hilbert_feature_replacement(
            feature, source.splitlines(True), poly, a.configuration(),
            a.printer_settings(source.splitlines()), lambda: False)
        self.assertIsNotNone(replacement)
        self.assertTrue(any("Hilbert" in line for line in replacement))
        self.assertTrue(any(line.startswith("G92 E1.0000000") for line in replacement))

    def test_wave_mode_replaces_bridge_with_anchored_fronts(self):
        self.assertEqual(a.DEFAULTS["overhang_mode"], "arc")
        with self.assertRaises(ValueError):
            a.configuration({"overhang_mode": "spiral"})
        self.assertIn('id="overhang_mode"', a.config_page())
        source = fixture()
        output, report = a.process_text(source, {"overhang_mode": "wave", "minimum_coverage_percent": 80})
        self.assertEqual(report["replaced_features"], 1, report)
        self.assertGreater(report["generated_arcs"], 5)
        self.assertGreaterEqual(report["minimum_coverage_percent"], 80)
        self.assertEqual(a.process_text(output)[0], output)
        # Wave fronts are not the same toolpaths as concentric arcs.
        arc_output, _ = a.process_text(source, {"minimum_coverage_percent": 80})
        self.assertNotEqual(output, arc_output)
        bridge = next(f for f in a.parse(output.splitlines(True)) if f.role == "bridge")
        self.assertFalse(a.is_retracted(bridge.moves[-1].after))
        self.assertNotIn("nan", output.lower())

    def test_hilbert_applies_to_feature_that_opens_with_retract_travel(self):
        # Orca emits ;TYPE first, then retract, travel, unretract. This must not block Hilbert.
        source = fixture() + "; CHANGE_LAYER\nG1 Z0.6\n; FEATURE: Internal solid infill\nG1 E-0.8 F2100\nG1 X20 Y12 F9000\nG1 E0.8 F2100\n"
        for i in range(36):
            y = 12 + i * 0.45
            xa, xb = (20, 28) if i % 2 == 0 else (28, 20)
            source += f"G1 X{xa} Y{y} F9000\nG1 X{xb} Y{y} E0.3 F2400\n"
        source += "; FEATURE: Outer wall\nG1 E-0.8 F2100\nG1 X10 Y10 F9000\nG1 E0.8 F2100\nG1 X30 Y10 E0.5\n"
        output, report = a.process_text(source, {"minimum_coverage_percent": 80, "next_layer_pattern": "hilbert"})
        self.assertEqual(report["replaced_features"], 1, report)
        self.assertEqual(report["hilbert_features"], 1, report)
        self.assertIn("Hilbert", output)
        # Balanced retraction: the replacement ends unretracted.
        feature = next(f for f in a.parse(output.splitlines(True)) if f.role.startswith("internal solid infill (hilbert"))
        self.assertFalse(a.is_retracted(feature.moves[-1].after))

    def test_slicer_order_kept_but_overhang_wall_follows_arcs(self):
        # Default Orca order: walls first, bridge after. Only the overhang wall moves.
        for style in ("modern", "legacy"):
            source = fixture(style)
            role = "; FEATURE: " if style == "modern" else ";TYPE:"
            source = source.replace(role + "Sparse infill", ring(11, 11, 18, 28, "Inner wall") + role + "Sparse infill")
            change = "; CHANGE_LAYER" if style == "modern" else ";LAYER_CHANGE"
            source += change + "\nG1 Z0.6\n" + ring(10, 10, 30, 30) + "M104 S0\n"
            output, report = a.process_text(source)
            self.assertEqual(report["replaced_features"], 1, report)
            self.assertLess(output.index(a.MARKER + "BEGIN"), output.rindex(change))
            self.assertTrue(output.endswith("M104 S0\n"))
            printed = [f for f in a.parse(output.splitlines(True)) if f.layer == 1
                       and any(a.segment(m) is not None for m in f.moves)]
            roles = [f.role for f in printed]
            self.assertEqual(roles, ["outer wall", "bridge", "overhang wall", "inner wall", "sparse infill"][:0] or roles)
            self.assertLess(roles.index("bridge"), roles.index("overhang wall"))
            # Normal features keep the slicer's relative order.
            self.assertEqual([r for r in roles if r not in ("bridge", "overhang wall")],
                             ["outer wall", "inner wall", "sparse infill"])
            original_wall = [m for f in a.parse(source.splitlines(True)) if f.role == "overhang wall"
                             for m in f.moves if a.segment(m) is not None]
            moved_wall = [m for f in printed if f.role == "overhang wall"
                          for m in f.moves if a.segment(m) is not None]
            self.assertEqual([(list(a.segment(m).coords), m.delta_e) for m in original_wall],
                             [(list(a.segment(m).coords), m.delta_e) for m in moved_wall])

    def test_infill_first_order_prints_arcs_before_all_walls(self):
        # "Infill first" wall order: bridge, then inner/outer/overhang walls. Nothing may move.
        source = fixture()
        bridge_start = source.index("; FEATURE: Bridge")
        walls_start = source.index("; FEATURE: Overhang wall")
        sparse = source.index("; FEATURE: Sparse infill")
        layer2 = source[:walls_start]
        reordered = (layer2 + source[bridge_start:sparse]
                     + ring(11, 11, 18, 28, "Inner wall")
                     + source[walls_start:bridge_start] + source[sparse:])
        output, report = a.process_text(reordered, {"minimum_coverage_percent": 80})
        self.assertEqual(report["replaced_features"], 1, report)
        printed = [f.role for f in a.parse(output.splitlines(True)) if f.layer == 1
                   and any(a.segment(m) is not None for m in f.moves)]
        self.assertLess(printed.index("bridge"), printed.index("inner wall"))
        self.assertLess(printed.index("bridge"), printed.index("overhang wall"))
        # No relocation happened: the output carries no extra travel-only restore blocks.
        self.assertEqual(output.count("G92 E"), reordered.count("G92 E") + 1)

    def test_no_bridge_unchanged(self):
        source = "G90\nM83\n; CHANGE_LAYER\nG1 X1 Y1 E0.2\n"
        self.assertEqual(a.process_text(source)[0], source)

    def test_absolute_e_rejected(self):
        source = fixture().replace("M83", "M82")
        with self.assertRaises(a.UnsupportedGCode):
            a.process_text(source)

    def test_fully_supported_bridge_with_overhang_tag_is_preserved(self):
        source = fixture().replace(ring(10, 10, 20, 30), ring(10, 10, 30, 30), 1)
        output, report = a.process_text(source)
        self.assertEqual(report["replaced_features"], 0)
        self.assertEqual(report["skipped_features"], 1)
        self.assertNotIn(a.MARKER, output)
        self.assertEqual(output, source)

    def test_arc_paths_start_on_support_or_previous_arc(self):
        support = a.Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        disconnected = a.LineString([(8, 0.5), (9, 0.5)])
        bridge = a.LineString([(1, 0.5), (2, 0.5)])
        continuation = a.LineString([(3, 0.5), (2, 0.5)])
        ordered = a.anchor_arc_paths(
            [continuation, bridge], support, 0.4, 0.42)
        self.assertIsNotNone(ordered)
        self.assertEqual(list(ordered[0].coords)[0], (1.0, 0.5))
        self.assertEqual(list(ordered[1].coords)[0], (2.0, 0.5))
        self.assertIsNone(a.anchor_arc_paths(
            [disconnected], support, 0.4, 0.42))
        self.assertIsNone(a.anchor_arc_paths(
            [bridge, disconnected], support, 0.4, 0.42))

    def test_wall_overlap_is_zero_when_disabled_and_grows_with_setting(self):
        self.assertEqual(a.DEFAULTS["wall_overlap_mm"], 0.2)
        source = fixture()
        printer = a.printer_settings(source.splitlines())
        width = printer["outer_wall_line_width"]
        arc_width = printer["nozzle_diameter"] * a.DEFAULTS["arc_spacing_nozzle_ratio"]
        current = a.layer_shape([f for f in a.parse(source.splitlines(True)) if f.layer == 1], width)
        wall_footprint = current.boundary.buffer(width / 2)
        measured = []
        for overlap in (0.0, 0.2, 0.8):
            output, report = a.process_text(source, {
                "wall_overlap_mm": overlap,
                "minimum_coverage_percent": 80,
            })
            self.assertEqual(report["replaced_features"], 1, report)
            arcs = [a.segment(move) for feature in a.parse(output.splitlines(True))
                    if feature.role in ("bridge", "bridge infill", "internal bridge")
                    for move in feature.moves if a.segment(move) is not None]
            arc_footprint = a.unary_union([line.buffer(arc_width / 2) for line in arcs])
            measured.append(arc_footprint.intersection(wall_footprint).area)
        self.assertLess(measured[0], 1e-6, measured)
        self.assertLess(measured[1], measured[2], measured)

    def test_inner_wall_overlap_can_reach_inner_wall_beyond_outer_wall_width(self):
        current = a.Polygon(
            [(0, 0), (10, 0), (10, 10), (0, 10)],
            holes=[[(4, 4), (6, 4), (6, 6), (4, 6)]])
        bridge = a.LineString([(1, 5), (2, 5)])
        narrow = a.bridge_region([bridge], current, 0.42, 0.38, 0.2)
        extended = a.bridge_region([bridge], current, 0.42, 0.38, 4.0)
        wall_window = a.Polygon([(3.7, 4.0), (4.3, 4.0), (4.3, 6.0), (3.7, 6.0)])
        inner_wall_band = current.boundary.buffer(0.21).intersection(wall_window)
        self.assertLess(narrow.intersection(inner_wall_band).area, 1e-6)
        self.assertGreater(extended.intersection(inner_wall_band).area, 0.05)

    def test_geometric_overhang_without_special_wall_tag(self):
        source = fixture().replace("Overhang wall", "Inner wall")
        output, report = a.process_text(source)
        self.assertEqual(report["replaced_features"], 1)
        self.assertIn(a.MARKER, output)

    def test_disabled_unchanged(self):
        source = fixture()
        self.assertEqual(a.process_text(source, {"enabled": False})[0], source)

    def test_cancellation(self):
        with self.assertRaises(a.Cancelled):
            a.process_text(fixture(), cancelled=lambda: True)

    def test_unreachable_area_preserved(self):
        source = fixture().replace(ring(10, 10, 20, 30), ring(100, 100, 110, 120), 1)
        self.assertEqual(a.process_text(source)[0], source)

    def test_holes_in_shape(self):
        source = "G90\nM83\n; CHANGE_LAYER\nG1 Z0.2\n" + ring(0, 0, 20, 20) + ring(5, 5, 10, 10)
        shape = a.layer_shape(a.parse(source.splitlines(True)), 0.42)
        self.assertAlmostEqual(shape.area, 375)
        self.assertFalse(shape.contains(a.Point(7, 7)))

    def test_file_atomic_failure_and_binary(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / "test.gcode"
            source = fixture().encode()
            path.write_bytes(source)
            with patch.object(a.os, "replace", side_effect=OSError("test failure")):
                with self.assertRaises(OSError):
                    a.process_file(path, {"minimum_coverage_percent": 80})
            self.assertEqual(path.read_bytes(), source)
            self.assertEqual(list(Path(folder).glob(".arc-overhang-*")), [])
            path.write_bytes(b"PK\\0binary")
            with self.assertRaises(a.UnsupportedGCode):
                a.process_file(path)

    def test_speed_spacing_wall_overlap_independent(self):
        cfg = a.configuration({"arc_speed_mm_s": 10, "minimum_arc_speed_mm_s": 10,
                               "arc_spacing_nozzle_ratio": 0.5, "wall_overlap_mm": 1.2})
        printer = a.printer_settings(fixture().splitlines())
        params = a.parameters(cfg, printer, lambda:False)
        self.assertEqual(params["ArcWidth"], 0.2)
        out = "".join(a.emit_arcs([a.LineString([(20,20),(22,20)])], a.State(x=20,y=20,relative_e=True),
                         a.State(x=22,y=20,relative_e=True), cfg, printer))
        self.assertIn("G1 F600.00", out)
        self.assertIn("E0.1410612", out)

    def test_wave_has_own_speed_flow_and_optional_z_hop(self):
        printer = a.printer_settings(fixture().splitlines())
        line = [a.LineString([(20, 20), (22, 20)])]
        before, after = a.State(x=20, y=20, z=0.4, relative_e=True), a.State(x=22, y=20, z=0.4, relative_e=True)
        arc = "".join(a.emit_arcs(line, before, after, a.configuration({"arc_speed_mm_s": 10, "minimum_arc_speed_mm_s": 10}), printer))
        wave = "".join(a.emit_arcs(line, before, after, a.configuration(
            {"overhang_mode": "wave", "wave_speed_mm_s": 7, "arc_speed_mm_s": 10, "minimum_arc_speed_mm_s": 10}), printer))
        self.assertIn("G1 F600.00", arc)
        self.assertIn("G1 F420.00", wave)
        self.assertNotIn("E0.1410612", wave)
        self.assertNotIn("Z0.8", arc)
        hop = "".join(a.emit_arcs(line, before, after, a.configuration({"z_hop_mm": 0.4}), printer))
        self.assertIn("G1 Z0.80000", hop)
        self.assertEqual(hop.count("G1 Z0.40000"), 2)


    def test_wave_components(self):
        from shapely.geometry import box
        from shapely.ops import unary_union
        # reconnect joins touching ends and leaves distant pieces alone
        joined = a.reconnect_polylines([[(0, 0), (1, 0)], [(1.05, 0), (2, 0)], [(5, 5), (6, 5)]], 0.2)
        self.assertEqual(len(joined), 2)
        self.assertEqual(joined[0][0], (0, 0))
        # a 0.5 mm neck gets a slit that changes topology; a wide neck is not
        narrow = unary_union([box(0, 0, 10, 10), box(10, 4.75, 10.5, 5.25), box(10.5, 0, 20.5, 10)])
        slit = a.narrow_split_slits(narrow, 0.35, 0.7)
        self.assertEqual(a._hole_count(narrow.difference(slit)), 1)  # the slit opens a hole, as in the C++ topology test
        self.assertIsNone(a.narrow_split_slits(unary_union([box(0, 0, 10, 10), box(10, 3, 14, 7), box(14, 0, 24, 10)]), 0.35, 0.7))
        # square has 4 sharp corners at 100 degrees, none at 80
        self.assertEqual(len(a.detect_overhang_corners(box(0, 0, 4, 4), 1.7)), 4)
        self.assertEqual(len(a.detect_overhang_corners(box(0, 0, 4, 4), 1.4)), 0)
        printer = {"nozzle_diameter": 0.4, "outer_wall_line_width": 0.42}
        poly, support = box(10, 10, 30, 30), box(10, 10, 20, 30)
        counts = {}
        for pattern in ("smart", "zigzag", "monotonic"):
            cfg = a.configuration({"overhang_mode": "wave", "wave_pattern": pattern})
            paths, coverage = a.fill_polygon_wave(poly, support, cfg, printer, lambda: False)
            counts[pattern] = len(paths)
            self.assertGreater(coverage, 95)
            for path in paths:
                self.assertLess(path.difference(poly).length, 1e-6)
        self.assertLess(counts["zigzag"], counts["smart"])
        self.assertEqual(counts["smart"], counts["monotonic"])
        # corner taper adds lines; max_iterations limits them
        base = a.configuration({"overhang_mode": "wave", "wave_pattern": "monotonic"})
        taper = a.configuration({"overhang_mode": "wave", "wave_pattern": "monotonic", "wave_corner_taper": True,
                                 "wave_corner_spacing_mm": 0.175, "wave_corner_angle_deg": 100, "wave_corner_distance_mm": 3, "minimum_coverage_percent": 50})
        capped = a.configuration({"overhang_mode": "wave", "wave_max_iterations": 3, "minimum_coverage_percent": 50})
        n_base = len(a.fill_polygon_wave(poly, support, base, printer, lambda: False)[0])
        self.assertGreater(len(a.fill_polygon_wave(poly, support, taper, printer, lambda: False)[0]), n_base)
        self.assertLessEqual(len(a.fill_polygon_wave(poly, support, capped, printer, lambda: False)[0]), 3)
        long_only = a.configuration({"overhang_mode": "wave", "wave_min_length_mm": 500})
        self.assertIsNone(a.fill_polygon_wave(poly, support, long_only, printer, lambda: False))

    def test_wave_fan_temperature_dwell_and_volumetric_cap(self):
        source = "M104 S210\nM106 S128\n" + fixture()
        cfg = {"overhang_mode": "wave", "minimum_coverage_percent": 80, "wave_fan_override": True,
               "wave_temperature_c": 230, "wave_min_time_s": 500}
        output, report = a.process_text(source, cfg)
        self.assertEqual(report["replaced_features"], 1, report)
        block = output[output.index(a.MARKER + "BEGIN"):output.index(a.MARKER + "END")]
        self.assertIn("M106 S255", block)
        self.assertIn("M106 S128", block)
        self.assertIn("M104 S230", block)
        self.assertIn("M104 S210", block)
        self.assertIn("G4 P", block)
        printer = a.printer_settings(fixture().splitlines())
        printer["max_volumetric_speed"] = 0.15
        before, after = a.State(x=20, y=20, z=0.4, relative_e=True), a.State(x=22, y=20, z=0.4, relative_e=True)
        out = "".join(a.emit_arcs([a.LineString([(20, 20), (22, 20)])], before, after,
                                  a.configuration({"overhang_mode": "wave", "wave_speed_mm_s": 5}), printer))
        self.assertIn("G1 F60.00", out)
        for bad in ({"wave_pattern": "spiral"}, {"wave_fan_percent": 101}, {"wave_temperature_c": 50}, {"wave_corner_angle_deg": 5}):
            with self.assertRaises(ValueError):
                a.configuration(bad)

    def test_wave_bridge_heuristic(self):
        from shapely.geometry import box
        anchors = a.unary_union([box(0, 0, 10, 10), box(0, 20, 10, 30)])
        span, cantilever = box(0, 10, 10, 20), box(10, 0, 20, 10)
        args = (anchors, anchors, span.buffer(0.1), 0.35)
        self.assertFalse(a.should_generate_waves(span, span, *args, False))
        self.assertTrue(a.should_generate_waves(span, span, *args, True))
        self.assertEqual(a.bridging_unsupported_distance(span, anchors), 0.0)
        anchor = box(0, 0, 10, 10)
        free = box(0, 10, 10, 20)
        self.assertAlmostEqual(a.bridging_unsupported_distance(free, anchor), 10.0, places=2)
        self.assertTrue(a.should_generate_waves(free, free, anchor, anchor, free.buffer(0.1), 0.35, False))
        output, report = a.process_text(fixture(), {"overhang_mode": "wave", "minimum_coverage_percent": 80,
                                                    "wave_instead_of_bridges": False})
        self.assertEqual(report["replaced_features"], 1, report)

    def test_wave_floor_speeds_ramp_and_end_retract(self):
        cfg = a.configuration({"wave_floor_layers": 3, "wave_floor_speed_ramp": 3})
        self.assertEqual([a.floor_speed(cfg, k, 10, 50) for k in (1, 2, 3)], [10, 30, 50])
        self.assertIsNone(a.floor_speed(cfg, 1, 0, 50))
        source = fixture() + "; CHANGE_LAYER\nG1 Z0.6\n" + ring(10, 10, 30, 30) + "; FEATURE: Internal solid infill\nG1 X21 Y12 F9000\nG1 X28 Y12 E0.3\n"
        source = source.replace("; FEATURE: Overhang wall", ring(11, 11, 29, 29, "Inner wall") + "; FEATURE: Overhang wall")
        cfg = {"overhang_mode": "wave", "minimum_coverage_percent": 80, "wave_perimeter_speed_mm_s": 10,
               "wave_floor_perimeter_speed_mm_s": 15, "wave_floor_print_speed_mm_s": 12, "wave_floor_layers": 2,
               "wave_end_retract_mm": 0.3}
        output, report = a.process_text(source, cfg)
        self.assertEqual(report["replaced_features"], 1, report)
        self.assertGreaterEqual(report["retimed_features"], 3, report)
        for feed in ("F600.0", "F900.0", "F720.0"):
            self.assertIn(feed, output)
        self.assertIn("G1 E-0.30000", output)
        self.assertEqual(a.process_text(output, cfg)[0], output)
        # Feed state after every retimed feature matches the source, so later moves are untouched.
        ends = lambda t: [f.moves[-1].after.feed for f in a.parse(t.splitlines(True)) if f.moves and f.role != "bridge"]
        self.assertEqual(ends(source)[-1], ends(output)[-1])

    def test_wave_hilbert_floor_density_and_fans(self):
        source = fixture() + "; CHANGE_LAYER\nG1 Z0.6\n; FEATURE: Internal solid infill\nG1 X20 Y12 F9000\n"
        for i in range(36):
            y = 12 + i * 0.45
            xa, xb = (20, 28) if i % 2 == 0 else (28, 20)
            source += f"G1 X{xa} Y{y} F9000\nG1 X{xb} Y{y} E0.3 F2400\n"
        source += "; FEATURE: Outer wall\nG1 X10 Y10 F9000\nG1 X30 Y10 E0.5\n"
        cfg = {"overhang_mode": "wave", "minimum_coverage_percent": 80, "wave_floor_use_hilbert": True,
               "wave_floor_print_speed_mm_s": 20, "wave_floor_fan_override": True, "wave_floor_fan_percent": 30,
               "wave_floor_aux_fan_override": True, "wave_floor_aux_fan_percent": 50}
        output, report = a.process_text(source, cfg)
        self.assertEqual(report["hilbert_features"], 1, report)
        self.assertIn("M106 S76", output)
        self.assertIn("M106 P2 S127", output)
        self.assertIn("M106 P2 S120", output)
        self.assertIn("F1200.0", output)
        sparse, _ = a.process_text(source, {**cfg, "wave_floor_hilbert_density_percent": 25})
        self.assertLess(sparse.count("\nG1 X"), output.count("\nG1 X"))
        for bad in ({"wave_floor_layers": 21}, {"wave_floor_hilbert_density_percent": 0}, {"wave_floor_fan_percent": 101},
                    {"wave_floor_speed_ramp": 1.5}, {"wave_perimeter_speed_mm_s": 1001}):
            with self.assertRaises(ValueError):
                a.configuration(bad)

    def test_import_wave_gallery_profile(self):
        text = """; wave_overhang_pattern = zigzag
; wave_overhang_line_spacing = 0.35
; wave_overhang_perimeter_overlap = 0.15
; wave_overhang_floor_use_hilbert = 1
; wave_overhang_floor_hilbert_layers = 2
; wave_overhang_floor_hilbert_density = 50
; wave_overhang_floor_print_speed = 20
; wave_overhang_floor_fan_speed = 0
; wave_overhang_mystery = 1
; WAVE_OVERHANG_CONFIG spacing=0.4 speed=3
"""
        values, ignored = a.import_wave_profile(text)
        self.assertEqual(values["overhang_mode"], "wave")
        self.assertEqual(values["wave_pattern"], "zigzag")
        self.assertEqual(values["wave_line_spacing_mm"], 0.35)  # explicit line beats the marker summary
        self.assertEqual(values["wave_speed_mm_s"], 3.0)
        self.assertEqual(values["wave_perimeter_overlap_mm"], 0.15)
        self.assertTrue(values["wave_floor_use_hilbert"])
        self.assertEqual(values["wave_floor_hilbert_density_percent"], 50.0)
        self.assertEqual((values["wave_floor_fan_override"], values["wave_floor_fan_percent"]), (True, 0.0))
        self.assertEqual(ignored, ["wave_overhang_mystery"])
        a.configuration(values)

    def test_hilbert_floor_ignores_start_gcode_purge_line(self):
        text = fixture().replace("G90\nM83\nG92 E0\n", "G90\nM82\nG92 E0\n; FEATURE: Custom\nG1 X5 Y5 F3000\nG1 E50 F200\nM83\n", 1)
        _, report = a.process_text(text, {"overhang_mode": "wave", "wave_floor_use_hilbert": True, "minimum_area_mm2": 1})
        self.assertEqual(report["replaced_features"], 1)

    def test_wave_line_spacing_in_mm(self):
        coarse, _ = a.process_text(fixture(), {"overhang_mode": "wave", "minimum_coverage_percent": 80, "wave_line_spacing_mm": 0.35})
        default, _ = a.process_text(fixture(), {"overhang_mode": "wave", "minimum_coverage_percent": 80})
        self.assertEqual(coarse, default)  # 0.35 mm == 0.875 * 0.4 mm nozzle
        wide, _ = a.process_text(fixture(), {"overhang_mode": "wave", "minimum_coverage_percent": 80, "wave_line_spacing_mm": 0.5})
        self.assertNotEqual(wide, default)
        with self.assertRaises(ValueError):
            a.configuration({"wave_line_spacing_mm": 2})

    def test_wave_min_layer_time_adds_dwell(self):
        source = fixture() + "; CHANGE_LAYER\nG1 Z0.6\n" + ring(10, 10, 30, 30)
        output, report = a.process_text(source, {"overhang_mode": "wave", "minimum_coverage_percent": 80,
                                                 "wave_min_layer_time_s": 500})
        self.assertEqual(report["replaced_features"], 1, report)
        self.assertRegex(output, r"G4 P\d{5,}\n; CHANGE_LAYER\nG1 Z0.6")

    def test_split_outer_overhang_wall_ring(self):
        source = "G90\nM83\n; CHANGE_LAYER\nG1 Z0.2\n"
        source += "; FEATURE: Outer wall\nG1 X0 Y0\nG1 X20 Y0 E1\nG1 X20 Y20 E1\n"
        source += "; FEATURE: Overhang wall\nG1 X0 Y20 E1\nG1 X0 Y0 E1\n"
        shape = a.layer_shape(a.parse(source.splitlines(True)), 0.42)
        self.assertAlmostEqual(shape.area, 400)

    def test_other_bridge_in_same_layer_is_preserved(self):
        interior = "; FEATURE: Bridge\nG1 X12 Y12 F1800\nG1 X14 Y12 E0.1\nG1 X14 Y13 E0.1\nG1 X12 Y13 E0.1\n"
        source = fixture() + interior
        output, report = a.process_text(source)
        self.assertEqual(report["replaced_features"], 1)
        self.assertEqual(report["skipped_features"], 1)
        self.assertIn(interior, output)

    def test_default_coverage_and_toolpath_envelope(self):
        output, report = a.process_text(fixture())
        self.assertEqual(report["replaced_features"], 1)
        self.assertGreaterEqual(report["minimum_coverage_percent"], 90)
        injected = output.split(a.MARKER + "BEGIN")[1].split(a.MARKER + "END")[0]
        for _, words in (a.command(line) for line in injected.splitlines()):
            if "X" in words:
                self.assertTrue(10-1e-4 <= words["X"] <= 30+1e-4)
                self.assertTrue(10-1e-4 <= words["Y"] <= 30+1e-4)

    def test_actual_orca_metadata_contract_and_registration(self):
        import types, runpy, tomllib
        file = ROOT / "dist/arc_overhang.py"
        source = file.read_text()
        block = source.split("# /// script\n",1)[1].split("# ///",1)[0]
        metadata = tomllib.loads("\n".join(line[2:] for line in block.splitlines()))
        self.assertEqual(metadata["tool"]["orcaslicer"]["plugin"]["version"], a.VERSION)
        self.assertEqual(len(metadata["dependencies"]), 2)
        calls = []
        class Capability:
            config = "{}"
            fail_save = False
            override = None
            def get_config(self): return self.override if self.override is not None else self.config
            def save_config(self, config):
                if self.fail_save: return False
                self.config = config
                return True
            def post_message(self, data):
                if not hasattr(self, "messages"): self.messages = []
                self.messages.append(data)
        result = types.SimpleNamespace(success=lambda *v:("success",v), skipped=lambda *v:("skipped",v),
                                       failure=lambda *v:("failure",v))
        host = types.ModuleType("orca")
        host.base = type("Base", (), {})
        host.plugin = lambda cls:cls
        host.register_capability = calls.append
        host.slicing = types.SimpleNamespace(SlicingPipelineCapabilityBase=Capability, Step=types.SimpleNamespace(psGCodePostProcess=99))
        host.pages = types.SimpleNamespace(PagesPluginCapabilityBase=Capability)
        host.ExecutionResult = result
        host.PluginResult = types.SimpleNamespace(FatalError="fatal")
        with patch.dict(sys.modules, {"orca":host}):
            namespace = runpy.run_path(str(file), run_name="plugin_test")
        namespace["ArcOverhangPlugin"]().register_capabilities()
        self.assertEqual(len(calls), 2)
        capability = calls[0]()
        self.assertEqual(capability.get_name(), "Arc Overhang")
        self.assertEqual(capability.get_default_config(), a.DEFAULTS)
        self.assertTrue(capability.has_config_ui())
        self.assertIn("window.orca.saveConfig", capability.get_config_ui())
        self.assertEqual(capability.execute(types.SimpleNamespace(step=0))[0], "skipped")
        ctx = types.SimpleNamespace(step=99, config_value=lambda key:None, gcode_path="missing-file.gcode", cancelled=lambda:False)
        self.assertEqual(capability.execute(ctx)[0], "failure")
        page = calls[1]()
        self.assertEqual(page.get_name(), "Arc Overhang")
        self.assertIn("window.orca.onMessage", page.get_ui())
        capability.on_load()
        page.on_message({"action":"read","request_id":1})
        self.assertEqual(page.messages[-1]["config"], a.DEFAULTS)
        page.on_message({"action":"save","request_id":2,"config":{"arc_speed_mm_s":10}})
        self.assertTrue(page.messages[-1]["ok"])
        self.assertEqual(__import__("json").loads(capability.get_config())["arc_speed_mm_s"],10)
        page.on_message({"action":"save","request_id":3,"config":{"arc_speed_mm_s":0}})
        self.assertFalse(page.messages[-1]["ok"])
        self.assertEqual(__import__("json").loads(capability.get_config())["arc_speed_mm_s"],10)
        capability.fail_save = True
        page.on_message({"action":"save","request_id":4,"config":{"arc_speed_mm_s":12}})
        self.assertFalse(page.messages[-1]["ok"])
        capability.fail_save = False
        capability.override = '{"arc_speed_mm_s":3}'
        page.on_message({"action":"save","request_id":5,"config":{"arc_speed_mm_s":12}})
        self.assertTrue(page.messages[-1]["preset_override_active"])
        self.assertEqual(page.messages[-1]["config"]["arc_speed_mm_s"],3)
        capability.override = None
        capability.on_unload()
        page.on_message({"action":"read","request_id":6})
        self.assertFalse(page.messages[-1]["ok"])
        page.on_message(None)
        page.on_message({"action":"read","request_id":"invalid"})


    def test_missing_settings_and_unsupported_modes(self):
        for source in (fixture().replace("; nozzle_diameter = 0.4\n",""),
                       fixture().replace("M83","M83\nG20")):
            with self.subTest(source=source[:60]), self.assertRaises(a.UnsupportedGCode):
                a.process_text(source)
        source = fixture().replace("; nozzle_diameter = 0.4",
                                   "; nozzle_diameter = 0.4;0.6")
        source = source.replace("; filament_diameter = 1.75",
                                "; filament_diameter = 1.75;2.85")
        self.assertEqual(a.printer_settings(source.splitlines(), tool_index=1)["nozzle_diameter"], 0.6)
        output, report = a.process_text(source)
        self.assertEqual(report["replaced_features"], 1, report)

    def test_single_nonzero_tool_index_is_supported(self):
        source = fixture().replace("G90\nM83", "T1\nT1\nG90\nM83")
        output, report = a.process_text(source)
        self.assertEqual(report["replaced_features"], 1)
        self.assertIn(a.MARKER, output)

    def test_multiple_physical_tools_use_selected_material_and_preserve_switches(self):
        source = fixture().replace("G90\nM83", "T0\nG90\nM83")
        source = source.replace("; FEATURE: Bridge", "T1\n; FEATURE: Bridge")
        source = source.replace("; FEATURE: Sparse infill", "T0\n; FEATURE: Sparse infill")
        resolved = {
            "nozzle_diameter": [0.4, 0.6],
            "filament_diameter": [1.75, 2.85],
            "outer_wall_line_width": [0.42, 0.62],
            "filament_flow_ratio": [1.0, 0.9],
        }
        selected = a.printer_settings(source.splitlines(), resolved, tool_index=1)
        self.assertEqual(selected["nozzle_diameter"], 0.6)
        self.assertEqual(selected["filament_diameter"], 2.85)
        output, report = a.process_text(source, resolved=resolved)
        self.assertEqual(report["replaced_features"], 1, report)
        self.assertIn("T1\n; FEATURE: Bridge", output)
        self.assertTrue(output.endswith("T0\n; FEATURE: Sparse infill" + fixture().split("; FEATURE: Sparse infill",1)[1]))
        arc_block = output.split(a.MARKER + "BEGIN",1)[1].split(a.MARKER + "END",1)[0]
        arc_lines = arc_block.splitlines()
        first_extrusion_index = next(i for i,line in enumerate(arc_lines)
                                     if a.command(line)[0] == "G1"
                                     and "X" in a.command(line)[1] and "Y" in a.command(line)[1]
                                     and a.command(line)[1].get("E", 0) > 0)
        first_extrusion = a.command(arc_lines[first_extrusion_index])[1]
        travel_words = next(a.command(line)[1] for line in reversed(arc_lines[:first_extrusion_index])
                            if a.command(line)[0] == "G1" and "X" in a.command(line)[1]
                            and "Y" in a.command(line)[1] and "E" not in a.command(line)[1])
        distance = ((first_extrusion["X"] - travel_words["X"])**2
                    + (first_extrusion["Y"] - travel_words["Y"])**2)**0.5
        expected_e_per_mm = (0.6 / 2.85) ** 2 * 1.35 * 0.9
        self.assertAlmostEqual(first_extrusion["E"], distance * expected_e_per_mm, places=6)

    def test_snapmaker_style_four_tool_index_is_supported(self):
        source = fixture().replace("G90\nM83", "T0\nG90\nM83")
        source = source.replace("; FEATURE: Bridge", "T3\n; FEATURE: Bridge")
        source = source.replace("; FEATURE: Sparse infill", "T0\n; FEATURE: Sparse infill")
        resolved = {
            "nozzle_diameter": [0.4, 0.4, 0.4, 0.6],
            "filament_diameter": [1.75, 1.75, 1.75, 2.85],
            "outer_wall_line_width": [0.42, 0.42, 0.42, 0.62],
            "filament_flow_ratio": [1.0, 1.0, 1.0, 0.9],
        }
        output, report = a.process_text(source, resolved=resolved)
        self.assertEqual(report["replaced_features"], 1, report)
        self.assertIn("T3\n; FEATURE: Bridge", output)
        self.assertIn("T0\n; FEATURE: Sparse infill", output)

    def test_seam_gap_is_closed_for_support_detection(self):
        source = "G90\nM83\n; CHANGE_LAYER\nG1 Z0.2\n"
        source += "; FEATURE: Outer wall\nG1 X0 Y0.04\nG1 X20 Y0 E1\nG1 X20 Y20 E1\nG1 X0 Y20 E1\nG1 X0 Y0.08 E1\n"
        shape = a.layer_shape(a.parse(source.splitlines(True)), 0.42)
        self.assertGreater(shape.area, 399)


    def test_tool_change_inside_bridge_feature_is_preserved(self):
        source = fixture().replace("G1 X29.5 Y10.5 E0.15 F1200",
                                   "G1 X29.5 Y10.5 E0.15 F1200\nT1", 1)
        output, report = a.process_text(source)
        self.assertEqual(report["replaced_features"], 0)
        self.assertIn("T1\nG1 X29.5 Y10.9", output)

    def test_bambu_markers_do_not_hide_real_multimaterial_switches(self):
        source = fixture().replace("G90\nM83", "T1000\nT0\nG90\nM83")
        source = source.replace("; FEATURE: Bridge", "T1\n; FEATURE: Bridge")
        source = source.replace("; FEATURE: Sparse infill", "T0\nT255\n; FEATURE: Sparse infill")
        resolved = {
            "nozzle_diameter": [0.4, 0.6],
            "filament_diameter": [1.75, 2.85],
        }
        output, report = a.process_text(source, resolved=resolved)
        self.assertEqual(report["replaced_features"], 1, report)
        self.assertIn("T1\n; FEATURE: Bridge", output)
        self.assertIn("T0\nT255\n; FEATURE: Sparse infill", output)

    def test_bambu_virtual_tool_markers_are_not_physical_tool_changes(self):
        source = fixture().replace("G90\nM83", "T1000\nT0\nG90\nM83") + "T255\n"
        output, report = a.process_text(source)
        self.assertEqual(report["replaced_features"], 1)
        self.assertTrue(output.endswith("T255\n"))


    def test_full_circle_and_radius_arc_input(self):
        full = "G90\nM83\n; CHANGE_LAYER\nG1 Z0.2\n; FEATURE: Outer wall\nG1 X20 Y10\nG3 X20 Y10 I-10 J0 E1\n"
        move = a.parse(full.splitlines(True))[0].moves[-1]
        line = a.segment(move)
        self.assertTrue(line.is_ring)
        self.assertAlmostEqual(line.length, 20*a.math.pi, delta=0.1)
        for code in ("G2","G3","G02","G03"):
            text = f"G90\nM83\n; CHANGE_LAYER\nG1 Z0.2\n; FEATURE: Outer wall\nG1 X0 Y0\n{code} X20 Y0 R10 E1\n"
            line = a.segment(a.parse(text.splitlines(True))[0].moves[-1])
            self.assertAlmostEqual(line.length,10*a.math.pi,delta=0.1)

    def test_progress_message_does_not_block_injection(self):
        source = fixture().replace("G1 X29.5 Y10.5 E0.15 F1200", "M73 P10 R10\nG1 X29.5 Y10.5 E0.15 F1200")
        self.assertIn("M73 P10 R10",source)
        output,report = a.process_text(source)
        self.assertEqual(report["replaced_features"],1)
        self.assertEqual(output.count("M73 P10 R"),1)  # the remaining minutes may be shifted by the time estimate

    def test_time_estimate_follows_slower_waves(self):
        source = "; model printing time: 1m 0s; total estimated time: 2m 0s\nM73 P0 R2\nG90\nM83\n" + fixture().split("G90\nM83\n", 1)[1]
        output, report = a.process_text(source, {"overhang_mode": "wave", "wave_speed_mm_s": 1, "minimum_coverage_percent": 80})
        self.assertGreater(report["time_change_s"], 10)
        header = output.splitlines()[1]
        self.assertAlmostEqual(a.parse_duration(header.split("estimated time:")[1]), 120 + report["time_change_s"], delta=1)

    def test_scarf_projection_has_correct_hole_topology(self):
        source = "G90\nM83\n; CHANGE_LAYER\nG1 Z0.2\n"
        # Complete contour with a retraced seam tail.
        source += ring(0,0,20,20) + "G1 X5 Y0 E0.01\n" + ring(5,5,10,10)
        shape = a.layer_shape(a.parse(source.splitlines(True)),0.42)
        self.assertGreater(shape.area,374)
        self.assertLess(shape.area,376)
        self.assertFalse(shape.contains(a.Point(7,7)))

    def test_utf8_bom_file_is_supported(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path=Path(folder)/"bom.gcode"
            path.write_bytes(b"\xef\xbb\xbf"+fixture().encode("utf-8"))
            report=a.process_file(path)
            self.assertEqual(report["replaced_features"],1)


    def test_xy_extrusion_repays_wipe_retraction(self):
        source = "G90\nM83\n; CHANGE_LAYER\nG1 Z0.2\n; FEATURE: Outer wall\nG1 X0 Y0\nG1 E-.4\nG1 X1 Y0 E.7\n"
        last = a.parse(source.splitlines(True))[0].moves[-1]
        self.assertAlmostEqual(last.before.retracted,.4)
        self.assertEqual(last.after.retracted,0)

    def test_submicron_wipe_rounding_is_not_a_permanent_debt(self):
        source = "G90\nM83\n; CHANGE_LAYER\nG1 Z0.2\n; FEATURE: Outer wall\nG1 X0 Y0\nG1 E-.40027\nG1 E.4\n"
        self.assertEqual(a.parse(source.splitlines(True))[0].moves[-1].after.retracted,0)
        source = fixture().replace("G92 E0", "G92 E0\nG1 E-.40027\nG1 E.4")
        output,report=a.process_text(source)
        self.assertEqual(report["replaced_features"],1)
        self.assertIn(a.MARKER,output)

    def test_firmware_retract_and_unretract_are_supported(self):
        source = fixture().replace("G92 E0\n", "G92 E0\nG10\nG11\n", 1)
        parsed = a.parse(source.splitlines(True))
        self.assertFalse(parsed[0].moves[-1].after.firmware_retracted)
        output, report = a.process_text(source)
        self.assertEqual(report["replaced_features"], 1, report)
        self.assertIn(a.MARKER, output)

    def test_bridge_with_firmware_retract_inside_is_preserved(self):
        source = fixture()
        source = source.replace(
            "G1 X29.5 Y10.5 E0.15 F1200\n",
            "G1 X29.5 Y10.5 E0.15 F1200\nG10\n", 1)
        source = source.replace(
            "G1 X19 Y10.9 E0.15 F1200\n",
            "G11\nG1 X19 Y10.9 E0.15 F1200\n", 1)
        output, report = a.process_text(source)
        self.assertEqual(report["replaced_features"], 0, report)
        self.assertEqual(output, source)

    def test_g10_with_parameters_remains_unsupported(self):
        with self.assertRaises(a.UnsupportedGCode):
            a.parse("G90\nM83\nG10 P1 X2\n".splitlines(True))

    def test_real_unrecovered_retraction_remains_protected(self):
        cfg=a.configuration()
        printer=a.printer_settings(fixture().splitlines())
        with self.assertRaises(a.UnsupportedGCode):
            a.emit_arcs([a.LineString([(0,0),(1,0)])],
                        a.State(x=0,y=0,retracted=.4),
                        a.State(x=1,y=0,retracted=0),cfg,printer)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        out, report = a.process_text(fixture(), {"minimum_coverage_percent":80})
        (ROOT / "synthetic_before.gcode").write_text(fixture())
        (ROOT / "synthetic_after.gcode").write_text(out)
        print(report)
    sys.exit(not result.wasSuccessful())
