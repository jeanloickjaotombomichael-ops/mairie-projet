/**
 * Catalogue partagé : services municipaux, dossiers d'état civil, guichets.
 *
 * Source unique des identifiants utilisés par le site public (menu Services,
 * pages de service), l'espace utilisateur (rangées de demandes, formulaires) et
 * l'API Django (`dossier_type`).
 */

/* ------------------------------------------------------------------ */
/* Slugs d'URL                                                         */
/* ------------------------------------------------------------------ */

/** Services du menu « Services » (ordre d'affichage du site public). */
export const SERVICE_SLUGS = [
  'recette',
  'transport',
  'urbanisme',
  'marche',
  'cadastre',
  'impot-foncier',
] as const

/** Sous-menu « État civil ». */
export const CIVIL_SLUGS = ['naissance', 'mariage', 'deces', 'legislation', 'actes-divers'] as const

export type ServiceSlug = (typeof SERVICE_SLUGS)[number]
export type CivilSlug = (typeof CIVIL_SLUGS)[number]
export type DossierSlug = ServiceSlug | CivilSlug

/* ------------------------------------------------------------------ */
/* Types de dossier (valeurs envoyées à l'API : champ `dossier_type`)  */
/* ------------------------------------------------------------------ */

export const DOSSIER_TYPES = [
  'recette',
  'transport',
  'urbanisme',
  'marche',
  'cadastre',
  'impot_foncier',
  'naissance',
  'mariage',
  'deces',
  'legislation',
  'actes_divers',
] as const

export type DossierType = (typeof DOSSIER_TYPES)[number]

const SLUG_TO_TYPE: Record<DossierSlug, DossierType> = {
  recette: 'recette',
  transport: 'transport',
  urbanisme: 'urbanisme',
  marche: 'marche',
  cadastre: 'cadastre',
  'impot-foncier': 'impot_foncier',
  naissance: 'naissance',
  mariage: 'mariage',
  deces: 'deces',
  legislation: 'legislation',
  'actes-divers': 'actes_divers',
}

const TYPE_TO_SLUG: Record<DossierType, DossierSlug> = {
  recette: 'recette',
  transport: 'transport',
  urbanisme: 'urbanisme',
  marche: 'marche',
  cadastre: 'cadastre',
  impot_foncier: 'impot-foncier',
  naissance: 'naissance',
  mariage: 'mariage',
  deces: 'deces',
  legislation: 'legislation',
  actes_divers: 'actes-divers',
}

export function isServiceSlug(value: string | undefined): value is ServiceSlug {
  return value !== undefined && (SERVICE_SLUGS as readonly string[]).includes(value)
}

export function isCivilSlug(value: string | undefined): value is CivilSlug {
  return value !== undefined && (CIVIL_SLUGS as readonly string[]).includes(value)
}

export function isDossierSlug(value: string | undefined): value is DossierSlug {
  return isServiceSlug(value) || isCivilSlug(value)
}

export function isDossierType(value: string | undefined | null): value is DossierType {
  return value !== undefined && value !== null && (DOSSIER_TYPES as readonly string[]).includes(value)
}

export function slugToType(slug: DossierSlug): DossierType {
  return SLUG_TO_TYPE[slug]
}

export function typeToSlug(type: DossierType): DossierSlug {
  return TYPE_TO_SLUG[type]
}

export function isCivilType(type: DossierType): boolean {
  return isCivilSlug(TYPE_TO_SLUG[type])
}

/* ------------------------------------------------------------------ */
/* Chemins                                                             */
/* ------------------------------------------------------------------ */

/** Page publique d'un service ou d'un dossier d'état civil. */
export function publicPath(type: DossierType): string {
  const slug = TYPE_TO_SLUG[type]
  return isCivilSlug(slug) ? `/services/etat-civil/${slug}` : `/services/${slug}`
}

/** Formulaire de demande (espace utilisateur) pour un type de dossier. */
export function requestPath(type: DossierType): string {
  return `/espace/demande/${TYPE_TO_SLUG[type]}`
}

export const ESPACE_HOME = '/espace'
export const ESPACE_NOTIFICATIONS = '/espace/notifications'
export const ESPACE_MAIL = '/espace/mail'

/** Statuts d'une demande (valeurs de l'API). */
export const DOSSIER_STATUSES = ['PENDING', 'IN_PROGRESS', 'APPROVED', 'REJECTED', 'COMPLETED'] as const
export type DossierStatus = (typeof DOSSIER_STATUSES)[number]
