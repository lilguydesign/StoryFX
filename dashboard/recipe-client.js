// Store only opaque action identifiers and row references, never media or account contents.
export function createRecipeClient({ request, storage, owner, uuid = () => crypto.randomUUID() }) {
  const key = `storyfx.recipe-actions.v1.${owner}`;
  const read = () => {
    const value = JSON.parse(storage.getItem(key) || '{"draft":null,"launches":{},"pending":null}');
    if (!value || typeof value.launches !== 'object' || value.launches === null) throw Error('Journal de recette illisible.');
    return value;
  };
  const write = value => {
    storage.setItem(key, JSON.stringify(value));
    if (storage.getItem(key) !== JSON.stringify(value)) throw Error('La reprise fiable de cette demande ne peut pas être enregistrée.');
  };
  return {
    journal: read,
    async list() { return request('/v1/control/recipes'); },
    async detail(id) {
      const value = await request(`/v1/control/recipes/${encodeURIComponent(id)}`);
      return value.recipe || value;
    },
    async create(revision, rowIds) {
      const value = read();
      if (!value.draft) {
        if (!Number.isInteger(revision) || !rowIds.length || rowIds.length > 30 || new Set(rowIds).size !== rowIds.length)
          throw Error('Choisissez entre une et trente lignes distinctes.');
        value.draft = { client_key: uuid(), revision, row_ids: [...rowIds], executor: 'android' };
        value.draft_refused = null;
        write(value);
      }
      let result;
      try { result = await request('/v1/control/recipes', { method: 'POST', body: value.draft }); }
      catch (error) {
        if (['CONFIGURATION_CHANGED', 'ADAPTER_NOT_VALIDATED', 'PROFILE_NOT_FOUND'].includes(error.code)) {
          const latest = read(); latest.draft_refused = error.code; write(latest);
        }
        throw error;
      }
      this.reconcile([result.recipe || result]);
      return result.recipe || result;
    },
    recomposeDraft() {
      const value = read();
      if (!value.draft_refused || value.pending) throw Error('La création précédente reste à vérifier.');
      value.draft = null; value.draft_refused = null; write(value);
    },
    async command(id, action) {
      if (!['start', 'cancel', 'release'].includes(action)) throw Error('Commande de recette inconnue.');
      const result = await request(`/v1/control/recipes/${encodeURIComponent(id)}/${action}`, { method: 'POST', body: {} });
      return result.recipe || result;
    },
    async launch(recipeId, stepId) {
      const value = read(), target = `${recipeId}:${stepId}`;
      if (value.pending && value.pending !== target) throw Error('Une demande précédente reste à vérifier.');
      // A step has one immutable UUID: concurrent tabs cannot mint different attempts.
      value.launches[target] ||= stepId;
      value.pending = target;
      write(value);
      const result = await request(`/v1/control/recipes/${encodeURIComponent(recipeId)}/steps/${encodeURIComponent(stepId)}/launch`,
        { method: 'POST', body: { client_key: value.launches[target] } });
      if (result.recipe) this.reconcile([result.recipe]);
      return result;
    },
    reconcile(recipes) {
      const value = read();
      if (value.draft && recipes.some(recipe => recipe.client_key === value.draft.client_key)) {
        value.draft = null; value.draft_refused = null;
      }
      if (value.pending && recipes.some(recipe => recipe.steps?.some(step =>
        `${recipe.id}:${step.id}` === value.pending && (Boolean(step.job_id) || ['CANCELLED', 'RELEASED'].includes(recipe.state))))) value.pending = null;
      write(value);
    },
  };
}
