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
   window.__config={...defaults};window.__report=report;window.__saved=[];window.__readonly=false;
   let receive;
   window.orca={onMessage:cb=>{receive=cb;},getContext:()=>({readOnly:window.__readonly}),
    postMessage:request=>queueMicrotask(()=>{
     if(request.action==='save') { window.__config={...request.config};window.__saved.push({...request.config}); }
     receive({request_id:request.request_id,ok:true,config:window.__config,last_report:window.__report});
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
  console.log('Rendered UI: actual export, all settings preserved, modes/order, Hilbert conflict note, guide, light/dark, mobile, draft/reload, safe report text and read-only passed.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
