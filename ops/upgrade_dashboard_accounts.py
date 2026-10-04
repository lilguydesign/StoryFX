"""One-time source transformation, exact anchors only, without private data."""
from pathlib import Path


root = Path(__file__).resolve().parents[1] / 'dashboard'
app = (root / 'app.js').read_text(encoding='utf-8')
app = app.replace('request, setOwnerToken, clearOwnerToken, PilotError', 'request, PilotError')
for line in ('  find("#owner-key").hidden = state.authenticated;\n',
             '  find("#owner-key").required = !state.authenticated;\n',
             '  clearOwnerToken();\n', '  find("#owner-key").value = "";\n'):
    app = app.replace(line, '')
app = app.replace('"Prototype diagnostic"', '"Pilote privé · Internet"')
app = app.replace('  if (error instanceof PilotError && error.kind === "unauthorized") disconnect();',
                  '  if (error instanceof PilotError && error.kind === "unauthorized") { disconnect(); location.replace("/login/"); }')
start = app.index('find("#session-form").addEventListener("submit"')
end = app.index('find("#demo-button").addEventListener', start)
app = app[:start] + '''find("#session-form").addEventListener("submit", event => {
  event.preventDefault(); location.assign("/login/");
});
find("#logout-button").addEventListener("click", () => action(async () => {
  await request("/v1/auth/logout", { method: "POST", body: {} });
  disconnect(); location.replace("/login/");
}));
''' + app[end:]
start = app.index('  const result = await request("/v1/pairings"')
end = app.index('\n})));', start)
app = app[:start] + '''  find("#pair-code").textContent = "Compte FormaFX";
  find("#pair-expiry").textContent = "Dans StoryFX Android, choisissez Connecter mon compte, puis validez ce téléphone.";
  find("#pair-dialog").showModal();''' + app[end:]
app += '''
if (!state.demo) {
  state.busy = true;
  request("/v1/auth/session").then(async session => {
    find("#session-help").textContent = `Connecté avec ${session.user.email}. Accès propriétaire FormaFX actif.`;
    await refresh(); state.authenticated = true;
  }).catch(() => location.replace("/login/")).finally(() => { state.busy = false; render(); });
}
'''
(root / 'app.js').write_text(app, encoding='utf-8')
api = (root / 'api.js').read_text(encoding='utf-8')
start = api.index('let ownerToken = "";')
end = api.index('export class PilotError', start)
api = api[:start] + api[end:]
api = api.replace('  if (!ownerToken) throw new PilotError("unauthorized");\n', '')
api = api.replace('credentials: "omit"', 'credentials: "same-origin"')
api = api.replace('        Authorization: `Bearer ${ownerToken}`,\n', '')
(root / 'api.js').write_text(api, encoding='utf-8')
html = (root / 'index.html').read_text(encoding='utf-8')
html = html.replace('./favicon.svg', './assets/storyfx-icon.svg')
html = html.replace('StoryFX · prototype local', 'StoryFX · pilote privé 0.2.0')
html = html.replace('Prototype diagnostic', 'Pilote privé · Internet')
start = html.index('      <section class="session-panel"')
end = html.index('\n      <footer', start)
html = html[:start] + '''      <section class="session-panel" aria-labelledby="session-title"><div><h2 id="session-title">Votre compte FormaFX</h2><p id="session-help">Session sécurisée. Vos appareils sont rattachés à votre compte.</p></div><form id="session-form"><button class="button secondary" type="submit" id="login-button">Se connecter</button><button class="button secondary" type="button" id="logout-button" hidden>Déconnexion</button></form></section>''' + html[end:]
html = html.replace('Un code à usage limité associe l’appareil à votre espace.', 'Le compte FormaFX associe le téléphone à votre espace.')
html = html.replace('Votre code de connexion', 'Connecter votre téléphone')
html = html.replace('Saisissez ce code dans l’agent Android StoryFX. Il expire automatiquement.',
                    'Installez StoryFX Android, puis connectez-vous avec le même compte FormaFX. Aucune connexion USB ni Wi-Fi commun nécessaire.')
html = html.replace('L’agent Android doit être installé et ses permissions activées sur l’appareil.',
                    '<a href="https://api.formafx.com/functions/v1/storyfx-agent-download?platform=storyfx_agent_android&amp;channel=stable&amp;version=latest&amp;asset_type=apk">Télécharger la dernière version Android ↓</a>')
(root / 'index.html').write_text(html, encoding='utf-8')
