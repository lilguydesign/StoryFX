export const recipeStates = {
  DRAFT: 'Brouillon · aucun envoi', DRAINING: 'Attente des tâches actives', READY: 'Prête pour une étape',
  IN_PROGRESS: 'Publication en cours', COOLDOWN: 'Intervalle entre les lots', BLOCKED: 'Vérification nécessaire',
  PASSED: 'Étapes validées par l’agent', CANCELLED: 'Recette annulée', RELEASED: 'Recette clôturée',
};
export const recipeReasons = {
  MANUAL_RECIPE_ACTIVE: 'Une recette détient déjà le verrou de publication.',
  RECIPE_DRAINING: 'Attendez le résultat des tâches encore actives. Aucun renvoi.',
  RECIPE_COOLDOWN: 'Le serveur impose au moins cinq minutes après une preuve complète.',
  RECIPE_BLOCKED: 'Le résultat exige une vérification. Aucune étape suivante automatique.',
  RECIPE_STEP_NOT_NEXT: 'Cette étape n’est plus la prochaine étape autorisée. Actualisez.',
  ANDROID_EXECUTOR_NOT_READY: 'L’agent Android doit être prêt, déverrouillé et correctement associé.',
  ANDROID_RECIPE_VERSION_REQUIRED: 'Installez la version Android 0.4.15 ou ultérieure avant la recette.',
  ADAPTER_NOT_VALIDATED: 'Adaptateur natif indisponible pour cette plateforme ou ce mode.',
  RECIPE_VALIDATION_REQUIRED: 'Une recette complète doit être validée avant la reprise de la programmation.',
  RECIPE_SCOPE_NOT_VALIDATED: 'Ce périmètre ou cette révision ne correspond pas aux lignes validées.',
};
export function expectedMedia(row) {
  if (!Number.isInteger(row?.count) || row.count < 1 || row.count > 30) return null;
  if (row.engine === 'intro') return 1;
  if (row.engine === 'multi') return row.count;
  if (row.engine === 'intro+multi' && row.count < 30) return row.count + 1;
  return null;
}
export function eligibleRow(row) {
  return row?.enabled !== false && row?.platform === 'WhatsApp' && !row.page && !row.page_name &&
    expectedMedia(row) !== null && Boolean(row.engine === 'intro' ? row.album : row.album2 || row.album) &&
    (row.engine !== 'intro+multi' || Boolean(row.album));
}
export function eligibleRows(snapshot) {
  const profiles = new Set((snapshot?.collections.profiles || []).filter(profile => profile.enabled !== false).map(profile => profile.name));
  return (snapshot?.collections.matrix || []).filter(row => eligibleRow(row) && profiles.has(row.device));
}
export function nextStep(recipe) {
  return recipe?.steps?.find(step => step.id === recipe.next_step_id);
}
export function canLaunch(recipe) {
  const step = nextStep(recipe);
  return recipe?.state === 'READY' && recipe.lock_held === true && !recipe.external_pending &&
    !recipe.block_reason && Boolean(step) && !step.job_id && !step.verified;
}
export function recipeDate(value) {
  const date = new Date(value);
  return value && Number.isFinite(date.valueOf()) ? new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'Africa/Douala', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).format(date) : '—';
}
