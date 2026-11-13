// Local rendered-UI checks. Uses the project's own generated HTML and export fixture.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
const {chromium}=require('playwright');
(async()=>{
 const report=JSON.parse(fs.readFileSync('evidence/ui-report.json','utf8'));
 const html=fs.readFileSync('tab-preview.html','utf8');
 const defaults=JSON.parse(html.match(/const defaults = (.*);/)[1]);
 const executablePath=process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||(process.platform==='win32'?'C:/Program Files/Google/Chrome/Application/chrome.exe':undefined);
 const browser=await chromium.launch({headless:true,chromiumSandbox:true,...(executablePath?{executablePath}:{})});
 try {
  const page=await browser.newPage({viewport:{width:1400,height:1100},colorScheme:'light',reducedMotion:'reduce'});
  const errors=[],network=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(/^https?:/.test(r.url())) network.push(r.url());});
  await page.addInitScript(({defaults,report})=>{
   window.__config={...defaults};window.__report=report;window.__saved=[];window.__readonly=false;window.__revision=1;window.__state="ready";window.__catalogOnly=false;window.__regionRequests=[];window.__regionDelay=0;window.__canSync=undefined;window.__failSave=false;window.__context={process:'Test',printer:'Test',pipeline:'Arc Overhang'};
   let receive;
   window.orca={onMessage:cb=>{receive=cb;},getContext:()=>({readOnly:window.__readonly}),
    postMessage:request=>queueMicrotask(()=>{
     if(request.action==='save' && window.__failSave){receive({request_id:request.request_id,ok:false,error:'Host rejected settings'});return;}
     if(request.action==='save') { window.__config={...request.config};window.__saved.push({...request.config});if(window.__canSync){window.__report=null;window.__revision++;window.__state='stale';} }
     if(request.action==='region') {
       window.__regionRequests.push(request.config.id);
       const response={request_id:request.request_id,ok:true,revision:window.__revision,
         region:(()=>{const r=window.__report.preview.layers.find(region=>region.id===request.config.id);return {...r,context:window.__report.preview.contexts?.[String(r.layer)]};})()};
       setTimeout(()=>receive(response),request.config.id===0?window.__regionDelay:0);return;
     }
     const catalog=window.__catalogOnly&&window.__report?.preview?{...window.__report,preview:{...window.__report.preview,
       contexts:undefined,layers:window.__report.preview.layers.map(({paths,outlines,motions,...index})=>index)}}:window.__report;
     receive({request_id:request.request_id,ok:true,config:window.__config,last_report:catalog,
       revision:window.__revision,state:window.__state,config_context:window.__context,can_sync:window.__canSync,changed:request.config?.revision!==window.__revision});
    })};
  },{defaults,report});
  await page.goto(pathToFileURL(path.resolve('tab-preview.html')).href);
  await page.getByText('Settings loaded.',{exact:true}).waitFor();
  assert.equal(await page.locator('#preview-scope').inputValue(),'layer');
  assert((await page.locator('#export-paths polyline').count())>61);
  // All controls float inside the viewport; collapsing them changes no geometry.
  for(const id of ['preview-visibility','preview-timeline','preview-view-options']) {
    assert(await page.locator('#'+id).evaluate(el=>el.closest('.plot')!==null));
  }
  const beforeCollapse=await page.locator('#export-drawing').getAttribute('viewBox');
  await page.locator('#preview-visibility > summary').click();
  assert.equal(await page.locator('#preview-filters').isVisible(),false);
  await page.locator('#preview-visibility > summary').click();
  await page.locator('#preview-timeline > summary').click();
  assert.equal(await page.locator('#preview-progress').isVisible(),false);
  await page.locator('#preview-timeline > summary').click();
  assert.equal(await page.locator('#export-drawing').getAttribute('viewBox'),beforeCollapse);
  await page.locator('.plot').screenshot({path:'evidence/preview-overlays.png'});
  await page.locator('#preview-view-options > summary').click();
  await page.locator('#preview-scope').selectOption('region');
  assert.equal(await page.locator('#export-paths polyline').count(),61);
  assert.equal(await page.locator('#stat-paths').textContent(),'61');
  assert.equal(await page.locator('#preview-empty').isVisible(),false);
  assert.equal(await page.locator('#arc_speed_mm_s').isVisible(),true);
  assert.equal(await page.locator('#wave_speed_mm_s').isVisible(),false);
  assert.equal(await page.locator('#print_order').inputValue(),'layer_tail');
  const fit=await page.locator('#export-drawing').getAttribute('viewBox');
  await page.locator('#preview-fit').click();
  assert.notEqual(await page.locator('#export-drawing').getAttribute('viewBox'),fit);
  await page.locator('#preview-fit').click();
  assert.equal(await page.locator('#export-drawing').getAttribute('viewBox'),fit);
  // Drag follows screen pixels even with viewport padding and SVG aspect fitting.
  await page.locator('#export-drawing').scrollIntoViewIfNeeded();
  const svgBox=await page.locator('#export-drawing').boundingBox();
  const pathBeforePan=await page.locator('#export-paths polyline').first().boundingBox();
  await page.mouse.move(svgBox.x+svgBox.width*.65,svgBox.y+395);
  await page.mouse.down();await page.mouse.move(svgBox.x+svgBox.width*.65+30,svgBox.y+415);await page.mouse.up();
  const pathAfterPan=await page.locator('#export-paths polyline').first().boundingBox();
  assert(Math.abs(pathAfterPan.x-pathBeforePan.x-30)<1);
  assert(Math.abs(pathAfterPan.y-pathBeforePan.y-20)<1);
  await page.locator('#preview-home').click();
  assert((await page.locator('#preview-context polyline').count())>0);
  await page.locator('#preview-context-toggle').uncheck();assert.equal(await page.locator('#preview-context polyline').count(),0);await page.locator('#preview-context-toggle').check();
  await page.locator('#preview-previous-toggle').check();assert((await page.locator('#preview-previous polyline').count())>0);
  await page.locator('#preview-scope').selectOption('layer');
  const layerPaths=await page.locator('#export-paths polyline').count();assert(layerPaths>61);
  await page.locator('#refresh').click();await page.getByText('Settings loaded.',{exact:true}).waitFor();
  assert.equal(await page.locator('#preview-progress').inputValue(),'1000');
  const plan=await page.locator('#export-paths polyline').first().getAttribute('points');
  await page.locator('#preview-view').selectOption('3d');assert.notEqual(await page.locator('#export-paths polyline').first().getAttribute('points'),plan);
  const beforeOrbit=await page.locator('#export-paths polyline').first().getAttribute('points');
  await page.locator('#export-drawing').focus();await page.keyboard.press('ArrowRight');
  assert.notEqual(await page.locator('#export-paths polyline').first().getAttribute('points'),beforeOrbit);
  await page.keyboard.press('Home');
  await page.locator('#preview-filters input[data-role="outer"]').uncheck();assert.equal(await page.locator('#export-paths polyline[data-role="outer"]:not([hidden])').count(),0);
  await page.locator('#preview-filters input[data-role="outer"]').check();assert((await page.locator('#export-paths polyline[data-role="outer"]:not([hidden])').count())>0);
  await page.locator('#preview-reset').click();assert.equal(await page.locator('#export-paths polyline:not([hidden])').count(),0);
  await page.locator('#preview-progress').evaluate(el=>{el.value='500';el.dispatchEvent(new Event('input'));});
  await page.screenshot({path:'evidence/workbench-3d.png',fullPage:true});
  await page.locator('#preview-view').selectOption('2d');await page.locator('#preview-scope').selectOption('region');await page.locator('#preview-previous-toggle').uncheck();
  assert.equal(await page.locator('#export-paths polyline').count(),61);
  assert((await page.locator('#preview-area').textContent()).includes('mm²'));
  await page.locator('#apply-suggestion').click();assert((await page.locator('#status').textContent()).includes('draft'));
  await page.locator('#refresh').click();await page.getByText('Settings loaded.',{exact:true}).waitFor();
  assert.equal(await page.locator('#parameter-guide article').count(),5);
  await page.screenshot({path:'evidence/ui-overview.png',fullPage:true});
  await page.locator('#preview-reset').click();
  assert.equal(await page.locator('#export-paths polyline:not([hidden])').count(),0);
  assert.equal(await page.locator('#preview-progress').inputValue(),'0');
  await page.locator('#preview-progress').evaluate(el=>{el.value='350';el.dispatchEvent(new Event('input'));});
  const visiblePaths=await page.locator('#export-paths polyline:not([hidden])').count();
  assert(visiblePaths>0&&visiblePaths<61);
  assert((await page.locator('#export-paths polyline.active').count())<=1);
  await page.locator('#preview-show-travel').check();
  assert((await page.locator('#preview-travels polyline').count())>0);
  assert.equal(await page.locator('#preview-nozzle').getAttribute('hidden'),null);
  await page.locator('#preview-speed').selectOption('100');
  const progressBefore=Number(await page.locator('#preview-progress').inputValue());
  await page.locator('#preview-play').click();await page.waitForTimeout(300);
  await page.locator('#preview-play').click();
  const paused=await page.locator('#preview-progress').inputValue();
  assert(Number(paused)>progressBefore);
  await page.waitForTimeout(200);assert.equal(await page.locator('#preview-progress').inputValue(),paused);
  await page.screenshot({path:'evidence/ui-playback.png',fullPage:true});
  await page.locator('#preview-progress').evaluate(el=>{el.value='1000';el.dispatchEvent(new Event('input'));});
  assert.equal(await page.locator('#export-paths polyline:not([hidden])').count(),61);
  await page.locator('#preview-show-travel').uncheck();

  await page.locator('#enabled').uncheck();
  assert.equal(await page.locator('#processing-note').isVisible(),true);
  await page.locator('#enabled').check();
  await page.locator('#arc_speed_mm_s').fill('2.755');
  assert.equal(await page.locator('#preview-warning').isVisible(),true);
  await page.locator('#save').click();
  await page.getByText('Saved.',{exact:true}).waitFor();
  const saved=await page.evaluate(()=>window.__saved.at(-1));
  assert.equal(saved.arc_speed_mm_s,2.755);assert.equal(saved.wave_spacing_nozzle_ratio,0.875);
  assert.equal(Object.keys(saved).length,Object.keys(defaults).length);
  await page.locator('#overhang_mode').selectOption('wave');
  assert.equal(await page.locator('#arc_speed_mm_s').isVisible(),false);
  assert.equal(await page.locator('#wave_speed_mm_s').isVisible(),true);
  assert.equal(await page.locator('#wall_overlap_mm').isVisible(),true);
  await page.getByRole('button',{name:'How it works',exact:true}).click();
  assert.equal(await page.locator('#guide-heading').textContent(),'Wave fronts');
  assert((await page.locator('#guide-paths path').count())>=8);
  await page.screenshot({path:'evidence/ui-guide.png',fullPage:true});
  await page.getByRole('button',{name:'Fine tuning',exact:true}).click();
  const floor=page.locator('details').filter({has:page.getByText('Above the Waves',{exact:true})});
  await floor.locator('summary').click();await page.locator('#wave_floor_use_hilbert').check();
  await page.getByRole('button',{name:'Overview',exact:true}).click();
  assert.equal(await page.locator('#floor-note').isVisible(),true);
  await page.locator('#print_order').selectOption('slicer');
  await page.locator('#save').click();await page.getByText('Saved.',{exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>window.__saved.at(-1).print_order),'slicer');
  assert.equal(await page.evaluate(()=>window.__saved.at(-1).wave_floor_use_hilbert),true);
  await page.emulateMedia({colorScheme:'dark'});
  await page.screenshot({path:'evidence/ui-dark.png',fullPage:true});
  await page.emulateMedia({colorScheme:'light'});await page.setViewportSize({width:390,height:844});
  const overflow=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
  assert(overflow.scroll<=overflow.width+1,JSON.stringify(overflow));
  await page.screenshot({path:'evidence/ui-mobile.png',fullPage:true});
  // Explicit reload discards edits; a focus change preserves unsaved edits.
  await page.locator('#wave_speed_mm_s').fill('3');
  await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
  await page.waitForTimeout(100);assert.equal(await page.locator('#wave_speed_mm_s').inputValue(),'3');
  await page.locator('#refresh').click();await page.getByText('Settings loaded.',{exact:true}).waitFor();
  assert.equal(await page.locator('#wave_speed_mm_s').inputValue(),'2');
  // Slice events refresh only preview data; unsaved settings are preserved.
  await page.locator('#wave_speed_mm_s').fill('3.25');
  await page.evaluate(()=>{window.__revision++;window.__state='slicing';window.__report=null;});
  await page.getByText('Slicing your model…',{exact:true}).first().waitFor();
  assert.equal(await page.locator('#export-paths polyline').count(),0);
  assert.equal(await page.locator('#preview-area').textContent(),'');
  assert.equal(await page.locator('#preview-time').textContent(),'');
  assert.equal(await page.locator('#wave_speed_mm_s').inputValue(),'3.25');
  await page.evaluate(report=>{window.__revision++;window.__state='ready';window.__report=report;},report);
  await page.waitForFunction(()=>document.querySelectorAll('#export-paths polyline').length===61);
  assert.equal(await page.locator('#wave_speed_mm_s').inputValue(),'3.25');
  assert(!/export/i.test(await page.locator('body').innerText()),'No manual export step in the UI');
  // Twelve overhangs on four layers: only requested region geometry is transferred.
  await page.evaluate(report=>{
    const layers=Array.from({length:12},(_,id)=>{
      const region=structuredClone(report.preview.layers[0]);region.id=id;region.layer=2+Math.floor(id/3);
      region.z=Number((region.layer*.2).toFixed(2));region.tool=id%2;
      for(const m of region.motions){m[2]=region.z;m[5]=region.z;}
      return region;
    });
    window.__report={...report,preview:{...report.preview,layers}};window.__catalogOnly=true;
    window.__revision++;window.__state='ready';window.__regionRequests=[];
  },report);
  await page.waitForFunction(()=>document.querySelector('#preview-layer').options.length===4);
  await page.waitForFunction(()=>document.querySelector('#preview-region').options.length===3);
  await page.waitForFunction(()=>window.__regionRequests.length===1);
  await page.locator('#preview-layer').selectOption('5:1');
  await page.waitForFunction(()=>document.querySelector('#preview-caption').textContent.startsWith('Overhang 10'));
  await page.locator('#preview-region').selectOption('11');
  await page.waitForFunction(()=>document.querySelector('#preview-caption').textContent.startsWith('Overhang 12'));
  assert.equal(await page.locator('#preview-next').isDisabled(),true);
  assert((await page.locator('#preview-caption').textContent()).includes('T1'));
  await page.locator('#preview-prev').click();
  await page.waitForFunction(()=>document.querySelector('#preview-caption').textContent.startsWith('Overhang 11'));
  // A late response for a previously selected region cannot replace the current region.
  await page.evaluate(()=>{window.__regionDelay=300;});
  await page.locator('#preview-layer').selectOption('2:0.4');
  await page.locator('#preview-layer').selectOption('5:1');
  await page.waitForTimeout(450);
  assert((await page.locator('#preview-caption').textContent()).startsWith('Overhang 10'));
  await page.locator('#preview-progress').evaluate(el=>{el.value='999';el.dispatchEvent(new Event('input'));});
  await page.locator('#preview-speed').selectOption('100');await page.locator('#preview-play').click();
  await page.waitForFunction(()=>document.querySelector('#preview-play').textContent==='Play');
  assert.equal(await page.locator('#preview-progress').inputValue(),'1000');
  await page.locator('#preview-play').click();
  await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
  await page.waitForTimeout(100);assert.equal(await page.locator('#preview-play').textContent(),'Play');
  await page.locator('#preview-layer-range').evaluate(el=>{el.value='1';el.dispatchEvent(new Event('input'));});
  await page.waitForFunction(()=>document.querySelector('#preview-caption').textContent.startsWith('Overhang 4'));
  assert.equal(await page.locator('#preview-layer').inputValue(),'3:0.6');
  // New slicing clears geometry and stops the player.
  await page.locator('#preview-play').click();
  await page.evaluate(()=>{window.__revision++;window.__state='slicing';window.__report=null;});
  await page.waitForFunction(()=>document.querySelector('#preview-play').disabled);
  assert.equal(await page.locator('#export-paths polyline').count(),0);
  await page.evaluate(report=>{window.__catalogOnly=false;window.__state='ready';window.__report=report;window.__revision++;},report);
  await page.waitForFunction(()=>document.querySelectorAll('#export-paths polyline').length===61);
  // Process synchronization: automatic apply, sidebar polling and explicit re-slice guidance.
  await page.setViewportSize({width:1400,height:1100});
  await page.locator('#preview-view-options > summary').evaluate(el=>el.parentElement.open=false);
  await page.evaluate(report=>{window.__config={...report.preview.settings};window.__canSync=true;window.__state='ready';window.__report=report;window.__revision++;},report);
  await page.locator('#refresh').click();await page.getByText('Settings loaded.',{exact:true}).waitFor();
  await page.locator('#preview-scope').evaluate(el=>{el.value='layer';el.dispatchEvent(new Event('change'));});
  await page.waitForFunction(()=>document.querySelectorAll('#export-paths polyline').length>61);
  assert.equal(await page.locator('#preview-warning').isVisible(),false);
  await page.locator('.plot').screenshot({path:'evidence/preview-overlays.png'});
  const initialSaves=await page.evaluate(()=>window.__saved.length);
  await page.locator('#arc_speed_mm_s').fill('3.125');
  await page.waitForFunction(n=>window.__saved.length>n,initialSaves);
  assert.equal(await page.evaluate(()=>window.__config.arc_speed_mm_s),3.125);
  assert.equal(await page.locator('#export-paths polyline').count(),0);
  assert.equal(await page.locator('#preview-warning').isVisible(),true);
  assert((await page.locator('#preview-warning-message').textContent()).includes('Slice plate'));
  // Changes made in the sidebar appear without a reload, even if the slice revision is unchanged.
  await page.evaluate(()=>{window.__config.arc_speed_mm_s=4.25;});
  await page.waitForFunction(()=>document.querySelector('#arc_speed_mm_s').value==='4.25');
  // An input that is still invalid must not silently apply.
  const beforeInvalid=await page.evaluate(()=>window.__saved.length);
  await page.locator('#arc_speed_mm_s').fill('0');await page.waitForTimeout(850);
  assert.equal(await page.evaluate(()=>window.__saved.length),beforeInvalid);
  await page.evaluate(()=>{window.__failSave=true;});
  await page.locator('#arc_speed_mm_s').fill('3.5');
  await page.getByText('Save failed: Host rejected settings',{exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>window.__config.arc_speed_mm_s),4.25);
  await page.evaluate(()=>{window.__failSave=false;window.__canSync=undefined;});
  await page.locator('#refresh').click();await page.getByText('Settings loaded.',{exact:true}).waitFor();
  // Never apply a pending draft over a concurrent sidebar edit.
  await page.evaluate(async()=>{
    window.__canSync=true;await initialize(true);
    const input=document.querySelector('#arc_speed_mm_s');input.value='5';input.dispatchEvent(new Event('input',{bubbles:true}));
    window.__config.arc_speed_mm_s=6;await pollSlicePreview();
  });
  const conflictSaves=await page.evaluate(()=>window.__saved.length);
  await page.waitForTimeout(850);
  assert.equal(await page.evaluate(()=>window.__saved.length),conflictSaves);
  assert((await page.locator('#preview-warning-message').textContent()).includes('Reload settings'));
  await page.evaluate(()=>{window.__canSync=undefined;});
  await page.locator('#refresh').click();await page.getByText('Settings loaded.',{exact:true}).waitFor();
  // Restore a completed layer to inspect the compact, translucent overlays in both themes.
  await page.evaluate(report=>{window.__config={...report.preview.settings};window.__state='ready';window.__report=report;window.__revision++;},report);
  await page.locator('#refresh').click();await page.getByText('Settings loaded.',{exact:true}).waitFor();
  await page.emulateMedia({colorScheme:'dark'});
  await page.locator('.plot').screenshot({path:'evidence/preview-overlays-dark.png'});
  await page.emulateMedia({colorScheme:'light'});await page.setViewportSize({width:390,height:844});
  await page.locator('#preview-visibility > summary').evaluate(el=>el.parentElement.open=false);
  await page.locator('.plot').scrollIntoViewIfNeeded();
  await page.locator('.plot').screenshot({path:'evidence/preview-overlays-mobile.png'});
  for(const id of ['preview-timeline','preview-visibility','preview-view-options']){
    const contained=await page.locator('#'+id).evaluate(el=>{const a=el.getBoundingClientRect(),b=el.closest('.plot').getBoundingClientRect();return a.left>=b.left&&a.right<=b.right&&a.top>=b.top&&a.bottom<=b.bottom;});
    assert(contained,id+' stays inside the viewport');
  }
  // Host data is text, never HTML.
  await page.evaluate(()=>{window.__report={error:'<img src=x onerror="window.__xss=true">'};});
  await page.locator('#refresh').click();await page.waitForTimeout(100);
  assert((await page.locator('#last-report').textContent()).includes('<img'));
  assert.equal(await page.locator('#last-report img').count(),0);
  assert.equal(await page.evaluate(()=>window.__xss),undefined);
  await page.evaluate(()=>{window.__readonly=true;});await page.locator('#refresh').click();
  await page.getByText('This preset is read-only.',{exact:true}).waitFor();
  assert.equal(await page.locator('#arc_speed_mm_s').isDisabled(),true);
  assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
  console.log('Rendered UI: viewport overlays, full-layer default, automatic process apply, sidebar sync, conflict and failure handling, layer/region playback, light/dark/mobile, accessibility and existing UI regressions passed.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
