import { escape } from './views.js';
import { mediaSummary } from './media-plan.js';
import { canLaunch, eligibleRows, expectedMedia, recipeDate, recipeReasons, recipeStates } from './recipe-model.js';

export function publicationSummary(row, total = expectedMedia(row)) {
  return `<strong>${escape(row.name || row.system)}</strong><span>${escape(row.device)} · ${escape(row.platform)} · ${escape(row.engine)}</span>
    <span>${escape(mediaSummary(row))}</span><span>Destination : ${escape(row.page_name || row.page || 'Mon statut WhatsApp')} · <b>${escape(total)} média(s) au total</b></span>`;
}
const button = (action, label, enabled, kind = 'secondary') =>
  `<button type="button" class="button ${kind}" data-recipe-action="${action}" ${enabled ? '' : 'disabled'}>${label}</button>`;

export function renderRecipeView({ snapshot, recipes = [], selectedId, selectedRows = [], active, busy, error, journal = {} }) {
  const recipe = recipes.find(value => value.id === selectedId);
  const locked = recipes.some(value => value.lock_held);
  const enabled = active && !busy && !error;
  const rows = eligibleRows(snapshot);
  const selected = new Set(journal.draft?.row_ids || selectedRows);
  const options = recipes.map(value => `<option value="${escape(value.id)}" ${value.id === selectedId ? 'selected' : ''}>${escape(recipeDate(value.created_at))} · ${escape(recipeStates[value.state] || value.state)}</option>`).join('');
  return `<div class="terminal-heading"><h2>Recette manuelle · album par album</h2>${button('refresh', '↻ Actualiser', active && !busy)}</div>
    <p class="helper">WhatsApp Android 0.4.15 minimum. Chaque publication exige votre confirmation. Le serveur attend au moins cinq minutes après une preuve complète ; aucune étape ne démarre à la fin du délai.</p>
    <p class="recipe-warning">Facebook : adaptateur natif indisponible, y compris pour les deux pages configurées. Aucun basculement vers Windows.</p>
    ${error ? `<p class="recipe-warning" role="alert">${escape(error)} Les commandes sont suspendues ; actualisez pour vérifier leur résultat.</p>` : ''}
    ${journal.pending ? '<p class="recipe-warning" role="status">Une réponse de publication manque. La même demande est conservée. Aucune nouvelle tentative ne sera créée par une reprise.</p>' : ''}
    <details ${!recipe ? 'open' : ''}><summary>Préparer un nouveau brouillon · aucun envoi</summary>
      <p class="helper">Choisissez jusqu’à trente lignes. L’ordre affiché sera celui de la recette. Le nombre de médias et les albums sont conservés.</p>
      <div class="recipe-choices">${rows.map(row => `<label class="recipe-choice"><input type="checkbox" data-recipe-row="${escape(row.id)}" ${selected.has(row.id) ? 'checked' : ''} ${enabled && !locked && !journal.draft && !journal.pending && (selected.has(row.id) || selected.size < 30) ? '' : 'disabled'}><span class="recipe-summary">${publicationSummary(row)}</span></label>`).join('') || '<p>Aucune ligne WhatsApp Android éligible.</p>'}</div>
      ${journal.draft_refused ? '<p class="recipe-warning">La création a été explicitement refusée avant enregistrement. Vous pouvez recomposer le brouillon avec la configuration actualisée.</p>' : ''}
      ${button('create', journal.draft ? 'Reprendre la création du même brouillon' : 'Créer le brouillon sans envoi', enabled && !locked && !journal.pending && !journal.draft_refused && (journal.draft || selected.size > 0 && selected.size <= 30), 'primary')}
      ${journal.draft_refused ? button('recompose', 'Recomposer après refus confirmé', enabled && !locked && !journal.pending) : ''}
    </details>
    <label class="recipe-history">Recettes enregistrées<select data-recipe-select ${active && !busy && recipes.length ? '' : 'disabled'}><option value="">Choisir une recette</option>${options}</select></label>
    ${recipe ? renderRecipe(recipe, enabled, journal) : '<p class="helper">Créer un brouillon ne démarre ni la recette ni une publication.</p>'}`;
}

function renderRecipe(recipe, enabled, journal) {
  const steps = recipe.steps || [];
  const pendingStep = steps.find(step => `${recipe.id}:${step.id}` === journal.pending);
  const launchable = canLaunch(recipe) && (!journal.pending || Boolean(pendingStep && pendingStep.id === recipe.next_step_id));
  return `<div class="recipe-status" role="status"><span class="badge">${escape(recipeStates[recipe.state] || recipe.state)}</span>
    <span>${recipe.lock_held ? 'Verrou serveur détenu' : 'Verrou serveur libre'}</span></div>
    <p class="helper">Pause Windows/USB : déclaration humaine requise au démarrage, non vérifiable par ce serveur. ${recipe.external_pending ? 'Des tâches externes restent à terminer.' : ''}</p>
    ${recipe.block_reason ? `<p class="recipe-warning">${escape(recipeReasons[recipe.block_reason] || recipe.block_reason)}</p>` : ''}
    ${recipe.next_allowed_at ? `<p>Prochaine publication autorisable au plus tôt : <strong>${escape(recipeDate(recipe.next_allowed_at))}</strong> · Africa/Douala. Actualisez ensuite et confirmez l’étape.</p>` : ''}
    <ol class="recipe-steps">${steps.map(step => `<li ${step.id === recipe.next_step_id ? 'aria-current="step"' : ''}><div class="recipe-summary">${publicationSummary(step.publication, step.expected_media_count)}</div>
      <p><span class="badge">${escape(step.state)}</span> · ${step.verified ? 'Preuve complète du lot reçue de l’agent ; compte non vérifié' : step.job_id ? 'Tentative enregistrée ; consulter son résultat' : 'Aucune publication demandée'}${step.completed_at ? ` · ${escape(recipeDate(step.completed_at))}` : ''}</p></li>`).join('')}</ol>
    <p class="helper">Les lots qui ne sont jamais entièrement visibles dans une seule vue peuvent rester incertains. Une pagination seule ne prouve pas le lot ; aucun renvoi automatique.</p>
    <div class="scheduler-actions">${button('start', 'Démarrer la recette sans publier', enabled && recipe.state === 'DRAFT' && !journal.pending, 'primary')}
      ${button('launch', pendingStep ? 'Reprendre la même demande réelle…' : 'Publier une seule étape…', enabled && launchable, 'primary')}
      ${button('cancel', 'Annuler la suite…', enabled && !['CANCELLED', 'RELEASED'].includes(recipe.state), 'danger')}
      ${button('release', 'Clôturer et libérer…', enabled && ['PASSED', 'CANCELLED'].includes(recipe.state) &&
        (!recipe.lock_held || !recipe.external_pending && !steps.some(step => step.job_id && !step.completed_at)))}</div>
    <p class="helper">Annuler préserve toute publication déjà engagée. Clôturer une recette démarrée exige la fin des tâches actives et laisse la programmation automatique arrêtée. Un brouillon jamais démarré ne change pas la programmation. Sa reprise sera une action distincte limitée aux lignes validées et à leur révision.</p>`;
}
