"""Lifecycle integration: same engine, no manual export, no source-file writes."""
import json
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'dist'))
# tests.py shares its name with this directory; load the fixture explicitly.
fixture=runpy.run_path(str(ROOT/'tests.py'),run_name='preview_fixture')['fixture']

class SlicePreviewTests(unittest.TestCase):
    def setUp(self):
        class Capability:
            config='{}'
            def get_config(self): return self.config
            def save_config(self,value): self.config=value; return True
            def post_message(self,value): self.message=value
        self.events=types.SimpleNamespace(**{name:name for name in ['SliceStarted','GCodeExportFinished','SlicingJobComplete','ObjectChanged','PlateSelected','PresetSelected']})
        self.codes=types.SimpleNamespace(Ok='ok',Error='error',Warn='warn')
        host=types.ModuleType('orca');host.base=object;host.plugin=lambda cls:cls
        host.register_capability=lambda cls:None
        host.LifecycleEvent=self.events;host.LifecycleEvtCode=self.codes
        host.slicing=types.SimpleNamespace(SlicingPipelineCapabilityBase=Capability,Step=types.SimpleNamespace(psGCodePostProcess=99))
        host.pages=types.SimpleNamespace(PagesPluginCapabilityBase=Capability)
        host.ExecutionResult=types.SimpleNamespace(success=lambda *x:x,skipped=lambda *x:x,failure=lambda *x:x)
        host.PluginResult=types.SimpleNamespace(FatalError='fatal')
        with patch.dict(sys.modules,{'orca':host}):
            self.ns=runpy.run_path(str(ROOT/'dist/arc_overhang.py'),run_name='slice_test')
        self.cap=self.ns['ArcOverhangCapability']();self.cap.on_load()
        self.page=self.ns['ArcOverhangPage']()
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.file=Path(self.tmp.name)/'internal.gcode'
        self.original=fixture().encode('utf-8');self.file.write_bytes(self.original)
        self.ctx=types.SimpleNamespace(code='ok',msg=str(self.file),id='model',name='test')
        self.state=self.cap.on_lifecycle_event.__globals__
    def fire(self,name): self.cap.on_lifecycle_event(getattr(self.events,name),self.ctx)
    def test_successful_slice_populates_preview_without_changing_gcode(self):
        self.fire('SliceStarted');self.fire('GCodeExportFinished')
        self.assertEqual(self.state['_preview_state'],'ready')
        report=self.state['_last_report']
        self.assertGreater(report['generated_arcs'],0)
        self.assertTrue(report['preview']['layers'])
        self.assertEqual(self.file.read_bytes(),self.original)
        expected=self.ns['process_text'](self.original.decode())[1]
        self.assertEqual(report,expected)
    def test_new_slice_and_model_changes_clear_old_preview(self):
        for name in ['SliceStarted','ObjectChanged','PlateSelected','PresetSelected']:
            self.state['publish_preview']({'preview':{'layers':[{}]}})
            self.fire(name)
            self.assertIsNone(self.state['_last_report'])
    def test_failed_or_cancelled_slice_does_not_read_file(self):
        self.ctx.code='error';self.ctx.msg='not-a-file\nError'
        self.fire('GCodeExportFinished')
        self.assertEqual(self.state['_preview_state'],'failed')
        self.ctx.code='warn';self.fire('SlicingJobComplete')
        self.assertEqual(self.state['_preview_state'],'cancelled')
    def test_disabled_plugin_does_not_read_file(self):
        self.cap.config='{"enabled":false}';self.ctx.msg='missing.gcode'
        self.fire('GCodeExportFinished')
        self.assertEqual(self.state['_preview_state'],'disabled')
    def test_binary_input_fails_preview_without_mutation(self):
        self.file.write_bytes(b'PKbroken')
        self.fire('GCodeExportFinished')
        self.assertEqual(self.state['_preview_state'],'failed')
        self.assertEqual(self.file.read_bytes(),b'PKbroken')
    def test_stale_calculation_cannot_replace_new_state(self):
        def interrupted(*args):
            self.fire('ObjectChanged')
            return {'generated_arcs':999}
        with patch.dict(self.state,{'preview_file':interrupted}):
            self.fire('GCodeExportFinished')
            self.assertEqual(self.state['_preview_state'],'stale')
            self.assertIsNone(self.state['_last_report'])
    def test_poll_only_sends_geometry_when_revision_changes(self):
        self.fire('GCodeExportFinished')
        self.page.on_message({'action':'preview','request_id':1,'config':{'revision':None}})
        first=self.page.message
        self.assertTrue(first['changed']);self.assertIn('preview',first['last_report'])
        self.page.on_message({'action':'preview','request_id':2,'config':{'revision':first['revision']}})
        self.assertFalse(self.page.message['changed']);self.assertNotIn('last_report',self.page.message)
    def test_resolved_configuration_is_copied_in_pipeline_scope(self):
        self.cap.execute(types.SimpleNamespace(step=1,config_value=lambda key:'0.6' if key=='nozzle_diameter' else None))
        self.assertEqual(self.cap._slice_resolved['nozzle_diameter'],'0.6')
        self.fire('SliceStarted');self.assertIsNone(self.cap._slice_resolved)
    def test_save_invalidates_preview(self):
        self.state['publish_preview']({'generated_arcs':1})
        self.page.on_message({'action':'save','request_id':1,'config':{'arc_speed_mm_s':3}})
        self.assertTrue(self.page.message['ok'])
        self.assertEqual(self.state['_preview_state'],'stale')
        self.assertIsNone(self.state['_last_report'])

if __name__=='__main__': unittest.main()
