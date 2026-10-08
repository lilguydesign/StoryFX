import { request } from './api.js';
import { createRecipeClient } from './recipe-client.js';
import { canLaunch, eligibleRows, nextStep, recipeReasons } from './recipe-model.js';
import { publicationSummary, renderRecipeView } from './recipe-view.js';

let client = null, owner = null, epoch = 0, readSequence = 0, recipes = [], selectedId = '', selectedRows = [];
let snapshot = null, active = false, busy = false, error = '', pending = null, notice = () => {};
let redrawControl = () => {}, reloadControl = async () => {};
const find = selector => document.querySelector(selector);
const selectedRecipe = () => recipes.find(recipe => recipe.id === selectedId);
export const recipeHasLock = () => recipes.some(recipe => recipe.lock_held);
const message = failure => recipeReasons[failure.code] || failure.message || 'Recette indisponible.';

function draw() {
  if (!find('#manual-recipes')) return;
  let journal = {};
  try { if (client) journal = client.journal(); }
  catch { error = 'Le navigateur ne peut pas conserver la clé de reprise. Aucune publication n’est autorisée.'; }
  find('#manual-recipes').innerHTML = renderRecipeView({ snapshot: client ? snapshot : null, recipes, selectedId, selectedRows,
    active: active && Boolean(client), busy, error, journal });
  find('#recipe-confirm').disabled = !active || busy || Boolean(error) || !pending || (pending.action === 'start' && !find('#recipe-pause-ack').checked);
}

export function recipeSession(value) {
  if (owner === value) return;
  owner = value; epoch++; client = null; recipes = []; selectedId = ''; selectedRows = [];
  pending = null; error = ''; busy = false;
  find('#recipe-dialog')?.close();
  if (owner) {
    try { client = createRecipeClient({ request, storage: window.localStorage, owner }); }
    catch { error = 'Le stockage des clés de reprise est indisponible.'; }
  }
  draw();
}

export async function loadRecipes() {
  if (!client) return;
  const generation = epoch, sequence = ++readSequence, current = client;
  try {
    const result = await current.list();
    const values = result.recipes || [];
    const journal = current.journal();
    const chosen = journal.pending?.split(':')[0] || selectedId || result.active_recipe_id || values[0]?.id;
    if (chosen) {
      const detail = await current.detail(chosen);
      const index = values.findIndex(value => value.id === chosen);
      if (index >= 0) values[index] = detail; else values.unshift(detail);
    }
    if (generation !== epoch || sequence !== readSequence) return;
    current.reconcile(values);
    recipes = values; selectedId = chosen || ''; error = '';
  } catch (failure) {
    if (generation === epoch && sequence === readSequence) error = message(failure);
  }
  if (generation === epoch && sequence === readSequence) { draw(); redrawControl(); }
}

export function renderRecipes(value, enabled) { snapshot = value; active = Boolean(enabled); draw(); }

async function perform(work) {
  if (!active || !client || busy) return;
  const generation = epoch;
  busy = true; draw();
  try {
    await work(client);
    if (generation !== epoch) return;
    await reloadControl();
    notice('État de la recette actualisé. Aucune étape suivante n’est lancée automatiquement.');
  } catch (failure) {
    if (generation !== epoch) return;
    try { await reloadControl(); } catch (refreshError) { error = message(refreshError); }
    notice(`${message(failure)} Actualisez avant toute reprise ; la clé de cette demande est conservée.`, true);
  } finally {
    if (generation === epoch) { busy = false; draw(); }
  }
}

