/**
 * Mémorise la page où renvoyer l'usager une fois connecté
 * (ex. le formulaire du service qu'il consultait), le temps de la fenêtre de connexion.
 */
const STORAGE_KEY = 'mairy-project-return-to'

/** Seuls les chemins internes de l'espace personnel sont acceptés. */
function isSafePath(path: string): boolean {
  return path.startsWith('/espace') && !path.startsWith('//')
}

export function rememberReturnTo(path: string): void {
  if (!isSafePath(path)) return
  try {
    window.sessionStorage.setItem(STORAGE_KEY, path)
  } catch {
    // stockage indisponible : l'usager arrivera simplement sur l'accueil de l'espace
  }
}

/** Renvoie (et oublie) la page mémorisée, ou `null`. */
export function consumeReturnTo(): string | null {
  try {
    const path = window.sessionStorage.getItem(STORAGE_KEY)
    window.sessionStorage.removeItem(STORAGE_KEY)
    return path && isSafePath(path) ? path : null
  } catch {
    return null
  }
}
