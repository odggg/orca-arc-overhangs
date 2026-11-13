from pathlib import Path
import runpy, sys, unittest, math, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dist'))
import arc_overhang as a
fixture=runpy.run_path(str(ROOT/'tests.py'),run_name='fixtures')['fixture']
ring=runpy.run_path(str(ROOT/'tests.py'),run_name='fixtures')['ring']

class WorkbenchTests(unittest.TestCase):
    def test_context_contains_roles_tools_previous_and_curves(self):
        source=fixture()
        out,report=a.process_text(source,{'minimum_coverage_percent':80})
        context=report['preview']['contexts']['2']
        self.assertTrue({'support','outer','overhang','infill'}<=set(context['roles']))
        self.assertTrue(context['previous'])
        self.assertGreater(context['duration'],report['preview']['layers'][0]['duration'])
        self.assertNotIn('contexts',a.preview_catalog(report)['preview'])
        source='G90\nM83\n; CHANGE_LAYER\n;TYPE:Outer wall\nG1 X0 Y0 Z.2 F600\nG1 X1 Y0 E.1\nG3 X0 Y1 I-1 J0 E.1\nG4 P1000\n'
        context=a.layer_contexts(source.splitlines(True))['1']
        self.assertGreater(len(context['paths'][0]),5)
        self.assertEqual(context['motions'][-1][6:8],[1,2])
        self.assertAlmostEqual(context['paths'][0][-1][1],1)
    def test_refinement_preserves_state_and_limits_volume(self):
        printer=a.printer_settings(fixture().splitlines());printer['max_volumetric_speed']=.15
        state=a.State(x=0,y=0,z=.4,relative_e=True,modal=(('acceleration','M204 P1200 T1800\n'),('fan:1','M106 P1 S153\n')))
        paths=[a.LineString([(0,0),(2,0),(3,1)]),a.LineString([(3,1),(3,2),(4,3)])]
        cfg=a.configuration({'support_acceleration_mm_s2':200,'support_fan_override':True,'support_fan_percent':80,'initial_path_count':1,'initial_flow_percent':110,'initial_fan_percent':60,'far_speed_percent':50,'wipe_mm':.5,'connected_travel_mm':.2,'edge_coast_mm':.3})
        prefix='G90\nM83\n;CHANGE_LAYER\n;TYPE:Outer wall\nG1 X0 Y0 Z.4\nM204 P1200 T1800\nM106 P1 S153\n'
        body=a.emit_arcs(paths,state,state,cfg,printer)
        parsed=a.parse((prefix+''.join(body)).splitlines(True));end=parsed[-1].moves[-1].after
        self.assertAlmostEqual(end.e,0,places=6)
        self.assertFalse(a.is_retracted(end))
        self.assertEqual((end.x,end.y,end.z),(0,0,.4))
        self.assertEqual(dict(end.modal),dict(state.modal))
        self.assertIn('M204 S200', ''.join(body))
        for feature in parsed:
            for move in feature.moves:
                line=a.segment(move)
                if line is not None:
                    volumetric=move.delta_e*math.pi*(printer['filament_diameter']/2)**2/(line.length/(move.after.feed/60))
                    self.assertLessEqual(volumetric,.1501)
    def test_local_slowdown_splits_boundary_preserves_extrusion(self):
        cfg=a.configuration({'upper_slowdown_layers':2,'upper_speed_percent':40})
        source='G90\nM83\n;CHANGE_LAYER\n;TYPE:Bridge\nG1 X0 Y0 Z.2 F600\n'+a.MARKER+'BEGIN\nG1 X5 Y0 E1\n'+a.MARKER+'END\n;CHANGE_LAYER\n;TYPE:Internal solid infill\nG1 X-5 Y0 Z.4 F3000\nG1 X10 Y0 E3 F3000\nG1 X10 Y10 E2\n'
        source=fixture().split('; CHANGE_LAYER')[0]+source
        out,count=a.slowdown_above_support(source.splitlines(True),cfg,lambda:False)
        self.assertEqual(count,1)
        moves=[m for f in a.parse(out) if f.layer==1 for m in f.moves if a.segment(m) is not None]
        self.assertAlmostEqual(sum(m.delta_e for m in moves),5,places=7)
        slow=[m for m in moves if m.after.feed<3000]
        self.assertTrue(slow)
        self.assertTrue(all(-.201<=m.after.x<=5.201 for m in slow))
        self.assertEqual(moves[-1].after.feed,3000)
    def test_profiles_are_tool_specific_and_capped(self):
        source=fixture().splitlines()+['; filament_type = PLA;PETG-CF','; fan_max_speed = 90;25']
        s=a.profile_suggestions(source,{'nozzle_diameter':[.4,.6],'filament_max_volumetric_speed':[1,.1]},1)
        self.assertEqual(s['material'],'PETG-CF');self.assertEqual(s['nozzle'],.6)
        self.assertEqual(s['values']['support_fan_percent'],25)
        self.assertLess(s['values']['arc_speed_mm_s'],1)
    def test_removable_rejects_insufficient_space_without_modifying_source(self):
        source=fixture();out,report=a.process_text(source,{'support_mode':'removable'})
        self.assertEqual(source,out);self.assertTrue(report['skip_reasons'])
    def removable_fixture(self):
        # Undercut: the intermediate layer recedes, leaving space for the floor.
        source=fixture();header,first,second=source.split('; CHANGE_LAYER\n')
        middle='G1 Z0.4\n'+ring(10,10,17,30)
        second=second.replace('G1 Z0.4','G1 Z0.6')
        return header+'; CHANGE_LAYER\n'+first+'; CHANGE_LAYER\n'+middle+'; CHANGE_LAYER\n'+second
    def test_removable_keeps_original_bridge_and_restores_state(self):
        source=self.removable_fixture()
        out,report=a.process_text(source,{'support_mode':'removable','minimum_coverage_percent':80})
        self.assertEqual(report['removable_floors'],1,report['skip_reasons'])
        self.assertIn('G1 X29.5 Y10.5 E0.15 F1200',out)
        paths=report['preview']['layers'][0]
        self.assertAlmostEqual(paths['z'],.3)
        self.assertLess(out.index(a.MARKER+'BEGIN'),out.index('G1 Z0.4'))
        original=a.parse(source.splitlines(True))[-1].moves[-1].after
        result=a.parse(out.splitlines(True))[-1].moves[-1].after
        self.assertEqual(original,result)
        self.assertEqual(a.process_text(out)[0],out)
    def test_removable_collision_and_tool_mismatch_are_kept(self):
        source=self.removable_fixture().replace(ring(10,10,17,30),ring(10,10,20,30))
        out,report=a.process_text(source,{'support_mode':'removable','minimum_coverage_percent':80})
        self.assertEqual(source,out);self.assertTrue(any('overlaps' in r for r in report['skip_reasons']))
        source=self.removable_fixture().replace('G1 Z0.6','T1\nG1 Z0.6')
        out,report=a.process_text(source,{'support_mode':'removable','minimum_coverage_percent':80})
        self.assertEqual(out,source);self.assertTrue(any('tool' in r for r in report['skip_reasons']))
    def test_adaptive_paths_stay_connected_and_cancel(self):
        support=a.Polygon([(0,0),(1,0),(1,4),(0,4)])
        paths=[a.LineString([(1,0),(1,4)]),a.LineString([(1.3,0),(1.3,4)]),a.LineString([(1.6,0),(1.6,4)])]
        result=a.adaptive_order(list(reversed(paths)),support,.4)
        self.assertTrue(result[0].equals(paths[0]))
        with self.assertRaises(a.Cancelled): a.adaptive_order(paths,support,.4,lambda:True)
    def test_cooling_coast_and_connected_travel(self):
        p=a.printer_settings(fixture().splitlines());state=a.State(x=0,y=0,z=.4,relative_e=True)
        paths=[a.LineString([(0,0),(2,0),(3,1)]),a.LineString([(3,1),(4,2)])]
        support=a.Polygon([(-1,-1),(.1,-1),(.1,1),(-1,1)])
        cfg=a.configuration({'connected_travel_mm':.2,'path_cooling_s':10,'edge_coast_mm':.5,'wipe_mm':.5})
        body=''.join(a.emit_arcs(paths,state,state,cfg,p,support=support))
        self.assertIn('G4 P',body)
        # One initial retract plus the final return; the exact connector needs none.
        self.assertEqual(body.count('G1 E-'),2)
        self.assertIn('G1 X4.00000 Y2.00000\n',body)
        # A supported endpoint must never be coasted.
        body=''.join(a.emit_arcs([paths[0]],state,state,cfg,p,support=a.Polygon([(-2,-2),(5,-2),(5,5),(-2,5)])))
        self.assertNotIn('G1 X3.00000 Y1.00000\n',body)
    def test_curved_slowdown_preserves_shape_and_tool_selection(self):
        cfg=a.configuration({'upper_slowdown_layers':1,'upper_speed_percent':50})
        header=fixture().split('; CHANGE_LAYER')[0]
        source=header+';CHANGE_LAYER\n;TYPE:Bridge\nG1 X0 Y0 Z.2 F600\n'+a.MARKER+'BEGIN\nG1 X1 Y0 E1\n'+a.MARKER+'END\n;CHANGE_LAYER\n;TYPE:Outer wall\nG1 X1 Y0 Z.4 F3000\nG3 X0 Y1 I-1 J0 E2 F3000\nT1\n;TYPE:Outer wall\nG1 X1 Y0 F3000\nG3 X0 Y1 I-1 J0 E2 F3000\n'
        out,count=a.slowdown_above_support(source.splitlines(True),cfg,lambda:False)
        self.assertEqual(count,1)
        moves=[m for f in a.parse(out) if f.layer==1 for m in f.moves if a.segment(m) is not None]
        t0=[m for m in moves if m.after.tool==0];t1=[m for m in moves if m.after.tool==1]
        self.assertAlmostEqual(sum(m.delta_e for m in t0),2,places=7)
        self.assertTrue(any(m.after.feed==1500 for m in t0))
        self.assertTrue(all(abs(math.hypot(m.after.x,m.after.y)-1)<.011 for m in t0))
        self.assertTrue(all(m.after.feed==3000 and m.command=='G3' for m in t1))
    def test_refinements_integrate_with_both_schedules_and_engines(self):
        source=fixture()
        original=a.parse(source.splitlines(True))[-1].moves[-1].after
        for mode in ('arc','wave'):
            for order in ('layer_tail','slicer'):
                with self.subTest(mode=mode,order=order):
                    out,r=a.process_text(source,{'overhang_mode':mode,'print_order':order,'adaptive_paths':True,'minimum_coverage_percent':80,'far_speed_percent':70,'connected_travel_mm':.2,'initial_path_count':2,'initial_flow_percent':105})
                    self.assertEqual(r['replaced_features'],1,r)
                    final=a.parse(out.splitlines(True))[-1].moves[-1].after
                    self.assertEqual(a.replace(final,e=0),a.replace(original,e=0))
                    self.assertAlmostEqual(final.e,original.e,places=6)
    def test_missing_modal_state_does_not_invent_acceleration_or_fan(self):
        cfg=a.configuration({'support_acceleration_mm_s2':200,'support_fan_override':True,'support_fan_percent':60})
        state=a.State(x=0,y=0,z=.2,relative_e=True);p=a.printer_settings(fixture().splitlines())
        body=''.join(a.emit_arcs([a.LineString([(0,0),(1,0)])],state,state,cfg,p))
        self.assertNotIn('M204',body);self.assertNotIn('M106',body)
    def test_invalid_extension_values_rejected(self):
        for values in ({'support_mode':'auto'},{'upper_speed_percent':0},{'initial_flow_percent':200},{'upper_slowdown_layers':1.2},{'peel_gap_mm':1}):
            with self.subTest(values=values),self.assertRaises(ValueError): a.configuration(values)
if __name__=='__main__':unittest.main()
