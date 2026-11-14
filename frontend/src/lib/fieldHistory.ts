/**
 * Mémoire des saisies du formulaire de demande : les valeurs déjà envoyées sont proposées
 * en suggestions dans chaque champ (comme la saisie automatique du navigateur).
 *
 * Conservée dans le navigateur (localStorage), séparément pour chaque compte.
 * Toute erreur de stockage (navigation privée, stockage bloqué) est ignorée.
 */
const PREFIX = "mairy:field-history:";
const MAX_PER_FIELD = 8;

type History = Record<string, string[]>;

function storageKey(userId: string): string {
  return `${PREFIX}${userId}`;
}

export function loadFieldHistory(userId: string | null | undefined): History {
  if (!userId) return {};
  try {
    const raw = window.localStorage.getItem(storageKey(userId));
    const data: unknown = raw ? JSON.parse(raw) : {};
    if (!data || typeof data !== "object" || Array.isArray(data)) return {};
    const history: History = {};
    for (const [name, list] of Object.entries(
      data as Record<string, unknown>,
    )) {
      if (Array.isArray(list))
        history[name] = list.filter(
          (item): item is string => typeof item === "string",
        );
    }
    return history;
  } catch {
    return {};
  }
}

/** Ajoute les valeurs envoyées en tête de l'historique de chaque champ (sans doublon). */
export function saveFieldHistory(
  userId: string | null | undefined,
  values: Record<string, string>,
): History {
  const history = loadFieldHistory(userId);
  if (!userId) return history;
  for (const [name, rawValue] of Object.entries(values)) {
    const value = rawValue.trim();
    if (!value) continue;
    const previous = (history[name] ?? []).filter(
      (item) => item.toLowerCase() !== value.toLowerCase(),
    );
    history[name] = [value, ...previous].slice(0, MAX_PER_FIELD);
  }
  try {
    window.localStorage.setItem(storageKey(userId), JSON.stringify(history));
  } catch {
    // Stockage indisponible : les suggestions ne seront simplement pas mémorisées.
  }
  return history;
}
