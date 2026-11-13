"""Coverage and final G-code motion tests for the layer player."""
from pathlib import Path
import json
import math
import runpy
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dist'))
import arc_overhang as a
fixture=runpy.run_path(str(ROOT/'tests.py'),run_name='preview_fixture')['fixture']

class PlaybackTests(unittest.TestCase):
    def large_preview(self):
        cfg=a.configuration(); printer=a.printer_settings(fixture().splitlines())
        lines=['G90\n','M83\n','G92 E0\n']; records=[]
        for layer in range(9):
            z=round(.2*(layer+1),3)
            lines+=['; CHANGE_LAYER\n',f'G1 X0 Y0 Z{z} F6000\n']
            for tool in (0,1):
                lines.append(f'T{tool}\n')
                state=a.State(x=0,y=0,z=z,relative_e=True,tool=tool)
                paths=[a.LineString([(1,y*.01),(2,y*.01)]) for y in range(301)]
                lines+=a.emit_arcs(paths,state,state,cfg,printer)
                records.append((layer,z,tool,'arc',(),a.Polygon([(0,0),(3,0),(3,4),(0,4)])))
        return a.export_preview(records,cfg,lines)
    def test_all_layers_regions_and_paths_remain_available(self):
        preview=self.large_preview()
        self.assertEqual(len(preview['layers']),18)
        self.assertEqual(len({r['layer'] for r in preview['layers']}),9)
        self.assertEqual([r['id'] for r in preview['layers']],list(range(18)))
        self.assertTrue(all(len(r['paths'])==301 for r in preview['layers']))
        self.assertGreater(sum(len(p) for r in preview['layers'] for p in r['paths']),10000)
        self.assertEqual(preview['layers'][-1]['tool'],1)
        self.assertFalse(preview['limited'])
        catalog=a.preview_catalog({'preview':preview})
        self.assertEqual(len(catalog['preview']['layers']),18)
        self.assertTrue(all('paths' not in r and 'motions' not in r and 'outlines' not in r for r in catalog['preview']['layers']))
        self.assertLess(len(json.dumps(catalog)),len(json.dumps(preview))/10)
        self.assertIn('motions',preview['layers'][0]) # catalogue did not mutate the stored report
    def test_motion_matches_final_gcode_in_both_orders_and_modes(self):
        for mode in ('arc','wave'):
            for order in ('slicer','layer_tail'):
                with self.subTest(mode=mode,order=order):
                    output,report=a.process_text(fixture(),{'overhang_mode':mode,'print_order':order,'z_hop_mm':.4})
                    region=report['preview']['layers'][0]
                    lines=output.splitlines(keepends=True)
                    start=next(i for i,l in enumerate(lines) if l.strip()==a.MARKER+'BEGIN')
                    end=next(i for i,l in enumerate(lines) if l.strip()==a.MARKER+'END')
                    moves=[m for f in a.parse(lines) for m in f.moves if start<m.index<end
                           and (math.dist((m.before.x,m.before.y,m.before.z),(m.after.x,m.after.y,m.after.z))>1e-9 or abs(m.delta_e)>1e-9)]
                    motion=[m for m in region['motions']]
                    self.assertEqual(len(moves),len(motion))
                    for actual,expected in zip(motion,moves):
                        self.assertEqual(actual[:6],[expected.before.x,expected.before.y,expected.before.z,expected.after.x,expected.after.y,expected.after.z])
                        distance=math.dist(actual[:3],actual[3:6])
                        self.assertAlmostEqual(actual[6],(distance or abs(expected.delta_e))/(expected.after.feed/60))
                    self.assertTrue(any(m[2]!=m[5] for m in motion))
                    self.assertTrue(any(m[7]==0 for m in motion))
                    self.assertTrue(any(m[7]==2 for m in motion))
    def test_dwell_is_included_in_timeline(self):
        cfg=a.configuration();printer=a.printer_settings(fixture().splitlines())
        state=a.State(x=0,y=0,z=.2,relative_e=True)
        lines=['G90\n','M83\n','; CHANGE_LAYER\n','G1 X0 Y0 Z.2\n']+a.emit_arcs([a.LineString([(0,0),(1,0)])],state,state,cfg,printer,post=['G4 P1500\n'])
        preview=a.export_preview([],cfg,lines)
        self.assertTrue(any(m[6]==1.5 and m[7]==2 for m in preview['layers'][0]['motions']))
    def test_preview_cancellation_is_honored(self):
        with self.assertRaises(a.Cancelled):
            a.export_preview([],a.configuration(),[a.MARKER+'BEGIN\n',a.MARKER+'END\n'],lambda:True)

if __name__=='__main__':unittest.main()
