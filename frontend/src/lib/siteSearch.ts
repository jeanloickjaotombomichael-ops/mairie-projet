/**
 * Recherche dans les informations de la plateforme (accueil et espace utilisateur).
 * Tout se fait dans le navigateur : aucun appel réseau, aucune recherche externe.
 */
import type { TFunction } from 'i18next'
import { DOSSIER_TYPES, publicPath } from '@/data/catalog'

/** Minuscules sans accents, pour que « etat civil » trouve « État civil ». */
export function normalizeText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim()
}

/** Vrai si chaque mot de la recherche apparaît dans le texte. */
export function matchesQuery(haystack: string, query: string): boolean {
  const words = normalizeText(query).split(/\s+/).filter(Boolean)
  if (words.length === 0) return false
  const text = normalizeText(haystack)
  return words.every((word) => text.includes(word))
}

export interface SiteSearchEntry {
  id: string
  path: string
  group: 'service' | 'page'
  title: string
  /** Texte dans lequel on cherche (titre, description, pièces à fournir…). */
  haystack: string
}

/** Entrées de recherche du site public, dans la langue courante. */
export function buildSiteEntries(t: TFunction): SiteSearchEntry[] {
  const entries: SiteSearchEntry[] = [
    {
      id: 'page-home',
      path: '/',
      group: 'page',
      title: t('header.nav.home'),
      haystack: `${t('header.nav.home')} ${t('home.title')} ${t('home.subtitle')}`,
    },
    {
      id: 'page-services',
      path: '/services',
      group: 'page',
      title: t('catalog.servicesTitle'),
      haystack: `${t('catalog.servicesTitle')} ${t('catalog.servicesIntro')}`,
    },
    {
      id: 'page-civil',
      path: '/services/etat-civil',
      group: 'page',
      title: t('catalog.civil.title'),
      haystack: `${t('catalog.civil.title')} ${t('catalog.civil.description')}`,
    },
    {
      id: 'page-contact',
      path: '/contact',
      group: 'page',
      title: t('header.nav.contact'),
      haystack: `${t('header.nav.contact')} ${t('contactPage.title')} ${t('contactPage.intro', { email: '' })}`,
    },
    {
      id: 'page-scan',
      path: '/scanner',
      group: 'page',
      title: t('scan.title'),
      haystack: `${t('scan.title')} ${t('scan.instructions')} ${t('search.pages.verify')} QR`,
    },
    {
      id: 'page-agent',
      path: '/demande-agent',
      group: 'page',
      title: t('home.ctaAgent'),
      haystack: `${t('home.ctaAgent')} ${t('agent.title')}`,
    },
    {
      id: 'page-espace',
      path: '/espace',
      group: 'page',
      title: t('search.pages.espace'),
      haystack: `${t('search.pages.espace')} ${t('nav.mySpace')} ${t('header.login')}`,
    },
  ]

  for (const type of DOSSIER_TYPES) {
    const pieces = t(`catalog.types.${type}.pieces`, { returnObjects: true }) as string[]
    entries.push({
      id: `service-${type}`,
      path: publicPath(type),
      group: 'service',
      title: t(`catalog.types.${type}.title`),
      haystack: `${t(`catalog.types.${type}.title`)} ${t(`catalog.types.${type}.description`)} ${
        Array.isArray(pieces) ? pieces.join(' ') : ''
      }`,
    })
  }

  return entries
}

/** Résultats triés : les titres qui contiennent la recherche passent avant. */
export function searchSiteEntries(
  entries: readonly SiteSearchEntry[],
  query: string,
  limit = 8,
): SiteSearchEntry[] {
  const needle = normalizeText(query)
  if (!needle) return []

  const matches = entries.filter((entry) => matchesQuery(entry.haystack, query))
  const inTitle = (entry: SiteSearchEntry) => (normalizeText(entry.title).includes(needle) ? 0 : 1)
  return [...matches].sort((a, b) => inTitle(a) - inTitle(b)).slice(0, limit)
}
