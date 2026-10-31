/** Un UUID complet, n'importe où dans un texte (URL de QR code incluse). */
const UUID_IN_TEXT = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i

/** Un UUID, et rien d'autre. */
const UUID_ONLY = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function isUuid(value: string): boolean {
  return UUID_ONLY.test(value.trim())
}

/**
 * Extrait le premier UUID d'un texte (URL scannée, identifiant collé à la main…).
 * Retourne l'UUID en minuscules (le backend n'accepte que ce format), ou `null`.
 *
 * On n'utilise JAMAIS le texte scanné comme adresse de redirection : seul
 * l'UUID extrait est réutilisé, ce qui évite qu'un QR code piégé n'envoie
 * l'utilisateur vers un site externe.
 */
export function extractUuid(text: string): string | null {
  const match = UUID_IN_TEXT.exec(text)
  return match ? match[0].toLowerCase() : null
}
