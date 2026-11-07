const fs=require('fs'),vm=require('vm'),assert=require('assert');
const hostPath=process.env.ORCA_CONFIG_BRIDGE_PATH||'C:/Program Files/OrcaSlicer/resources/web/dialog/js/plugin-config-ui.js';
const hostSource=fs.readFileSync(hostPath,'utf8');
const html=fs.readFileSync('config-preview.html','utf8');
assert(!/<form\b/i.test(html),'Native config frame forbids forms');
assert(/id="save" type="button"/.test(html));
const source=html.match(/<script>([\s\S]*)<\/script>/)[1];
const defaults=JSON.parse(source.match(/const defaults = (.*);/)[1]);
async function check(scope){
 const elements=Object.fromEntries([...Object.keys(defaults),'settings','status','refresh','save','last-report','import','import_text','orca-host-theme-vars'].map(k=>[k,{value:'',checked:false,textContent:''}]));
 const events={};let nativeSave=null,timerID=0;
 const timers=new Map();
 const doc={hidden:false,getElementById:k=>elements[k],addEventListener(){},
 documentElement:{getAttribute:()=> 'light',setAttribute(){}}};
 const context={document:doc,window:{addEventListener:(event,cb)=>{events[event]=cb;}},
 parent:{postMessage:msg=>{nativeSave=msg;}},
 setTimeout:cb=>{timers.set(++timerID,cb);return timerID;},clearTimeout:id=>timers.delete(id)};
 context.window.window=context.window;
 vm.createContext(context);
 vm.runInContext(hostSource,context);
 const combined=context.BuildCustomConfigDocument(html,{arc_speed_mm_s:10},{scope,readOnly:false});
 for(const match of combined.matchAll(/<script>([\s\S]*?)<\/script>/g)) vm.runInContext(match[1],context);
 await new Promise(setImmediate);
 assert.equal(elements.arc_speed_mm_s.value,10);
 elements.arc_speed_mm_s.value=10.5;
 const saving=elements.save.onclick();
 await new Promise(setImmediate);
 assert.equal(nativeSave.__orca,'save');
 assert.equal(nativeSave.config.arc_speed_mm_s,10.5);
 assert.notEqual(elements.status.textContent,'Saved.','Must wait for real host acknowledgement');
 events.message({data:{__orca:'config',config:nativeSave.config}});
 await saving;
 assert.equal(elements.status.textContent,'Saved.');
 assert.equal(timers.size,0);
 elements.minimum_arc_speed_mm_s.value=20;nativeSave=null;
 await elements.save.onclick();
 assert.equal(nativeSave,null);
 elements.minimum_arc_speed_mm_s.value=.5;
 const waiting=elements.save.onclick();
 await new Promise(setImmediate);
 for(const cb of [...timers.values()])cb();
 await waiting;
 assert.match(elements.status.textContent,/No save acknowledgement/);
 events.message({data:{__orca:'config',config:defaults,context:{scope,readOnly:true}}});
 await elements.save.onclick();
 assert.match(elements.status.textContent,/read-only/);
 console.log('Installed Orca bridge passed:',scope,'button, acknowledgement, timeout, validation, read-only.');
}
(async()=>{await check('preset');await check('global');})().catch(e=>{console.error(e);process.exitCode=1;});
