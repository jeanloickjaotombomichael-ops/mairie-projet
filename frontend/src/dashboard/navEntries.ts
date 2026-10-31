import type { TFunction } from 'i18next'
import { DOSSIER_TYPES, ESPACE_HOME, ESPACE_NOTIFICATIONS, requestPath } from '@/data/catalog'

export interface NavEntry {
  id: string
  label: string
  /** Texte secondaire affiché dans les résultats (rubrique). */
  hint: string
  path: string
}

/** Pages de l'espace : la recherche de l'espace ne porte que sur cela. */
export function buildNavEntries(t: TFunction): NavEntry[] {
  const entries: NavEntry[] = [
    { id: 'home', label: t('dash.nav.home'), hint: t('dash.brand'), path: ESPACE_HOME },
  ]

  for (const type of DOSSIER_TYPES) {
    entries.push({
      id: `demande-${type}`,
      label: t(`catalog.types.${type}.title`),
      hint: t('dash.nav.demande'),
      path: requestPath(type),
    })
  }

  entries.push({
    id: 'notifications',
    label: t('dash.notifications.title'),
    hint: t('dash.topbar.notifications'),
    path: ESPACE_NOTIFICATIONS,
  })

  return entries
}
