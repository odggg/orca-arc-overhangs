const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('tab-preview.html','utf8');
const source=html.match(/<script>([\s\S]*)<\/script>/)[1];
const defaults=JSON.parse(source.match(/const defaults = (.*);/)[1]);
const elements=Object.fromEntries([...Object.keys(defaults),'settings','status','refresh','save','last-report','import','import_text'].map(k=>[k,{value:'',checked:false,textContent:'',dataset:{},addEventListener(){}}]));
let receive,visibility;
let stored={arc_speed_mm_s:10},fail=false,override=false;
const requests=[];
const store={};
const context={
 setTimeout,clearTimeout,
 localStorage:{getItem:k=>store[k]??null,setItem:(k,v)=>{store[k]=v;},removeItem:k=>{delete store[k];}},
 document:{hidden:false,getElementById:k=>elements[k],addEventListener:(event,cb)=>{visibility=cb;}},
 window:{orca:{
  onMessage:cb=>{receive=cb;},
  postMessage:request=>{
    requests.push(request);
    queueMicrotask(()=>{
      if(fail) return receive({request_id:request.request_id,ok:false,error:'Save rejected'});
      if(request.action==='save') stored=JSON.parse(JSON.stringify(request.config));
      receive({request_id:request.request_id,ok:true,config:stored,preset_override_active:override});
    });
  }
 }}
};
vm.runInNewContext(source,context);
const tick=()=>new Promise(setImmediate);
(async()=>{
 await tick();
 assert.equal(requests[0].action,'read');
 assert.equal(elements.arc_speed_mm_s.value,10);
 assert.equal(elements.wall_overlap_mm.value,0.2);
 assert.equal(elements.next_layer_pattern.value,'slicer');
 assert.equal(elements.print_order.value,'layer_tail');
 elements.print_order.value='slicer';
 elements.next_layer_pattern.value='hilbert';
 elements.arc_speed_mm_s.value=12;
 await elements.save.onclick();
 assert.equal(stored.arc_speed_mm_s,12);
 assert.equal(stored.wall_overlap_mm,0.2);
 assert.equal(stored.next_layer_pattern,'hilbert');
 assert.equal(stored.print_order,'slicer');
 assert.equal(elements.status.textContent,'Saved.');
 fail=true;
 await elements.save.onclick();
 assert.match(elements.status.textContent,/Save failed: Save rejected/);
 fail=false;override=true;
 await elements.save.onclick();
 assert.match(elements.status.textContent,/active preset/);
 stored={arc_speed_mm_s:7};
 await elements.refresh.onclick();
 assert.equal(elements.arc_speed_mm_s.value,7);
 stored={arc_speed_mm_s:8};
 visibility();
 await tick();
 assert.equal(elements.arc_speed_mm_s.value,8);
 // unsaved edits survive a focus change
 elements.wave_pattern.value='zigzag';
 // gallery profile import (WaveOverhangs #142)
 elements.import_text.value=`; wave_overhang_pattern = zigzag
; wave_overhang_line_spacing = 0.35
; wave_overhang_perimeter_overlap = 0.15
; wave_overhang_floor_use_hilbert = 1
; wave_overhang_floor_hilbert_layers = 2
; wave_overhang_floor_hilbert_density = 50
; wave_overhang_floor_print_speed = 20
; wave_overhang_floor_fan_speed = 0
; wave_overhang_unknown_thing = 3`;
 elements.import.onclick();
 assert.equal(elements.wave_pattern.value,'zigzag');
 assert.equal(elements.wave_line_spacing_mm.value,0.35);
 assert.equal(elements.wave_perimeter_overlap_mm.value,0.15);
 assert.equal(elements.wave_floor_use_hilbert.checked,true);
 assert.equal(elements.wave_floor_hilbert_layers.value,2);
 assert.equal(elements.wave_floor_hilbert_density_percent.value,50);
 assert.equal(elements.wave_floor_print_speed_mm_s.value,20);
 assert.equal(elements.wave_floor_fan_override.checked,true);
 assert.equal(elements.wave_floor_fan_percent.value,0);
 assert.equal(elements.overhang_mode.value,'wave');
 assert.equal(elements.import_text.value,'','import box is cleared');
 assert.match(elements.status.textContent,/wave_overhang_unknown_thing/);
 // gallery entry "Wave settings" section (labels with values on the next line)
 elements.import_text.value=`### Wave settings
Wave perimeters
: -
Line spacing
: 0\\.35 mm
Wave flow
: 0.15 mm³/mm
Print speed: 2 mm/s
Fan speed
: 100 %
Replace bridges
: no`;
 elements.import.onclick();
 assert.equal(elements.wave_line_spacing_mm.value,0.35);
 assert.equal(elements.wave_flow_mm3_per_mm.value,0.15);
 assert.equal(elements.wave_speed_mm_s.value,2);
 assert.equal(elements.wave_fan_override.checked,true);
 assert.equal(elements.wave_fan_percent.value,100);
 assert.equal(elements.wave_instead_of_bridges.checked,false);
 // config block of a print sliced by the plugin itself: no wave keys, specific message
 elements.import_text.value='; plugins = "orca_arc_overhang-0.3.0-py3-none-any;;Arc Overhang"\n; layer_height = 0.2';
 elements.import.onclick();
 assert.match(elements.status.textContent,/debug header/);
 assert.equal(elements.import_text.value,'; plugins = "orca_arc_overhang-0.3.0-py3-none-any;;Arc Overhang"\n; layer_height = 0.2','failed import keeps the pasted text');
 visibility();
 await tick();
 assert.equal(elements.wave_line_spacing_mm.value,0.35,'draft must survive refocus');
 console.log('Tab bridge: initial read, shared save, rejected save, profile warning, refresh, draft and gallery import passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