function review(action) {
  const recipe = selectedRecipe();
  if (!recipe) return;
  const step = nextStep(recipe);
  if (action === 'launch' && !canLaunch(recipe)) return;
  pending = { action, recipeId: recipe.id, stepId: step?.id };
  find('#recipe-pause-ack').checked = false;
  find('#recipe-pause-label').hidden = action !== 'start';
  const copy = {
    start: ['Démarrer la recette', 'Les nouveaux départs du serveur seront suspendus. Les tâches déjà en attente ou engagées finiront. Le démarrage de la recette ne publie rien.', 'Démarrer sans publier'],
    launch: ['Publier cette seule étape', 'Cette action publie réellement le lot ci-dessous sur Mon statut WhatsApp. Une réponse perdue sera reprise avec la même clé, sans nouvelle tentative. L’étape suivante restera manuelle.', 'Confirmer cette publication réelle'],
    cancel: ['Annuler la suite de la recette', 'Les publications déjà engagées et leurs résultats sont préservés. Aucune étape restante ne sera lancée. Si la recette a démarré, son verrou reste détenu jusqu’à la clôture. Annuler un brouillon ne modifie pas la programmation.', 'Annuler la suite'],
    release: ['Clôturer la recette', 'Pour une recette démarrée, le serveur exige la fin des tâches actives et laisse la programmation arrêtée. Clôturer un brouillon jamais démarré ne modifie pas la programmation. Aucun ancien lot n’est rejoué.', 'Confirmer la clôture'],
  }[action];
  if (!copy) return;
  find('#recipe-dialog-title').textContent = copy[0];
  find('#recipe-dialog-description').textContent = copy[1];
  find('#recipe-review').innerHTML = action === 'launch' ? publicationSummary(step.publication, step.expected_media_count) :
    `<p>${recipe.steps.length} étape(s) · moteur Android WhatsApp.</p>`;
  find('#recipe-confirm').textContent = copy[2];
  draw(); find('#recipe-dialog').showModal();
}

export function mountRecipes({ notify, redraw, reload }) {
  notice = notify; redrawControl = redraw; reloadControl = reload;
  find('#launch-controls').insertAdjacentHTML('beforebegin', '<section class="panel recipe-panel" id="manual-recipes" aria-label="Recette manuelle"></section>');
  document.body.insertAdjacentHTML('beforeend', `<dialog id="recipe-dialog" aria-labelledby="recipe-dialog-title"><form method="dialog" class="dialog-close"><button class="icon-button" aria-label="Fermer">×</button></form>
    <h2 id="recipe-dialog-title"></h2><p id="recipe-dialog-description"></p><div id="recipe-review" class="recipe-summary"></div>
    <label id="recipe-pause-label" class="recipe-choice"><input type="checkbox" id="recipe-pause-ack"><span>Je confirme avoir mis en pause le moteur externe Windows/USB pour cette recette. Cette déclaration ne constitue pas une vérification du serveur.</span></label>
    <button type="button" class="button primary full" id="recipe-confirm"></button></dialog>`);
  find('#recipe-dialog').addEventListener('close', () => { pending = null; });
  find('#recipe-pause-ack').addEventListener('change', draw);
  find('#manual-recipes').addEventListener('change', event => {
    if (!active || busy) return;
    if (event.target.matches('[data-recipe-row]')) {
      const checked = new Set([...find('#manual-recipes').querySelectorAll('[data-recipe-row]:checked')].map(input => input.dataset.recipeRow));
      selectedRows = eligibleRows(snapshot).filter(row => checked.has(row.id)).map(row => row.id);
      draw();
    }
    if (event.target.matches('[data-recipe-select]')) {
      selectedId = event.target.value;
      perform(async () => {});
    }
  });
  find('#manual-recipes').addEventListener('click', event => {
    const button = event.target.closest('[data-recipe-action]');
    if (!button || button.disabled || !active || busy) return;
    const action = button.dataset.recipeAction;
    if (action === 'refresh') { perform(async () => {}); return; }
    if (action === 'recompose') { perform(async api => { api.recomposeDraft(); selectedRows = []; }); return; }
    if (action === 'create') {
      const revision = snapshot?.revision, rows = [...selectedRows];
      perform(async api => {
        const result = await api.create(revision, rows);
        if (api === client) { selectedId = result.id; selectedRows = []; }
      });
      return;
    }
    review(action);
  });
  find('#recipe-confirm').addEventListener('click', () => {
    if (!pending || busy || !active || error) return;
    const command = { ...pending }, recipe = recipes.find(value => value.id === command.recipeId);
    if (command.action === 'start' && !find('#recipe-pause-ack').checked) return;
    if (command.action === 'launch' && (!canLaunch(recipe) || recipe.next_step_id !== command.stepId)) {
      find('#recipe-dialog').close(); notice('L’étape a changé. Actualisez la recette avant de confirmer.', true); return;
    }
    perform(async api => {
      if (command.action === 'launch') await api.launch(command.recipeId, command.stepId);
      else await api.command(command.recipeId, command.action);
      if (api === client) find('#recipe-dialog').close();
    });
  });
}
