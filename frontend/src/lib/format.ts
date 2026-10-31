/** Formate une date ISO pour l'affichage (langue du site ; le malgache retombe sur le français si indisponible). */
export function formatDateTime(iso: string | null | undefined, language: string): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''

  const options: Intl.DateTimeFormatOptions = { dateStyle: 'medium', timeStyle: 'short' }
  try {
    return new Intl.DateTimeFormat(language, options).format(date)
  } catch {
    return new Intl.DateTimeFormat('fr', options).format(date)
  }
}

/** Date seule (sans l'heure). */
export function formatDate(iso: string | null | undefined, language: string): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''

  const options: Intl.DateTimeFormatOptions = { dateStyle: 'medium' }
  try {
    return new Intl.DateTimeFormat(language, options).format(date)
  } catch {
    return new Intl.DateTimeFormat('fr', options).format(date)
  }
}
