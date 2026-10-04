const $ = selector => document.querySelector(selector);
let mode = 'password', busy = false, requested = false, recovery = false;
let requestId = new URLSearchParams(location.search).get('request_id');
if (requestId && /^[A-Za-z0-9_-]{43}$/.test(requestId)) sessionStorage.setItem('storyfx_agent_request', requestId);
else requestId = sessionStorage.getItem('storyfx_agent_request');
history.replaceState(null, '', location.pathname);
const messages = {OWNER_ACCESS_REQUIRED:'StoryFX est réservé aux propriétaires FormaFX actifs.',AUTH_REFUSED:'Les identifiants ou le code ne sont pas valides.',RATE_LIMITED:'Patientez une minute avant de réessayer.',PASSWORD_CONFIRMATION_MISMATCH:'Les deux mots de passe doivent être identiques.',AGENT_REQUEST_INVALID:'La demande de connexion a expiré. Recommencez depuis le téléphone.'};
function notice(message, error=false){$('#notice').textContent=message;$('#notice').hidden=!message;$('#notice').classList.toggle('error',error);}
async function api(path, body, method='POST'){
  const response=await fetch(path,{method,credentials:'same-origin',cache:'no-store',referrerPolicy:'no-referrer',headers:body===undefined?{}:{'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const data=await response.json();
  if(!response.ok)throw new Error(messages[data.error]||'La demande a été refusée ou le service est indisponible.');
  return data;
}
async function action(work){if(busy)return;busy=true;document.querySelectorAll('button').forEach(button=>button.disabled=true);notice('');try{await work();}catch(error){notice(error.message,true);}finally{busy=false;document.querySelectorAll('button').forEach(button=>button.disabled=false);}}
function selectMode(next){mode=next;recovery=next==='reset';requested=false;$('#password-fields').hidden=next!=='password';$('#otp-fields').hidden=next==='password';$('#password').required=next==='password';$('#otp').required=false;$('#back').hidden=!recovery;$('#login-title').textContent=recovery?'Réinitialiser le mot de passe':'Bienvenue dans StoryFX';$('#login-subtitle').textContent=recovery?'Vérifiez votre adresse par un code OTP, puis définissez votre nouveau mot de passe FormaFX.':'Retrouvez votre compte FormaFX. L’accès est réservé aux propriétaires actifs.';$('#submit').textContent=next==='password'?'Se connecter →':'Recevoir un code →';document.querySelectorAll('[data-mode]').forEach(button=>{button.classList.toggle('active',button.dataset.mode===next);button.setAttribute('aria-pressed',String(button.dataset.mode===next));});notice('');}
async function sendCode(){await api('/v1/auth/otp/request',{email:$('#email').value});requested=true;$('#otp').required=true;$('#submit').textContent='Vérifier le code →';notice('Si votre adresse est autorisée dans FormaFX, un code a été envoyé.');$('#otp').focus();}
async function connected(){
  if(requestId){
    const details=await api('/v1/auth/agent/request?request_id='+encodeURIComponent(requestId),undefined,'GET');
    $('#login-content').hidden=true;$('#new-password-form').hidden=true;$('#agent-consent').hidden=false;
    $('#login-title').textContent='Votre téléphone, votre compte';
    $('#device-description').textContent=`${details.name} · Android ${details.android_version}`;
  }else location.replace('/dashboard/');
}
$('#login-form').addEventListener('submit',event=>{event.preventDefault();action(async()=>{
  if(mode==='password'){const password=$('#password').value;$('#password').value='';await api('/v1/auth/login',{email:$('#email').value,password});await connected();}
  else if(!requested)await sendCode();
  else{const code=$('#otp').value;$('#otp').value='';await api('/v1/auth/otp/verify',{email:$('#email').value,code});if(recovery){$('#login-content').hidden=true;$('#new-password-form').hidden=false;notice('Adresse vérifiée. Choisissez votre nouveau mot de passe.');}else await connected();}
});});
$('#new-password-form').addEventListener('submit',event=>{event.preventDefault();action(async()=>{
  const password=$('#new-password').value,confirmation=$('#confirmation').value;$('#new-password').value='';$('#confirmation').value='';
  await api('/v1/auth/password',{password,confirmation},'PUT');await connected();
});});
$('#resend').addEventListener('click',()=>action(sendCode));
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>selectMode(button.dataset.mode)));
$('#reset').addEventListener('click',()=>selectMode('reset'));$('#back').addEventListener('click',()=>selectMode('password'));
$('#show-password').addEventListener('click',()=>{const show=$('#password').type==='password';$('#password').type=show?'text':'password';$('#show-password').setAttribute('aria-label',show?'Masquer le mot de passe':'Afficher le mot de passe');});
$('#sso').addEventListener('click',()=>action(async()=>{const result=await api('/v1/auth/sso/start',{});const target=new URL(result.redirect_to);if(target.origin!=='https://auth.formafx.com'||target.pathname!=='/sso/start')throw new Error('Destination de connexion invalide.');location.assign(target.href);}));
$('#authorize').addEventListener('click',()=>action(async()=>{const result=await api('/v1/auth/agent/authorize',{request_id:requestId});const target=new URL(result.redirect_to);if(target.protocol!=='storyfx-android:'||target.hostname!=='auth'||target.pathname!=='/callback')throw new Error('Retour vers le téléphone invalide.');sessionStorage.removeItem('storyfx_agent_request');location.assign(target.href);notice('Association autorisée. Revenez dans StoryFX sur votre téléphone.');}));
$('#cancel-connect').addEventListener('click',()=>{sessionStorage.removeItem('storyfx_agent_request');requestId=null;location.replace('/dashboard/');});
$('#theme').addEventListener('click',()=>{const light=document.documentElement.dataset.theme!=='light';document.documentElement.dataset.theme=light?'light':'dark';$('#theme').textContent=light?'☾':'☼';$('#theme').setAttribute('aria-label',`Activer le thème ${light?'sombre':'clair'}`);});
api('/v1/auth/session',undefined,'GET').then(connected).catch(()=>{});
