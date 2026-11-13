"""Lifecycle integration: same engine, no manual export, no source-file writes."""
import json
import re
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
        self.host=host
        self.entries=[{"plugin_key":"other-plugin","capability":"Other","cap_config":{"path":'C:\\test\\file',"label":'quote " and Unicode ä'}}]
        self.preset_name='Test process';self.pipeline='"Arc Overhang"';self.updates=[]
        def escaped(value): return value.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r')
        self.escape=escaped
        def config_value(key):
            return self.pipeline if key=='slicing_pipeline_plugin' else self.escape(json.dumps(self.entries))
        self.preset=types.SimpleNamespace(name=self.preset_name,config_keys=lambda:['print_plugin_config_overrides'],config_value=config_value)
        self.bundle=types.SimpleNamespace(current_process_preset=lambda:self.preset,current_printer_preset=lambda:types.SimpleNamespace(name='Test printer'))
        def update(key,value):
            self.updates.append((key,value))
            decoded=re.sub(r'\\(.)',lambda m:{'n':'\n','r':'\r'}.get(m[1],m[1]),value)
            self.entries=json.loads(decoded)
            own=next(e for e in self.entries if e['plugin_key']=='test-plugin')
            self.cap.config=json.dumps(own['cap_config'])
        host.host=types.SimpleNamespace(preset_bundle=lambda:self.bundle,preset=types.SimpleNamespace(process=types.SimpleNamespace(update=update)),plugin=types.SimpleNamespace(storage=lambda:'/storage/test-plugin'))
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
    def test_catalog_and_region_requests_are_revision_scoped(self):
        self.fire('GCodeExportFinished')
        self.page.on_message({'action':'read','request_id':1})
        catalog=self.page.message
        region=catalog['last_report']['preview']['layers'][0]
        self.assertNotIn('motions',region)
        self.page.on_message({'action':'region','request_id':2,'config':{'id':region['id'],'revision':catalog['revision']}})
        self.assertTrue(self.page.message['ok'])
        self.assertTrue(self.page.message['region']['motions'])
        self.fire('ObjectChanged')
        self.page.on_message({'action':'region','request_id':3,'config':{'id':region['id'],'revision':catalog['revision']}})
        self.assertFalse(self.page.message['ok'])

    def test_save_invalidates_preview(self):
        self.state['publish_preview']({'generated_arcs':1})
        self.page.on_message({'action':'save','request_id':1,'config':{'arc_speed_mm_s':3}})
        self.assertTrue(self.page.message['ok'])
        self.assertEqual(self.state['_preview_state'],'stale')
        self.assertIsNone(self.state['_last_report'])


    def test_tab_save_updates_process_only_and_preserves_other_plugins(self):
        other=dict(self.entries[0])
        self.cap.save_config=lambda value:self.fail("Must not write global defaults")
        self.page.on_message({'action':'save','request_id':1,'config':{'arc_speed_mm_s':3}})
        self.assertTrue(self.page.message['ok'],self.page.message)
        self.assertEqual(self.updates[0][0],'print_plugin_config_overrides')
        self.assertEqual(self.entries[0],other)
        self.assertEqual(self.entries[-1]['cap_config']['arc_speed_mm_s'],3)
        self.page.on_message({'action':'save','request_id':2,'config':{'arc_speed_mm_s':4}})
        self.assertEqual(len(self.entries),2)

    def test_sidebar_change_is_polled_and_invalidates_old_preview(self):
        self.fire('GCodeExportFinished')
        self.page.on_message({'action':'read','request_id':1})
        self.cap.config='{"arc_speed_mm_s":3}'
        self.page.on_message({'action':'preview','request_id':2,'config':{'revision':self.page.message['revision']}})
        self.assertEqual(self.page.message['config']['arc_speed_mm_s'],3)
        self.assertEqual(self.page.message['state'],'stale')
        self.assertIsNone(self.page.message['last_report'])

    def test_profile_switch_rejects_pending_save(self):
        self.page.on_message({'action':'read','request_id':1})
        context=self.page.message['config_context']
        self.preset.name='Another process'
        self.page.on_message({'action':'save','request_id':2,'config':{'arc_speed_mm_s':3},'config_context':context})
        self.assertFalse(self.page.message['ok']);self.assertFalse(self.updates)

    def test_sidebar_conflict_rejects_stale_save(self):
        self.page.on_message({'action':'read','request_id':1})
        baseline=self.page.message['config']
        self.cap.config='{"arc_speed_mm_s":4}'
        self.page.on_message({'action':'save','request_id':2,'config':{'arc_speed_mm_s':3},'base_config':baseline})
        self.assertFalse(self.page.message['ok']);self.assertFalse(self.updates)

    def test_unsupported_host_and_inactive_pipeline_do_not_write(self):
        self.pipeline='"Another Arc Overhang"'
        self.page.on_message({'action':'save','request_id':1,'config':{'arc_speed_mm_s':3}})
        self.assertFalse(self.page.message['ok']);self.assertFalse(self.updates)
        self.host.host.preset.process.update=None
        self.page.on_message({'action':'save','request_id':2,'config':{'arc_speed_mm_s':3}})
        self.assertFalse(self.page.message['ok']);self.assertFalse(self.updates)
        self.assertEqual(self.cap.config,'{}')

    def test_failed_process_write_keeps_preview_and_config(self):
        self.fire('GCodeExportFinished')
        def reject(*args): raise ValueError('Host rejected settings')
        self.host.host.preset.process.update=reject
        self.page.on_message({'action':'save','request_id':1,'config':{'arc_speed_mm_s':3}})
        self.assertFalse(self.page.message['ok']);self.assertEqual(self.cap.config,'{}')
        self.assertEqual(self.state['_preview_state'],'ready')

if __name__=='__main__': unittest.main()
