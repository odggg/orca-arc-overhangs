from pathlib import Path
p=Path(__file__).parent/'tests.py'
s=p.read_text()
methods = '''
    def test_split_outer_overhang_wall_ring(self):
        source = "G90\\nM83\\n; CHANGE_LAYER\\nG1 Z0.2\\n"
        source += "; FEATURE: Outer wall\\nG1 X0 Y0\\nG1 X20 Y0 E1\\nG1 X20 Y20 E1\\n"
        source += "; FEATURE: Overhang wall\\nG1 X0 Y20 E1\\nG1 X0 Y0 E1\\n"
        shape = a.layer_shape(a.parse(source.splitlines(True)), 0.42)
        self.assertAlmostEqual(shape.area, 400)

    def test_other_bridge_in_same_layer_is_preserved(self):
        interior = "; FEATURE: Bridge\\nG1 X12 Y12 F1800\\nG1 X14 Y12 E0.1\\nG1 X14 Y13 E0.1\\nG1 X12 Y13 E0.1\\n"
        source = fixture() + interior
        output, report = a.process_text(source)
        self.assertEqual(report["replaced_features"], 1)
        self.assertEqual(report["skipped_features"], 1)
        self.assertTrue(output.endswith(interior))

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
        block = source.split("# /// script\\n",1)[1].split("# ///",1)[0]
        metadata = tomllib.loads("\\n".join(line[2:] for line in block.splitlines()))
        self.assertEqual(metadata["tool"]["orcaslicer"]["plugin"]["version"], a.VERSION)
        self.assertEqual(len(metadata["dependencies"]), 2)
        calls = []
        class Capability:
            def get_config(self): return "{}"
        result = types.SimpleNamespace(success=lambda *v:("success",v), skipped=lambda *v:("skipped",v),
                                       failure=lambda *v:("failure",v))
        host = types.ModuleType("orca")
        host.base = type("Base", (), {})
        host.plugin = lambda cls:cls
        host.register_capability = calls.append
        host.slicing = types.SimpleNamespace(SlicingPipelineCapabilityBase=Capability, Step=types.SimpleNamespace(psGCodePostProcess=99))
        host.ExecutionResult = result
        host.PluginResult = types.SimpleNamespace(FatalError="fatal")
        with patch.dict(sys.modules, {"orca":host}):
            namespace = runpy.run_path(str(file), run_name="plugin_test")
        namespace["ArcOverhangPlugin"]().register_capabilities()
        self.assertEqual(len(calls), 1)
        capability = calls[0]()
        self.assertEqual(capability.get_name(), "Arc Overhang")
        self.assertEqual(capability.get_default_config(), a.DEFAULTS)
        self.assertTrue(capability.has_config_ui())
        self.assertIn("window.orca.saveConfig", capability.get_config_ui())
        self.assertEqual(capability.execute(types.SimpleNamespace(step=0))[0], "skipped")
        ctx = types.SimpleNamespace(step=99, config_value=lambda key:None, gcode_path="missing-file.gcode", cancelled=lambda:False)
        self.assertEqual(capability.execute(ctx)[0], "failure")

    def test_missing_settings_and_unsupported_modes(self):
        for source in (fixture().replace("; nozzle_diameter = 0.4\\n",""),
                       fixture().replace("M83","M83\\nG20"),
                       fixture().replace("M83","M83\\nT1"),
                       fixture().replace("; nozzle_diameter = 0.4","; nozzle_diameter = 0.4;0.6")):
            with self.subTest(source=source[:60]), self.assertRaises(a.UnsupportedGCode):
                a.process_text(source)

'''
s=s.replace('if __name__ == "__main__":',methods+'if __name__ == "__main__":')
p.write_text(s,encoding='utf-8')
