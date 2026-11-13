const defaults = __DEFAULTS__;
const IMPORT = __IMPORT__;
const ALIASES = __ALIASES__;
const fields = Object.keys(defaults);
const $ = id => document.getElementById(id);
const all = selector => Array.from(document.querySelectorAll?.(selector) || []);
const status = $('status');
let previewRevision = null, previewPollBusy = false;
let draft = null, ready = false, savingUI = false, lastReport = null, showWholeLayer = false;
function text(id, value) { const el=$(id); if(el) el.textContent=value; }
function collect() {
  const values={};
  for(const key of fields) {
    const el=$(key); if(!el) continue;
    values[key]=typeof defaults[key]==='boolean'?el.checked:(typeof defaults[key]==='string'?el.value:Number(el.value));
  }
  return values;
}
function selectView(name) {
  for(const view of all('.app-view')) view.hidden=view.id!=='view-'+name;
  for(const button of all('[data-view]')) {
    if(button.dataset.view===name) button.setAttribute('aria-current','page');
    else button.removeAttribute('aria-current');
  }
  if(name==='guide') renderGuide();
}
function renderState() {
  const disabled=$('processing-note'); if(disabled) disabled.hidden=!!$('enabled')?.checked;
  const wave=$('overhang_mode')?.value==='wave';
  for(const section of all('[data-mode]')) section.hidden=section.dataset.mode!==(wave?'wave':'arc');
  text('mode-note',wave?'Offset fronts grow from the supported edge. Wave mode is experimental.':'Concentric paths connect to the previous layer and extend into the overhang.');
  const removable=$('support_mode')?.value==='removable';
  for(const key of ['print_order','next_layer_pattern'])if($(key))$(key).disabled=readonly()||removable;
  const slicer=$('print_order')?.value==='slicer';
  const labels=removable?['Lower layer','Removable floor','Original model paths']:slicer?['Slicer sequence','Bridge → support','Early overhang walls follow']:['Walls + infill',wave?'Waves':'Arcs','Overhang walls'];
  all('#sequence li').forEach((el,index)=>{el.textContent=labels[index];});
  text('sequence-note',removable?'Experimental floor inserted earlier when space permits. The original model paths and infill pattern are retained.':slicer?'Normal walls and infill stay in their sliced positions. Early Overhang walls follow the support.':'The previous order is kept within each layer and tool section.');
  const note=$('floor-note'); if(note) note.hidden=!(wave && $('wave_floor_use_hilbert')?.checked);
  renderGuide(); renderPreviewWarning(); renderParameterGuide();
}
function renderGuide() {
  const group=$('guide-paths'); if(!group) return;
  const wave=$('overhang_mode')?.value==='wave';
  const raw=Number($(wave?'wave_line_spacing_mm':'arc_spacing_nozzle_ratio')?.value);
  const spacing=Number.isFinite(raw)?Math.max(.05,Math.min(1.5,raw)):0.4;
  const count=Math.max(8,Math.min(30,Math.round(13/spacing)));
  while(group.firstChild) group.removeChild(group.firstChild);
  for(let i=0;i<count;i++) {
    const path=document.createElementNS('http://www.w3.org/2000/svg','path');
    const step=400/count, x=193+i*step;
    path.setAttribute('d',wave?`M${x} 32 C${x+25} 83 ${x+25} 173 ${x} 224`:`M190 ${224-i*2} Q${190+i*4} ${32-i*1.2} ${Math.min(588,205+i*step)} 32`);
    group.appendChild(path);
  }
  text('guide-heading',wave?'Wave fronts':'Concentric Arcs');
  text('guide-title',wave?'A front that grows from support.':'Connected paths, built outwards.');
  text('guide-note',wave?'Each front grows from supported material. Flow, spacing and cooling affect adhesion; this drawing explains the pattern and does not predict print quality.':'The first path starts on existing support. Later paths connect to material already laid down. The actual geometry is calculated from the Bridge regions of your sliced model.');
  text('spacing-readout',wave?`${raw===0?'Nozzle ratio':Number.isFinite(raw)?raw:'—'}${raw===0?'':' mm'}`:`${Number.isFinite(raw)?raw:'—'} × nozzle`);
}
function renderPreviewWarning() {
  const el=$('preview-warning'); if(!el) return;
  const snapshot=lastReport?.preview, values=collect();
  const different=snapshot?.settings && fields.some(key=>snapshot.settings[key]!==undefined && snapshot.settings[key]!==values[key]);
  el.hidden=!different;
  el.textContent=different?'Settings changed. Save and slice again to update the preview.':'';
}
let activeRegion=null, previewScene=null, playbackTime=0, playbackFrame=null, lastFrameTime=null;
let regionRequest=0, selectedRegionId=null, previewLayerKeys=[];
const regionKey=region=>`${region.layer}:${region.z}`;
function previewRegions() { return lastReport?.preview?.layers||[]; }
function stopPlayback() {
  if(playbackFrame!==null && typeof cancelAnimationFrame==='function') cancelAnimationFrame(playbackFrame);
  playbackFrame=null;lastFrameTime=null;
  text('preview-play','Play');$('preview-play')?.setAttribute('aria-label','Play print animation');
}
function playbackEnabled(enabled) {
  for(const id of ['preview-play','preview-reset','preview-progress']) if($(id)) $(id).disabled=!enabled;
}
function clearDrawing() {
  for(const id of ['export-paths','export-outlines','preview-travels','preview-context','preview-previous']) $(id)?.replaceChildren();
  $('preview-nozzle')?.setAttribute('hidden','');
}
function fillRegionChoices(layerKey, preferred=null) {
  const select=$('preview-region');if(!select) return;
  const regions=previewRegions().filter(region=>regionKey(region)===layerKey);
  select.replaceChildren();
  for(const region of regions) {
    const option=document.createElement('option');option.value=String(region.id);
    option.textContent=`Overhang ${region.id+1} · T${region.tool} · ${region.path_count??region.paths?.length??0} paths`;
    select.appendChild(option);
  }
  select.disabled=!regions.length;
  select.value=String(regions.some(region=>region.id===preferred)?preferred:regions[0]?.id??'');
  const slider=$('preview-layer-range');if(slider) slider.value=String(Math.max(0,previewLayerKeys.indexOf(layerKey)));
  loadPreviewRegion(Number(select.value));
}
function populatePreviewChoices() {
  const select=$('preview-layer');if(!select) return;
  const regions=previewRegions();
  previewLayerKeys=[...new Set(regions.map(regionKey))].sort((a,b)=>Number(a.split(':')[1])-Number(b.split(':')[1])||Number(a.split(':')[0])-Number(b.split(':')[0]));
  const previous=regions.find(region=>region.id===selectedRegionId);
  select.replaceChildren();
  for(const key of previewLayerKeys) {
    const region=regions.find(item=>regionKey(item)===key), option=document.createElement('option');
    option.value=key;option.textContent=`Layer ${region.layer} · Z ${region.z} mm`;select.appendChild(option);
  }
  select.disabled=!regions.length;
  if(!regions.length) {
    const option=document.createElement('option');option.textContent='No overhang layers';select.appendChild(option);
  } else select.value=previous?regionKey(previous):previewLayerKeys[0];
  const slider=$('preview-layer-range');if(slider){slider.max=String(Math.max(0,previewLayerKeys.length-1));slider.disabled=previewLayerKeys.length<2;}
  fillRegionChoices(select.value,previous?.id);
}
async function loadPreviewRegion(id) {
  stopPlayback();const token=++regionRequest,revision=previewRevision;
  activeRegion=null;previewScene=null;clearDrawing();playbackEnabled(false);
  const regions=previewRegions(),entry=regions.find(region=>region.id===id);
  selectedRegionId=entry?.id??null;
  const position=regions.indexOf(entry);
  if($('preview-prev')) $('preview-prev').disabled=position<=0;
  if($('preview-next')) $('preview-next').disabled=position<0||position>=regions.length-1;
  if($('preview-empty')) $('preview-empty').hidden=!!entry;
  if($('preview-fit')) $('preview-fit').disabled=!entry;
  if(!entry) {text('preview-progress-label','No toolpaths loaded');return;}
  text('preview-caption','Loading overhang…');
  try {
    const region=entry.paths?entry:(await settingsBridge.getRegion(id,revision)).region;
    if(token!==regionRequest || revision!==previewRevision) return;
    activeRegion=region;playbackTime=Number(region.duration)||0;
    renderSnapshot();
  } catch(error) {
    if(token===regionRequest) text('preview-caption',error.message||'Could not load this overhang.');
  }
}
function moveRegion(direction) {
  const regions=previewRegions(),index=regions.findIndex(region=>region.id===selectedRegionId);
  const next=regions[index+direction];if(!next)return;
  $('preview-layer').value=regionKey(next);fillRegionChoices(regionKey(next),next.id);
}
function makePolyline(group,line) {
  const poly=document.createElementNS('http://www.w3.org/2000/svg','polyline');
  poly.setAttribute('points',line.map(point=>projectPoint(point).join(',')).join(' '));group.appendChild(poly);return poly;
}
function renderSnapshot() {
  const region=displayRegion(),canvas=$('export-drawing');if(!canvas)return;
  clearDrawing();
  if(!region){canvas.setAttribute('viewBox','0 0 480 340');return;}
  const showTravel=!!$('preview-show-travel')?.checked;
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
  function include(point){point=projectPoint(point);if(!point||!Number.isFinite(point[0])||!Number.isFinite(point[1]))return;minX=Math.min(minX,point[0]);maxX=Math.max(maxX,point[0]);minY=Math.min(minY,point[1]);maxY=Math.max(maxY,point[1]);}
  for(const line of region.paths) for(const point of line) include(point);
  if(showWholeLayer) for(const line of region.outlines||[]) for(const point of line)include(point);
  if(showTravel) for(const motion of region.motions||[]) {include(motion);include(motion.slice(3));}
  if(!Number.isFinite(minX))return;
  if(showWholeLayer || $('preview-view')?.value==='3d') for(const path of visibleContextPaths()) for(const point of path.points) include(point);
  const span=Math.max(maxX-minX,maxY-minY,1),pad=span*.12;
  canvas.setAttribute('viewBox',`${minX-pad} ${minY-pad} ${maxX-minX+pad*2} ${maxY-minY+pad*2}`);
  for(const id of ['export-outlines','export-paths','preview-travels','preview-head','preview-context','preview-previous']) $(id)?.setAttribute('transform',`translate(0 ${minY+maxY}) scale(1 -1)`);
  for(const line of region.outlines||[]) makePolyline($('export-outlines'),line);
  for(const path of visibleContextPaths()) { const node=makePolyline($(path.previous?'preview-previous':'preview-context'),path.points);node.style.stroke=path.color; }
  const nodes=region.paths.map((line,i)=>{const node=makePolyline($('export-paths'),line);node.dataset.role=region.roles?.[i]||'support';if(region.roles)node.style.stroke=pathColors[node.dataset.role];return node;});
  const ends=[],pathEnds=region.paths.map(()=>0),travels=[];let duration=0;
  for(const [index,motion] of (region.motions||[]).entries()) {
    duration+=Math.max(0,motion[6]);ends.push(duration);
    if(motion[7]===1) pathEnds[motion[8]]=duration;
    if(showTravel&&motion[7]===0) travels.push({index,node:makePolyline($('preview-travels'),[motion.slice(0,3),motion.slice(3,6)])});
  }
  previewScene={region,nodes,ends,pathEnds,travels,duration,fullPoints:region.paths.map(line=>line.map(p=>projectPoint(p).join(',')).join(' ')),states:nodes.map(()=>null)};
  $('preview-nozzle')?.setAttribute('r',String(span*.009));
  playbackTime=Math.min(playbackTime,duration);playbackEnabled(duration>0);
  text('preview-caption',`Overhang ${region.id+1} · Layer ${region.layer} · Z ${region.z} mm · T${region.tool} · ${region.mode==='wave'?'Wave':'Arc'}`);
  renderPlayback(); renderRegionStats();
}
function clockText(seconds){const n=Math.max(0,Math.floor(seconds));return `${Math.floor(n/60)}:${String(n%60).padStart(2,'0')}`;}
function renderPlayback() {
  if(!activeRegion||!previewScene)return;
  const {ends,pathEnds,nodes,travels,duration,fullPoints,states}=previewScene,motions=previewScene.region.motions||[];
  let low=0,high=ends.length;
  while(low<high){const middle=(low+high)>>1;if(ends[middle]<=playbackTime)low=middle+1;else high=middle;}
  const index=Math.min(low,motions.length-1),motion=motions[index];
  const start=index>0?ends[index-1]:0,ratio=motion?Math.max(0,Math.min(1,(playbackTime-start)/Math.max(motion[6],1e-12))):0;
  const position=motion?motion.slice(0,3).map((value,axis)=>value+(motion[axis+3]-value)*ratio):null;
  let printed=0;
  nodes.forEach((node,path)=>{
    const complete=pathEnds[path]<=playbackTime;
    const partial=motion&&ratio>0&&motion[7]===1&&motion[8]===path&&!complete;
    const state=complete?'complete':partial?'active':'future';
    if(states[path]!==state){node.toggleAttribute('hidden',state==='future'||!pathVisible(node.dataset.role));node.classList.toggle('active',state==='active');if(complete)node.setAttribute('points',fullPoints[path]);states[path]=state;}
    if(complete)printed++;
    else if(partial)node.setAttribute('points',[...previewScene.region.paths[path].slice(0,motion[9]),position].map(p=>projectPoint(p).join(',')).join(' '));
  });
  for(const travel of travels){travel.node.toggleAttribute('hidden',travel.index>index);if(travel.index===index&&motion[7]===0)travel.node.setAttribute('points',[projectPoint(motion.slice(0,3)),projectPoint(position)].map(p=>p.join(',')).join(' '));else {const m=motions[travel.index];travel.node.setAttribute('points',[projectPoint(m.slice(0,3)),projectPoint(m.slice(3,6))].map(p=>p.join(',')).join(' '));}}
  const nozzle=$('preview-nozzle');if(nozzle&&position){nozzle.removeAttribute('hidden');const point=projectPoint(position);nozzle.setAttribute('cx',point[0]);nozzle.setAttribute('cy',point[1]);}
  if($('preview-progress'))$('preview-progress').value=String(duration?Math.round(playbackTime/duration*1000):1000);
  const state=playbackTime>=duration?'Complete':motion?.[7]===1?'Printing':motion?.[7]===0?'Travel':'Retract / wait';
  text('preview-progress-label',`${clockText(playbackTime)} / ${clockText(duration)} · ${printed}/${nodes.length} paths · ${state}${position?' · Z '+position[2].toFixed(2)+' mm':''}`);
}
function playbackTick(timestamp) {
  if(!previewScene){stopPlayback();return;}
  if(lastFrameTime!==null)playbackTime=Math.min(previewScene.duration,playbackTime+Math.max(0,timestamp-lastFrameTime)/1000*Number($('preview-speed')?.value||20));
  lastFrameTime=timestamp;renderPlayback();
  if(playbackTime>=previewScene.duration){stopPlayback();return;}
  playbackFrame=requestAnimationFrame(playbackTick);
}
function togglePlayback() {
  if(playbackFrame!==null){stopPlayback();return;}
  if(!previewScene||!previewScene.duration)return;
  if(playbackTime>=previewScene.duration)playbackTime=0;
  text('preview-play','Pause');$('preview-play').setAttribute('aria-label','Pause print animation');
  lastFrameTime=null;renderPlayback();playbackFrame=requestAnimationFrame(playbackTick);
}
function renderReport(report) {
  lastReport=report || null;
  const valid=report && !report.error;
  text('stat-regions',valid?report.replaced_features:'—');
  text('stat-paths',valid?report.generated_arcs:'—');
  text('stat-hilbert',valid?(report.hilbert_features||0):'—');
  text('last-report',!report?'Slice a model to generate the preview.':report.error?'Preview: '+report.error:`Preview: ${report.replaced_features} regions replaced, ${report.generated_arcs} support paths, ${report.skipped_features} skipped.${report.preview_error?' '+report.preview_error:''}`);
  const reasons=Object.entries(report?.skip_reasons||{}), details=$('report-details'),list=$('skip-list');
  if(details) details.hidden=!reasons.length;
  if(list) { list.replaceChildren(); for(const [reason,count] of reasons) { const item=document.createElement('li'); item.textContent=`${count} × ${reason}`; list.appendChild(item); } }
  populatePreviewChoices(); renderPreviewWarning(); renderSuggestions();
}
function remember() { draft=collect(); status.textContent='Unsaved changes.'; renderState(); }
function readonly() { return window.orca.getContext ? !!window.orca.getContext().readOnly : false; }
async function initialize(discard=false) {
  try {
    let saved=await settingsBridge.getConfig(); if(typeof saved==='string') saved=JSON.parse(saved);
    if(discard===true) draft=null;
    const values={...defaults,...(saved||{}),...(draft||{})};
    for(const key of fields) {
      const el=$(key); if(!el) continue;
      if(typeof defaults[key]==='boolean') el.checked=values[key]; else el.value=values[key];
      el.disabled=readonly(); el.removeAttribute?.('aria-invalid');
    }
    ready=true; renderState();
    status.textContent=readonly()?'This preset is read-only.':draft?'Unsaved changes.':'Settings loaded.';
  } catch(error) { status.textContent='Could not load settings: '+error.message; }
}
function invalid(key,message) {
  const el=$(key); el?.setAttribute?.('aria-invalid','true');
  if(el?.closest) {
    selectView('tuning');
    const overview=el.closest('#view-overview'); if(overview) selectView('overview');
    let parent=el.parentElement;
    while(parent) { if(parent.tagName==='DETAILS') parent.open=true; if(parent.dataset?.mode) parent.hidden=false; parent=parent.parentElement; }
    el.focus();
  }
  status.textContent=message;
}
$('save').onclick=async()=>{
  if(!ready) { status.textContent='Wait for settings to load.'; return; }
  if(readonly()) { status.textContent='This preset is read-only.'; return; }
  if(savingUI) return;
  const values=collect();
  for(const key of fields) {
    $(key)?.removeAttribute?.('aria-invalid');
    if(typeof values[key]==='number' && (!Number.isFinite(values[key]) || $(key)?.value==='')) { invalid(key,'Please enter a valid number for '+key+'.'); return; }
    if($(key)?.checkValidity && !$(key).checkValidity()) { invalid(key,$(key).validationMessage); return; }
  }
  if(values.minimum_arc_speed_mm_s>values.arc_speed_mm_s) { invalid('minimum_arc_speed_mm_s','Minimum speed must not exceed maximum arc speed.'); return; }
  if(values.z_min_mm>values.z_max_mm) { invalid('z_min_mm','Invalid Z range.'); return; }
  savingUI=true; $('save').disabled=true; status.textContent='Saving…';
  try {
    const result=await settingsBridge.saveConfig(values);
    if(result===false) status.textContent='Save failed.';
    else { draft=null; status.textContent=result?.preset_override_active?'Global defaults saved. The active preset overrides some values; edit them in Plugin Configuration.':'Saved.'; }
  } catch(error) {
    const key=fields.find(key=>error.message.startsWith(key+' '));
    if(key) invalid(key,'Save failed: '+error.message);
    else status.textContent='Save failed: '+error.message;
  }
  finally { savingUI=false; $('save').disabled=false; renderPreviewWarning(); }
};
function importProfile(text) {
  const marker={},explicit={},prefixed=new Set(),ignored=[];
  for(const line of text.split(/\r?\n/)) {
    if(line.includes('WAVE_OVERHANG_CONFIG')) for(const m of line.matchAll(/(\w+)=(\S+)/g)) marker[ALIASES[m[1]]||m[1]]=m[2];
    for(const m of line.matchAll(/wave_overhang_(\w+?)["']?\s*[:=]\s*["']?([^\s"',;]+)/g)) { explicit[m[1]]=m[2]; prefixed.add(m[1]); }
  }
  const found={...marker,...explicit},values={overhang_mode:'wave'};
  for(const [key,raw] of Object.entries(found)) {
    const spec=IMPORT[key];
    if(!spec) { if(prefixed.has(key)&&!['min_angle','spacing_mode','seam_mode','debug_gcode','outer_perimeters'].includes(key)) ignored.push('wave_overhang_'+key); continue; }
    const [target,kind]=spec,number=Number(raw);
    if(kind==='text') { if(['smart','zigzag','monotonic'].includes(raw.toLowerCase())) values[target]=raw.toLowerCase(); else ignored.push('wave_overhang_'+key); }
    else if(kind==='bool') { if(['0','1','true','false'].includes(raw.toLowerCase())) values[target]=['1','true'].includes(raw.toLowerCase()); else ignored.push('wave_overhang_'+key); }
    else if(!Number.isFinite(number)) ignored.push('wave_overhang_'+key);
    else if(kind==='fan') { values[target[0]]=number>=0; values[target[1]]=Math.max(0,number); }
    else values[target]=number;
  }
  return {values,ignored};
}
$('import').onclick=()=>{
  if(readonly()) { status.textContent='This preset is read-only.'; return; }
  const {values,ignored}=importProfile($('import_text').value||'');
  const count=Object.keys(values).length-1;
  if(!count) { status.textContent='No wave_overhang_ settings found in the pasted text.'; return; }
  for(const [key,value] of Object.entries(values)) { const el=$(key); if(!el) continue; if(typeof value==='boolean') el.checked=value; else el.value=value; }
  remember(); $('import_text').value='';
  status.textContent=`Imported ${count} settings; press Save to keep them.`+(ignored.length?' No equivalent for: '+ignored.join(', ')+'.':'');
};
$('refresh').onclick=()=>initialize(true);
$('settings').addEventListener('input',event=>{if(fields.includes(event.target.id)) remember();});
$('settings').addEventListener('change',event=>{if(fields.includes(event.target.id)) remember();});
for(const button of all('[data-view]')) button.onclick=()=>selectView(button.dataset.view);
if($('open-guide')) $('open-guide').onclick=()=>selectView('guide');
if($('open-tuning')) $('open-tuning').onclick=()=>selectView('tuning');
if($('preview-layer')) $('preview-layer').onchange=()=>fillRegionChoices($('preview-layer').value);
if($('preview-region')) $('preview-region').onchange=()=>loadPreviewRegion(Number($('preview-region').value));
if($('preview-layer-range')) $('preview-layer-range').oninput=()=>{$('preview-layer').value=previewLayerKeys[Number($('preview-layer-range').value)];fillRegionChoices($('preview-layer').value);};
if($('preview-prev')) $('preview-prev').onclick=()=>moveRegion(-1);
if($('preview-next')) $('preview-next').onclick=()=>moveRegion(1);
if($('preview-play')) $('preview-play').onclick=togglePlayback;
if($('preview-reset')) $('preview-reset').onclick=()=>{stopPlayback();playbackTime=0;renderPlayback();};
if($('preview-progress')) $('preview-progress').oninput=()=>{stopPlayback();playbackTime=Number($('preview-progress').value)/1000*(previewScene?.duration||0);renderPlayback();};
if($('preview-show-travel')) $('preview-show-travel').onchange=()=>renderSnapshot();
if($('preview-fit')) $('preview-fit').onclick=()=>{showWholeLayer=!showWholeLayer; $('preview-fit').setAttribute('aria-pressed',String(showWholeLayer)); $('preview-fit').textContent=showWholeLayer?'Fit support':'Show whole layer'; renderSnapshot();};
document.addEventListener('visibilitychange',()=>{stopPlayback();if(!document.hidden) initialize();});
initialize();

