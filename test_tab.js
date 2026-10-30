const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('tab-preview.html','utf8');
const source=html.match(/<script>([\s\S]*)<\/script>/)[1];
const defaults=JSON.parse(source.match(/const defaults = (.*);/)[1]);
const elements=Object.fromEntries([...Object.keys(defaults),'settings','status','refresh','save','last-report'].map(k=>[k,{value:'',checked:false,textContent:''}]));
let receive,visibility;
let stored={arc_speed_mm_s:10},fail=false,override=false;
const requests=[];
const context={
 setTimeout,clearTimeout,
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
 elements.next_layer_pattern.value='hilbert';
 elements.arc_speed_mm_s.value=12;
 await elements.save.onclick();
 assert.equal(stored.arc_speed_mm_s,12);
 assert.equal(stored.wall_overlap_mm,0.2);
 assert.equal(stored.next_layer_pattern,'hilbert');
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
 console.log('Tab bridge: initial read, shared save, rejected save, profile warning and refresh passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
