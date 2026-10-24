export async function offerPasswordHelp(api, email, selectMode) {
  let action;
  try { ({ action } = await api('/v1/auth/password-help', { email })); }
  catch { return false; }
  if (!['create', 'create_verified', 'reset', 'verify'].includes(action)) return false;
  const create = action.startsWith('create');
  const dialog = document.createElement('dialog');
  dialog.className = 'password-help-dialog';
  dialog.setAttribute('aria-labelledby', 'password-help-title');
  const title = document.createElement('h2'); title.id = 'password-help-title';
  title.textContent = create ? 'Créer mon mot de passe' : action === 'reset'
    ? 'Mot de passe oublié ?' : 'Créer ou réinitialiser mon mot de passe';
  const text = document.createElement('p');
  text.textContent = create
    ? 'Vous n’avez pas encore de mot de passe FormaFX. Celui de votre ancienne plateforme ne permet pas de vous connecter ici. Cliquez sur OK pour définir votre mot de passe après vérification de votre e-mail.'
    : action === 'reset' ? 'Le mot de passe saisi est incorrect. L’avez-vous oublié ? Cliquez sur OK pour le réinitialiser.'
      : 'Après vérification de votre e-mail, vous pourrez définir votre mot de passe FormaFX si vous n’en avez pas encore, ou le réinitialiser si vous l’avez oublié.';
  const buttons = document.createElement('div'); buttons.className = 'password-help-actions';
  for (const [label, value] of [['Annuler', 'cancel'], ['OK', 'ok']]) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = label;
    button.addEventListener('click', () => dialog.close(value)); buttons.append(button);
  }
  dialog.append(title, text, buttons); document.body.append(dialog);
  const accepted = await new Promise(resolve => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'ok'), { once: true }); dialog.showModal();
  });
  dialog.remove();
  if (accepted && action === 'create') {
    const result = await api('/v1/auth/sso/start', {});
    const target = new URL(result.redirect_to);
    if (target.origin !== 'https://auth.formafx.com' || target.pathname !== '/sso/start') throw new Error('Destination de connexion invalide.');
    target.hash = new URLSearchParams({auth_action:'password_help',login_hint:email.trim().toLowerCase()}).toString();
    location.assign(target.href);
  } else if (accepted) selectMode(create ? 'create' : 'reset');
  return accepted;
}
