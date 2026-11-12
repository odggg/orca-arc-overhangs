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
  const slicer=$('print_order')?.value==='slicer';
  const labels=slicer?['Slicer sequence','Bridge → support','Early overhang walls follow']:['Walls + infill',wave?'Waves':'Arcs','Overhang walls'];
  all('#sequence li').forEach((el,index)=>{el.textContent=labels[index];});
  text('sequence-note',slicer?'Normal walls and infill stay in their sliced positions. Early Overhang walls follow the support.':'The previous order is kept within each layer and tool section.');
  const note=$('floor-note'); if(note) note.hidden=!(wave && $('wave_floor_use_hilbert')?.checked);
  renderGuide(); renderPreviewWarning();
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
function renderSnapshot(index=0) {
  const layers=lastReport?.preview?.layers || [], layer=layers[index];
  const empty=$('preview-empty'), canvas=$('export-drawing');
  if(empty) empty.hidden=!!layer;
  if(!canvas) return;
  const paths=$('export-paths'), outlines=$('export-outlines');
  if(!paths || !outlines) return;
  paths.replaceChildren(); outlines.replaceChildren();
  if(!layer) { canvas.setAttribute('viewBox','0 0 480 340'); return; }
  const lines=showWholeLayer?[...(layer.outlines||[]),...(layer.paths||[])]:layer.paths||[];
  const points=lines.flat().filter(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite));
  if(!points.length) return;
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
  const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  const span=Math.max(maxX-minX,maxY-minY,1), pad=span*.12;
  canvas.setAttribute('viewBox',`${minX-pad} ${minY-pad} ${maxX-minX+pad*2} ${maxY-minY+pad*2}`);
  for(const [key,group] of [['outlines',outlines],['paths',paths]]) {
    group.setAttribute('transform',`translate(0 ${minY+maxY}) scale(1 -1)`);
    for(const line of layer[key]||[]) {
      if(!line.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite))) continue;
      const poly=document.createElementNS('http://www.w3.org/2000/svg','polyline');
      poly.setAttribute('points',line.map(p=>p.join(',')).join(' ')); group.appendChild(poly);
    }
  }
  text('preview-caption',`Layer ${layer.layer} · Z ${layer.z} mm · T${layer.tool} · ${layer.mode==='wave'?'Wave':'Arc'}${lastReport.preview.limited?' · limited preview':' · simplified 2D'}`);
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
  const select=$('preview-layer');
  if(select) {
    select.replaceChildren(); const layers=report?.preview?.layers||[];
    for(const [index,layer] of layers.entries()) { const option=document.createElement('option'); option.value=String(index); option.textContent=`Region ${index+1} · Layer ${layer.layer} · T${layer.tool}`; select.appendChild(option); }
    if(!layers.length) { const option=document.createElement('option'); option.textContent='No Arc regions'; select.appendChild(option); }
    select.disabled=!layers.length;
  }
  if($('preview-fit')) $('preview-fit').disabled=!(report?.preview?.layers||[]).length;
  renderSnapshot(); renderPreviewWarning();
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
if($('preview-layer')) $('preview-layer').onchange=()=>renderSnapshot(Number($('preview-layer').value));
if($('preview-fit')) $('preview-fit').onclick=()=>{showWholeLayer=!showWholeLayer; $('preview-fit').setAttribute('aria-pressed',String(showWholeLayer)); $('preview-fit').textContent=showWholeLayer?'Fit support':'Show whole layer'; renderSnapshot(Number($('preview-layer')?.value||0));};
document.addEventListener('visibilitychange',()=>{if(!document.hidden) initialize();});
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