function renderSliceState(state) {
  const messages={waiting:'Slice a model to generate the preview.',slicing:'Slicing your model…',
    calculating:'Calculating Arc/Wave paths…',stale:'Model or settings changed. Slice again to update the preview.',
    cancelled:'Slicing stopped. Slice again to generate a preview.',failed:'Preview unavailable. Check the message below.',
    unavailable:'No preview is available for this slice. Slice the model again.',disabled:'Enable Arc Overhang and slice your model.'};
  text('preview-empty-title',state==='ready'?'No eligible overhangs':state==='calculating'?'Building your preview':state==='slicing'?'Slicing your model':'Slice preview');
  text('preview-empty-message',messages[state] || 'The current slice contains no eligible Arc/Wave regions. Check the region details below.');
  if(messages[state]) {
    text('preview-caption',messages[state]);
    text('last-report',lastReport?.error?'Preview: '+lastReport.error:messages[state]);
  } else if(state==='ready' && !(lastReport?.preview?.layers||[]).length) {
    text('preview-caption','No eligible Arc/Wave regions in this slice.');
  }
}
async function pollSlicePreview() {
  if(previewPollBusy || document.hidden || !settingsBridge.getPreview) return;
  previewPollBusy=true;
  try {
    const response=await settingsBridge.getPreview();
    if(response.changed) {
      previewRevision=response.revision;
      renderReport(response.last_report);
      renderSliceState(response.state);
    }
  } catch(error) { /* The configuration connection reports host failures separately. */ }
  finally { previewPollBusy=false; }
}
if(typeof setInterval==='function') setInterval(pollSlicePreview,1500);
