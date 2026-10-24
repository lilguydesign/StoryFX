const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=process.env.STORYFX_SOURCE_ROOT||path.resolve(__dirname,'../..');
let action='create_verified',error='PASSWORD_CREDENTIALS_INVALID',reads=0,sends=0;
const server=http.createServer((req,res)=>{
 const name=new URL(req.url,'http://localhost').pathname;
 if(name.startsWith('/v1/')){
  res.setHeader('Content-Type','application/json');req.resume();req.on('end',()=>{
   if(name==='/v1/auth/session'){res.statusCode=401;res.end('{}');return;}
   if(name==='/v1/auth/login'){res.statusCode=401;res.end(JSON.stringify({error}));return;}
   if(name==='/v1/auth/password-help'){reads++;res.end(JSON.stringify({action}));return;}
   sends++;res.statusCode=404;res.end('{}');
  });return;
 }
 const file=path.join(root,'dashboard',name.startsWith('/login/')?name:name.replace('/dashboard/','/'));
 const target=fs.existsSync(file)&&fs.statSync(file).isDirectory()?path.join(file,'index.html'):file;
 if(!target.startsWith(root)||!fs.existsSync(target)){res.writeHead(404);res.end();return;}
 res.setHeader('Content-Type',({'.html':'text/html','.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.ttf':'font/ttf','.otf':'font/otf'})[path.extname(target)]||'application/octet-stream');fs.createReadStream(target).pipe(res);
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({executablePath:'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',headless:true});
 try{
  const page=await browser.newPage();await page.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort());
  async function login(){await page.goto(origin+'/login/');await page.locator('#email').fill('validation@example.invalid');await page.locator('#password').fill('old-platform-password');await page.locator('#submit').click();}
  for(const [next,title]of [['create_verified','Créer mon mot de passe'],['reset','Mot de passe oublié ?'],['verify','Créer ou réinitialiser mon mot de passe']]){
   action=next;await login();const dialog=page.getByRole('dialog');await dialog.waitFor();assert.equal(await dialog.locator('h2').textContent(),title);assert.equal(sends,0);
   assert.equal(await dialog.locator('h2').evaluate(e=>getComputedStyle(e).fontFamily),'LemonMilk, sans-serif');
   await dialog.getByRole('button',{name:'OK',exact:true}).click();assert.equal(await page.locator('#login-title').textContent(),next==='create_verified'?'Créer mon mot de passe':'Réinitialiser le mot de passe');assert.equal(await page.locator('#email').inputValue(),'validation@example.invalid');assert.equal(sends,0);
  }
  action=null;await login();await page.locator('#notice').waitFor();assert.equal(await page.getByRole('dialog').count(),0);
  for(const next of ['RATE_LIMITED','OWNER_ACCESS_REQUIRED','AUTH_REFUSED']){error=next;const prior=reads;await login();await page.locator('#notice').waitFor();assert.equal(reads,prior);assert.equal(await page.getByRole('dialog').count(),0);}
  console.log(JSON.stringify({passed:true,scenarios:7,real_sends:sends,real_edge:true}));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
