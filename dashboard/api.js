const messages = {
  unauthorized: "La session propriétaire est invalide ou a expiré. Reconnectez-vous.",
  forbidden: "Cette action n’est pas disponible pour cette session.",
  conflict: "L’état a changé. Actualisez l’espace avant de réessayer.",
  unavailable: "Le serveur du pilote est indisponible. Réessayez dans quelques instants.",
  invalid: "La demande n’a pas été acceptée. Vérifiez les champs renseignés.",
};
export class PilotError extends Error {
  constructor(kind, code) {
    const controlMessages = {
      WINDOWS_EXECUTOR_UNAVAILABLE: 'Le moteur Windows est déconnecté ou ce profil n’est pas disponible. Connectez le moteur et le téléphone.',
      OCCURRENCE_ALREADY_REQUESTED: 'Cette occurrence a déjà été lancée ou publiée. Consultez son rapport ; elle ne sera pas rejouée.',
      SETTING_IN_USE: 'Cette référence est utilisée par une matrice. Modifiez la matrice avant de supprimer ou renommer la référence.',
      NAME_ALREADY_EXISTS: 'Ce nom existe déjà dans cette rubrique.',
      CONFIGURATION_CHANGED: 'La configuration a changé. Fermez le formulaire, actualisez et reprenez la modification.',
      SETTING_REFERENCE_MISSING: 'Sélectionnez un profil, un système et des albums enregistrés.',
    };
    super(controlMessages[code] || messages[kind] || messages.unavailable);
    this.kind = kind;
  }
}

export async function request(path, { method = "GET", body } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(path, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      referrerPolicy: "no-referrer",
      headers: {
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const kind = { 401: "unauthorized", 403: "forbidden", 409: "conflict", 400: "invalid", 422: "invalid" }[response.status];
      const safe = await response.json().catch(() => ({}));
      throw new PilotError(kind || "unavailable", safe.error);
    }
    if (response.status === 204) return {};
    try { return await response.json(); }
    catch { throw new PilotError("unavailable"); }
  } catch (error) {
    if (error instanceof PilotError) throw error;
    throw new PilotError("unavailable");
  } finally {
    clearTimeout(timeout);
  }
}
