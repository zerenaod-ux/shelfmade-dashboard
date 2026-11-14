const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
(async()=>{
 const root=path.resolve('docs/app'),calls=[];let deny=false;
 const server=http.createServer((req,res)=>{let file=path.join(root,req.url.split('?')[0].replace(/^\//,'')||'index.html');if(!file.startsWith(root)){res.writeHead(403);return res.end()}try{const body=fs.readFileSync(file);res.setHeader('Content-Type',file.endsWith('.html')?'text/html':file.endsWith('.js')?'text/javascript':'application/octet-stream');res.end(body)}catch{res.writeHead(404);res.end()}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch(process.env.CHROME_CHANNEL?{channel:process.env.CHROME_CHANNEL}:{});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}});
  await page.addInitScript(()=>localStorage.setItem('ghtok','mock-test-token'));
  page.on('dialog',d=>d.accept());
  await page.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());if(u.hostname==='127.0.0.1')return route.continue();
   const p=u.pathname;let data={};
   if(req.method()!=='GET'){
    calls.push({url:req.url(),method:req.method(),body:req.postData()});
    if(req.method()==='POST'&&deny)return route.fulfill({status:403,body:'{}'});
    return route.fulfill({status:req.method()==='DELETE'?204:200,body:req.method()==='DELETE'?'':'[]'});
   }
   const video='https://cdn.jsdelivr.net/gh/zerenaod-ux/content-engine@gh-pages/videos/ce-20261113-2105.mp4';
   if(p.endsWith('/issues'))data=p.includes('/content-engine/')?[{number:6,title:'Content Engine: Example video',body:'Watch: '+video,labels:[]}]:[{number:100,title:'Review SHORT Other channel',body:'',labels:[]}];
   if(p.includes('/contents/data/scenes/review/index.json'))data={items:[{folder:'saved',title:'Approved example',video},{folder:'delete',title:'Skipped example',video}]};
   return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
  });
  const url='http://127.0.0.1:'+server.address().port+'/index.html#review';
  async function fresh(){calls.length=0;await page.goto(url.replace('/index.html#','/index.html?case='+Date.now()+'#'));await page.locator('#r-scenes .rv .btns').waitFor()}
  await fresh();
  const buttons=page.locator('#r-scenes .rv .btns button');
  assert.deepEqual(await buttons.allTextContents(),['Approve','Skip']);
  assert.equal(await buttons.nth(0).getAttribute('class'),await page.locator('#r-list .rv .btns button').nth(0).getAttribute('class'));
  await buttons.nth(0).click();assert.equal(calls.filter(x=>x.method==='POST').length,0);
  await buttons.nth(0).click();await page.locator('#r-scenes .done').waitFor();
  assert.deepEqual(JSON.parse(calls.find(x=>x.method==='POST').body).labels,['ce-approve']);
  assert(calls.every(x=>x.url.includes('/content-engine/')));assert(!calls.some(x=>x.method==='PATCH'));
  await fresh();await buttons.nth(1).click();await buttons.nth(1).click();await page.locator('#r-scenes .done').waitFor();
  assert.deepEqual(JSON.parse(calls.find(x=>x.method==='POST').body).labels,['ce-skip']);
  await page.locator('#r-scenes').getByRole('button',{name:'Saved',exact:true}).click();await page.getByText('Approved example',{exact:true}).waitFor();
  assert.equal(await page.getByText('Skipped example',{exact:true}).count(),0);
  await page.locator('#r-scenes').getByRole('button',{name:'Delete',exact:true}).click();await page.getByText('Skipped example',{exact:true}).waitFor();
  assert.equal(await page.getByText('Approved example',{exact:true}).count(),0);
  deny=true;await fresh();await buttons.nth(0).click();await buttons.nth(0).click();
  await page.waitForFunction(()=>{const b=document.querySelector('#r-scenes .rv .btns button');return b&&!b.disabled&&b.textContent==='Approve'});
  assert.equal(await page.locator('#r-scenes .done').count(),0);
  await page.screenshot({path:'content-engine-review-preview.png',fullPage:true});
  console.log('PASS: matching layout, confirmation, approve, skip, folder separation, API failure recovery; other channels untouched.');
 }finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
