// Own local projection and explanatory drawings. No renderer or network dependencies.
const pathColors={support:'#208369',outer:'#d08735',inner:'#a79c3d',overhang:'#b75c75',bridge:'#627eb0',infill:'#89949c',solid:'#9b79b0',surface:'#659d9c',gap:'#b5907b',brim:'#72974b',other:'#81888e'};
const pathNames={support:'Arcs / Waves',outer:'Outer walls',inner:'Inner walls',overhang:'Overhang walls',bridge:'Bridges',infill:'Sparse infill',solid:'Solid infill',surface:'Surfaces',gap:'Gap fill',brim:'Brim / skirt',other:'Other'};
let cameraYaw=-.55,cameraPitch=.65;
const hiddenRoles=new Set();
function pathVisible(role){return !hiddenRoles.has(role||'support');}
function projectPoint(point){
  if(!point)return [NaN,NaN];
  const [x,y]=point,z=point[2]??activeRegion?.z??0;
  if($('preview-view')?.value!=='3d')return [x,y];
  return [x*Math.cos(cameraYaw)-y*Math.sin(cameraYaw),(x*Math.sin(cameraYaw)+y*Math.cos(cameraYaw))*Math.sin(cameraPitch)-z*Math.cos(cameraPitch)];
}
function layerContext(){return activeRegion?.context||lastReport?.preview?.contexts?.[String(activeRegion?.layer)];}
function displayRegion(){
  if(!activeRegion)return null;
  const context=layerContext();
  if($('preview-scope')?.value==='layer'&&context)return {...activeRegion,...context};
  return activeRegion;
}
function visibleContextPaths(){
  const context=layerContext();if(!context)return [];
  const result=[];
  if($('preview-context-toggle')?.checked&&$('preview-scope')?.value!=='layer'){
    context.paths.forEach((points,i)=>{const role=context.roles[i];if(role!=='support'&&pathVisible(role))result.push({points,color:pathColors[role]||pathColors.other});});
  }
  if($('preview-previous-toggle')?.checked)for(const points of context.previous||[])result.push({points,previous:true,color:'#87919a'});
  return result;
}
function renderRegionStats(){
  if($('preview-fit'))$('preview-fit').hidden=$('preview-scope')?.value==='layer';
  const r=activeRegion;if(!r)return;
  const coverage=r.coverage_percent==null?'':` · Minimum generated coverage ${Number(r.coverage_percent).toFixed(1)}%`;
  text('preview-area',`${r.path_count??r.paths.length} support paths${r.deposited_area_mm2==null?'':` · Deposited footprint ${r.deposited_area_mm2} mm²`}${coverage}`);
  text('preview-time',lastReport?.time_change_s==null?'':`Estimated print-time change: ${lastReport.time_change_s<0?'−':'+'}${clockText(Math.abs(lastReport.time_change_s))}`);
  text('preview-motion-note',($('preview-scope')?.value==='layer'&&layerContext()?'Full selected layer':'Selected overhang')+' · movement time estimate, without acceleration or heater waits.');
}
function renderSuggestions(){
  const table=$('region-results');if(table){table.replaceChildren();for(const result of lastReport?.region_results||[]){const row=document.createElement('tr');for(const value of [result.layer,result.status,result.reason||`${result.area_mm2} mm² · ${result.coverage_percent}% coverage`]){const cell=document.createElement('td');cell.textContent=value;row.appendChild(cell);}table.appendChild(row);}}
  if($('region-diagnostics'))$('region-diagnostics').hidden=!(lastReport?.region_results?.length);
  const select=$('suggestion-tool');if(!select)return;
  const previous=select.value;select.replaceChildren();
  for(const item of lastReport?.preview?.suggestions||[]){const option=document.createElement('option');option.value=String(item.tool);option.textContent=`T${item.tool} · ${item.material}`;select.appendChild(option);}
  if([...select.options].some(option=>option.value===previous))select.value=previous;
  showSuggestion();
}
function selectedSuggestion(){
  const item=(lastReport?.preview?.suggestions||[]).find(item=>String(item.tool)===$('suggestion-tool')?.value);
  const material=$('suggestion-material')?.value||'auto';
  if(!item)return null;
  if(material==='auto')return {...item,selectedMaterial:item.material,automatic:true};
  return item.materials?.[material]?{...item,values:item.materials[material],selectedMaterial:material,automatic:false}:null;
}
function showSuggestion(){
  const suggestion=selectedSuggestion();
  if($('apply-suggestion'))$('apply-suggestion').disabled=!suggestion||readonly();
  text('suggestion-note',suggestion?`${suggestion.selectedMaterial} starting points · ${suggestion.nozzle} mm nozzle · ${suggestion.layer_height} mm layer. Suggested ${suggestion.values.arc_speed_mm_s} mm/s, part-cooling fan ${suggestion.values.support_fan_percent}%, gap ${suggestion.values.peel_gap_mm} mm. ${suggestion.automatic?'Uses the sliced profile’s fan limit.':'Uses the selected material’s cooling, keeping nozzle and flow limits from the sliced profile.'} These are shared plugin settings; review every tool in a multi-material print.`:'Slice with generated support to read nozzle and flow limits.');
}
function renderParameterGuide(){
  const root=$('parameter-guide');if(!root)return;
  const overlap=Number($('wall_overlap_mm')?.value||0),spacing=Number($('arc_spacing_nozzle_ratio')?.value||.95);
  const gap=Number($('peel_gap_mm')?.value||.1),slow=Number($('upper_speed_percent')?.value||50);
  const cards=[
    ['Inner wall overlap',`Reach into inner walls: ${overlap} mm. The outer model boundary remains the limit.`, 'overlap'],
    ['Path spacing',`Arc spacing is ${spacing} × nozzle diameter. Smaller spacing means more paths.`, 'spacing'],
    ['Removable floor',`Vertical separation: ${gap} mm. A clear lower-layer insertion is required; otherwise this region is kept unchanged.`, 'gap'],
    ['Layers above support',`Inside the generated footprint: ${slow}% of the original feed. Outside: original feed.`, 'slow'],
    ['Print sequence',$('print_order')?.value==='slicer'?'Support follows the sliced Bridge position. Earlier Overhang walls follow support.':'Normal walls and infill → Arcs/Waves → Overhang walls, within each tool section.', 'order']
  ];
  root.replaceChildren();
  for(const [title,copy,kind] of cards){
    const card=document.createElement('article'),heading=document.createElement('h3'),note=document.createElement('p');heading.textContent=title;note.textContent=copy;
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 300 105');svg.setAttribute('role','img');svg.setAttribute('aria-label',title+' concept');
    function line(points,color,width=3){const path=document.createElementNS(svg.namespaceURI,'polyline');path.setAttribute('points',points);path.setAttribute('fill','none');path.setAttribute('stroke',color);path.setAttribute('stroke-width',width);svg.appendChild(path);}
    if(kind==='overlap'){for(let x=65;x<=125;x+=20)line(`${x},15 ${x},90`,'#89949c',5);for(let y=25;y<=85;y+=20)line(`${125-Math.min(100,overlap*45)},${y} 265,${y}`,'#208369');}
    if(kind==='spacing'){const step=Math.max(5,Math.min(25,spacing*18));for(let x=40;x<265;x+=step)line(`${x},90 ${x+18},60 ${x},20`,'#208369');}
    if(kind==='gap'){line('35,90 35,30 110,30','#89949c',10);line('110,30 270,30','#89949c',6);line(`95,${40+Math.min(35,gap*110)} 270,${40+Math.min(35,gap*110)}`,'#208369',5);}
    if(kind==='slow'){line('25,60 100,60','#89949c',4);line('100,60 220,60','#208369',4);line('220,60 280,60','#89949c',4);for(let x=110;x<220;x+=Math.max(5,slow/4))line(`${x},48 ${x},72`,'#208369',2);}
    if(kind==='order'){for(let i=0;i<3;i++){const x=35+i*95;line(`${x},30 ${x+45},30 ${x+45},80 ${x},80 ${x},30`,['#89949c','#208369','#b75c75'][i],3);if(i<2)line(`${x+52},55 ${x+85},55 ${x+77},47`,'#d08735',2);}}
    const button=document.createElement('button');button.type='button';button.className='text-button';button.textContent='Replay explanation';button.onclick=()=>{if(!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)svg.animate?.([{opacity:.15},{opacity:1}],{duration:650});};
    card.append(heading,svg,note,button);root.appendChild(card);
  }
}
if($('preview-filters'))for(const [role,name] of Object.entries(pathNames)){
  const label=document.createElement('label'),input=document.createElement('input'),swatch=document.createElement('i');input.type='checkbox';input.checked=true;input.dataset.role=role;input.setAttribute('aria-label',name);swatch.style.background=pathColors[role];label.append(input,swatch,document.createTextNode(name));$('preview-filters').appendChild(label);
  input.onchange=()=>{if(input.checked)hiddenRoles.delete(role);else hiddenRoles.add(role);renderSnapshot();};
}
for(const id of ['preview-view','preview-context-toggle','preview-previous-toggle'])if($(id))$(id).onchange=()=>renderSnapshot();
if($('preview-scope'))$('preview-scope').onchange=()=>{stopPlayback();playbackTime=displayRegion()?.duration||0;renderSnapshot();};
if($('preview-home'))$('preview-home').onclick=()=>{cameraYaw=-.55;cameraPitch=.65;renderSnapshot();};
if($('suggestion-tool'))$('suggestion-tool').onchange=showSuggestion;
if($('suggestion-material'))$('suggestion-material').onchange=showSuggestion;
if($('apply-suggestion'))$('apply-suggestion').onclick=()=>{
  if(readonly())return;
  const item=selectedSuggestion();if(!item)return;
  for(const [key,value] of Object.entries(item.values)){const el=$(key);if(!el)continue;if(typeof value==='boolean')el.checked=value;else el.value=value;}
  remember();status.textContent=settingsBridge.canSync===true?'Starting points selected. Applying to the active process…':'Starting points applied to draft. Review all tools and save before slicing.';
};
if($('export-drawing')){
  const svg=$('export-drawing');let drag=null;
  svg.setAttribute('tabindex','0');
  svg.addEventListener('keydown',event=>{
    if(!activeRegion||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','+','-'].includes(event.key))return;
    event.preventDefault();
    if(event.key==='Home'){cameraYaw=-.55;cameraPitch=.65;renderSnapshot();return;}
    const dx=event.key==='ArrowLeft'?-1:event.key==='ArrowRight'?1:0,dy=event.key==='ArrowUp'?-1:event.key==='ArrowDown'?1:0;
    if($('preview-view').value==='3d'&&(dx||dy)){cameraYaw+=dx*.1;cameraPitch=Math.max(.15,Math.min(1.5,cameraPitch+dy*.1));renderSnapshot();return;}
    const b=svg.getAttribute('viewBox').split(' ').map(Number),scale=event.key==='+'?.9:event.key==='-'?1.1:1;
    if(b[2]*scale<.1||b[2]*scale>100000)return;
    svg.setAttribute('viewBox',`${b[0]+b[2]*dx*.05+b[2]*(1-scale)/2} ${b[1]+b[3]*dy*.05+b[3]*(1-scale)/2} ${b[2]*scale} ${b[3]*scale}`);
  });
  svg.addEventListener('wheel',event=>{if(!activeRegion)return;event.preventDefault();const box=svg.getAttribute('viewBox').split(' ').map(Number),scale=event.deltaY>0?1.12:.89;if(box[2]*scale<.1||box[2]*scale>100000)return;svg.setAttribute('viewBox',`${box[0]+box[2]*(1-scale)/2} ${box[1]+box[3]*(1-scale)/2} ${box[2]*scale} ${box[3]*scale}`);},{passive:false});
  svg.addEventListener('pointerdown',event=>{if(!activeRegion)return;drag={x:event.clientX,y:event.clientY};svg.setPointerCapture(event.pointerId);});
  svg.addEventListener('pointermove',event=>{if(!drag)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;drag={x:event.clientX,y:event.clientY};if($('preview-view').value==='3d'&&!event.shiftKey){cameraYaw+=dx*.008;cameraPitch=Math.max(.15,Math.min(1.5,cameraPitch+dy*.008));renderSnapshot();}else{const b=svg.getAttribute('viewBox').split(' ').map(Number),matrix=svg.getScreenCTM();if(!matrix)return;const inverse=matrix.inverse();svg.setAttribute('viewBox',`${b[0]-dx*inverse.a-dy*inverse.c} ${b[1]-dx*inverse.b-dy*inverse.d} ${b[2]} ${b[3]}`);}});
  svg.addEventListener('pointerup',()=>drag=null);svg.addEventListener('pointercancel',()=>drag=null);
}
