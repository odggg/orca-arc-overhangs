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
   window.__config={...defaults};window.__report=report;window.__saved=[];window.__readonly=false;window.__revision=1;window.__state="ready";window.__catalogOnly=false;window.__regionRequests=[];window.__regionDelay=0;
   let receive;
   window.orca={onMessage:cb=>{receive=cb;},getContext:()=>({readOnly:window.__readonly}),
    postMessage:request=>queueMicrotask(()=>{
     if(request.action==='save') { window.__config={...request.config};window.__saved.push({...request.config}); }
     if(request.action==='region') {
       window.__regionRequests.push(request.config.id);
       const response={request_id:request.request_id,ok:true,revision:window.__revision,
         region:window.__report.preview.layers.find(region=>region.id===request.config.id)};
       setTimeout(()=>receive(response),request.config.id===0?window.__regionDelay:0);return;
     }
     const catalog=window.__catalogOnly&&window.__report?.preview?{...window.__report,preview:{...window.__report.preview,
       layers:window.__report.preview.layers.map(({paths,outlines,motions,...index})=>index)}}:window.__report;
     receive({request_id:request.request_id,ok:true,config:window.__config,last_report:catalog,
       revision:window.__revision,state:window.__state,changed:request.config?.revision!==window.__revision});
    })};
  },{defaults,report});
  await page.goto(pathToFileURL(path.resolve('tab-preview.html')).href);
  await page.getByText('Settings loaded.',{exact:true}).waitFor();
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
  console.log('Rendered UI: layer/region navigation, timed playback, lazy loading and stale-response protection, all settings preserved, modes/order, Hilbert conflict note, guide, light/dark, mobile, draft/reload, safe report text and read-only passed.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
