const messages = {
  unauthorized: "La session propriétaire est invalide ou a expiré. Reconnectez-vous.",
  forbidden: "Cette action n’est pas disponible pour cette session.",
  conflict: "L’état a changé. Actualisez l’espace avant de réessayer.",
  unavailable: "Le serveur du pilote est indisponible. Réessayez dans quelques instants.",
  invalid: "La demande n’a pas été acceptée. Vérifiez les champs renseignés.",
};
let ownerToken = "";

export function setOwnerToken(value) { ownerToken = value; }
export function clearOwnerToken() { ownerToken = ""; }

export class PilotError extends Error {
  constructor(kind) {
    super(messages[kind] || messages.unavailable);
    this.kind = kind;
  }
}

export async function request(path, { method = "GET", body } = {}) {
  if (!ownerToken) throw new PilotError("unauthorized");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(path, {
      method,
      credentials: "omit",
      cache: "no-store",
      referrerPolicy: "no-referrer",
      headers: {
        Authorization: `Bearer ${ownerToken}`,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const kind = { 401: "unauthorized", 403: "forbidden", 409: "conflict", 400: "invalid", 422: "invalid" }[response.status];
      throw new PilotError(kind || "unavailable");
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
