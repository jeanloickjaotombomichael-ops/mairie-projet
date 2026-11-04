/**
 * Schéma des formulaires de demande.
 *
 * Reflète exactement `backend/espace/schemas.py` : mêmes noms de champs, mêmes
 * règles. Le serveur reste l'autorité ; cette validation côté navigateur évite
 * seulement un aller-retour inutile.
 */
import type { DossierType } from '@/data/catalog'

export type FieldKind =
  | 'text'
  | 'textarea'
  | 'date'
  | 'time'
  | 'integer'
  | 'number'
  | 'select'
  | 'choice'
  | 'email'
  | 'phone'
  | 'cin'

/** Codes d'erreur ; ils correspondent aux clés `dash.form.errors.*`. */
export type FieldErrorCode = 'required' | 'invalid' | 'too_long' | 'email' | 'phone' | 'cin'

export interface FieldDef {
  name: string
  kind: FieldKind
  required: boolean
  maxLength: number
  /** Valeurs possibles d'une liste ; le libellé est `dash.options.<valeur>`. */
  options?: readonly string[]
  min?: number
  max?: number
  /** Valeur initiale (ex. nombre de copies = 1). */
  defaultValue?: () => string
  /** Les valeurs de la liste s'affichent telles quelles (noms propres, ex. fokontany). */
  rawOptions?: boolean
  /** Texte de la première option vide (clé de traduction), à la place de « Sélectionner… ». */
  placeholder?: string
  /** Peut rester vide dans l'espace usager (sinon tout y est demandé, même les champs facultatifs du serveur). */
  optional?: boolean
  /** Rubrique du formulaire (clé `dash.sections.<rubrique>`) : les champs sont regroupés sous un titre. */
  section?: string
}

const text = (name: string, required = false, maxLength = 200): FieldDef => ({
  name,
  kind: 'text',
  required,
  maxLength,
})

const textarea = (name: string, required = false): FieldDef => ({
  name,
  kind: 'textarea',
  required,
  maxLength: 2000,
})

const date = (name: string): FieldDef => ({ name, kind: 'date', required: true, maxLength: 10 })

const integer = (name: string, min: number, max: number, defaultValue?: () => string): FieldDef => ({
  name,
  kind: 'integer',
  required: true,
  maxLength: 4,
  min,
  max,
  defaultValue,
})

const copies = (): FieldDef => integer('copies', 1, 10, () => '1')

const select = (name: string, options: readonly string[]): FieldDef => ({
  name,
  kind: 'select',
  required: true,
  maxLength: 40,
  options,
})

const decimal = (name: string): FieldDef => ({ name, kind: 'number', required: false, maxLength: 20 })

/** Champ facultatif, y compris dans l'espace usager. */
const optional = (field: FieldDef): FieldDef => ({ ...field, required: false, optional: true })

const time = (name: string): FieldDef => optional({ name, kind: 'time', required: false, maxLength: 5 })

/** Range des champs sous une même rubrique. */
const inSection = (section: string, fields: readonly FieldDef[]): FieldDef[] =>
  fields.map((field) => ({ ...field, section }))

const SEXES = ['M', 'F'] as const

/** Parent de l'enfant (acte de naissance) ; le père peut rester vide (filiation non établie). */
const parent = (prefix: 'father' | 'mother'): FieldDef[] => {
  const fields = [
    text(`${prefix}_full_name`, true),
    date(`${prefix}_birth_date`),
    text(`${prefix}_birth_place`, true),
    optional(text(`${prefix}_profession`, false, 150)),
    text(`${prefix}_address`, true, 255),
  ]
  return inSection(prefix, prefix === 'father' ? fields.map(optional) : fields)
}

/** Époux ou épouse (acte de mariage), avec ses parents. */
const spouse = (prefix: 'husband' | 'wife'): FieldDef[] =>
  inSection(prefix, [
    text(`${prefix}_last_name`, true, 150),
    text(`${prefix}_first_names`, true),
    date(`${prefix}_birth_date`),
    text(`${prefix}_birth_place`, true),
    optional(text(`${prefix}_profession`, false, 150)),
    text(`${prefix}_address`, true, 255),
    optional(text(`${prefix}_father_name`)),
    optional(text(`${prefix}_father_profession`, false, 150)),
    optional(text(`${prefix}_mother_name`)),
    optional(text(`${prefix}_mother_profession`, false, 150)),
  ])

/** Identité du demandeur, commune à tous les dossiers. */
export const IDENTITY_FIELDS: readonly FieldDef[] = [
  text('last_name', true, 100),
  text('first_name', true, 100),
  // E-mail et téléphone facultatifs : beaucoup d'usagers (notamment en zone rurale) n'en ont pas.
  optional({ name: 'email', kind: 'email', required: false, maxLength: 254 }),
  optional({ name: 'phone', kind: 'phone', required: false, maxLength: 30 }),
  { name: 'national_id', kind: 'cin', required: false, maxLength: 30 },
  text('address', false, 200),
]

/** Champ « Précisions », accepté pour tous les types de dossier. */
const COMMENT_FIELD: FieldDef = textarea('comment')

/*
 * Actes : les mêmes informations que le document officiel. Le demandeur les saisit ici ;
 * elles arrivent déjà remplies dans le formulaire de l'agent qui établit l'acte.
 */
const DETAIL_FIELDS: Record<DossierType, readonly FieldDef[]> = {
  naissance: [
    ...inSection('child', [
      text('concerned_last_name', true),
      text('concerned_first_name', true),
      select('child_sex', SEXES),
      date('birth_date'),
      time('birth_time'),
      text('birth_place', true),
    ]),
    ...parent('father'),
    ...parent('mother'),
    ...inSection('request', [text('declarant_relationship', true, 150), copies()]),
  ],
  mariage: [
    ...inSection('celebration', [
      date('marriage_date'),
      time('marriage_time'),
      text('marriage_place', true),
      optional(text('matrimonial_regime', false, 500)),
    ]),
    ...spouse('husband'),
    ...spouse('wife'),
    ...inSection('witnesses', [
      text('witness1_name', true),
      optional(text('witness1_details', false, 255)),
      text('witness2_name', true),
      optional(text('witness2_details', false, 255)),
    ]),
    ...inSection('request', [copies()]),
  ],
  deces: [
    ...inSection('deceased', [
      text('deceased_last_name', true, 150),
      text('deceased_first_names', true),
      select('deceased_sex', SEXES),
      optional(date('deceased_birth_date')),
      optional(text('deceased_birth_place')),
      optional(text('deceased_profession', false, 150)),
      text('deceased_address', true, 255),
    ]),
    ...inSection('family', [
      optional(select('marital_status', ['SINGLE', 'MARRIED', 'WIDOWED', 'DIVORCED'])),
      optional(text('spouse_name')),
      optional(text('father_name')),
      optional(select('father_deceased', ['oui', 'non'])),
      optional(text('mother_name')),
      optional(select('mother_deceased', ['oui', 'non'])),
    ]),
    ...inSection('death', [date('death_date'), time('death_time'), text('death_place', true)]),
    ...inSection('declarant', [
      select('relationship', ['spouse', 'child', 'parent', 'sibling', 'other']),
      optional(integer('declarant_age', 10, 120)),
      optional(text('declarant_profession', false, 150)),
      copies(),
    ]),
  ],
  legislation: inSection('text', [
    select('text_type', ['arrete', 'deliberation', 'reglement', 'decision', 'other']),
    text('reference_number'),
    optional(date('text_date')),
    text('subject', true),
  ]),
  actes_divers: [text('act_nature', true), textarea('description', true), copies()],
  recette: [
    select('payment_type', ['taxe_marche', 'patente', 'droit_place', 'location', 'other']),
    text('reference_number'),
    decimal('amount'),
    text('period'),
  ],
  urbanisme: [
    select('request_kind', [
      'permis_construire',
      'certificat_urbanisme',
      'autorisation_travaux',
      'alignement',
    ]),
    text('plot_address', true),
    textarea('works_description', true),
    decimal('surface'),
    text('cadastral_reference'),
  ],
  transport: [
    select('request_kind', ['licence', 'carte_stationnement', 'autorisation_ligne', 'renouvellement']),
    select('vehicle_type', ['taxi', 'bus', 'pousse_pousse', 'bajaj', 'moto', 'other']),
    text('vehicle_plate', true),
    text('license_number'),
  ],
  marche: [
    select('request_kind', ['emplacement', 'renouvellement', 'transfert', 'resiliation']),
    text('market_name', true),
    text('activity', true),
    text('stall_number'),
  ],
  cadastre: [
    select('request_kind', ['extrait', 'certificat_propriete', 'bornage', 'mutation']),
    text('parcel_reference', true),
    text('district', true),
    text('title_number'),
  ],
  impot_foncier: [
    select('request_kind', ['declaration', 'avis_imposition', 'attestation_paiement', 'reclamation']),
    text('property_address', true),
    integer('tax_year', 2000, 2100, () => String(new Date().getFullYear())),
    text('tax_reference'),
  ],
}

/** Fokontany de la Commune urbaine de Mahajanga (même liste que `FOKONTANY` côté serveur). */
export const FOKONTANY = [
  'Abattoir',
  'Ambalavola',
  'Ambohimandamina',
  'Ambondrona',
  'Amborovy',
  'Ambovoalanana',
  'Ampisikina',
  'Antanimalandy',
  'Antanimasaja',
  'Antsahabingo',
  'Aranta',
  'Fiofio',
  'Mahabibo',
  'Mahajanga Be',
  'Mahatsinjo',
  'Mahavoky Atsimo',
  'Mahavoky Avaratra',
  'Manga',
  'Mangarivotra',
  'Manjarisoa',
  'Morafeno',
  'Tanambao Sotema',
  'Tsaramandroso Ambany',
  'Tsaramandroso Ambony',
  'Tsararano Ambany',
  'Tsararano Ambony',
] as const

/** Étape « Quartier » des demandes d'actes (envoyée avec les détails de la demande). */
const QUARTIER_FIELDS: readonly FieldDef[] = [
  {
    ...select('fokontany', FOKONTANY),
    maxLength: 60,
    rawOptions: true,
    placeholder: 'dash.form.chooseFokontany',
  },
  // Deux boutons « Oui » / « Non » côte à côte.
  { ...select('main_residence', ['oui', 'non']), kind: 'choice', defaultValue: () => 'oui' },
]

const QUARTIER_TYPES: readonly DossierType[] = ['naissance', 'mariage', 'deces', 'legislation']

/** Champs de l'étape « Quartier » (aucun pour les dossiers qui ne sont pas des actes). */
export function quartierFields(type: DossierType): readonly FieldDef[] {
  return QUARTIER_TYPES.includes(type) ? QUARTIER_FIELDS : []
}

/** Champs de détails d'un type de dossier (le champ « Précisions » en dernier). */
export function detailFields(type: DossierType): readonly FieldDef[] {
  return [...DETAIL_FIELDS[type], COMMENT_FIELD]
}

/*
 * Découpage des détails en plusieurs étapes (rubriques regroupées) pour les actes les plus longs :
 * avec « Vos informations » et « Quartier », le formulaire compte alors cinq étapes.
 */
const DETAIL_STEPS: Partial<Record<DossierType, readonly { key: string; sections: readonly string[] }[]>> = {
  naissance: [
    { key: 'child', sections: ['child'] },
    { key: 'parents', sections: ['father', 'mother'] },
    { key: 'request', sections: ['request'] },
  ],
  mariage: [
    { key: 'celebration', sections: ['celebration'] },
    { key: 'spouses', sections: ['husband', 'wife'] },
    { key: 'witnesses', sections: ['witnesses', 'request'] },
  ],
  deces: [
    { key: 'deceased', sections: ['deceased', 'family'] },
    { key: 'death', sections: ['death'] },
    { key: 'declarant', sections: ['declarant'] },
  ],
}

/** Étapes de la partie « Détails » (une seule, `details`, pour les dossiers non découpés). */
export function detailSteps(type: DossierType): { key: string; fields: FieldDef[] }[] {
  const fields = detailFields(type)
  const groups = DETAIL_STEPS[type]
  if (!groups) return [{ key: 'details', fields: [...fields] }]
  const steps = groups.map((group) => ({
    key: group.key,
    fields: fields.filter((field) => field.section !== undefined && group.sections.includes(field.section)),
  }))
  // Champs sans rubrique (« Précisions ») : à la dernière étape des détails.
  steps[steps.length - 1].fields.push(...fields.filter((field) => field.section === undefined))
  return steps
}

/** Valeurs initiales d'une liste de champs (vide, sauf valeur par défaut). */
export function defaultsFor(fields: readonly FieldDef[]): Record<string, string> {
  const values: Record<string, string> = {}
  for (const field of fields) {
    values[field.name] = field.defaultValue ? field.defaultValue() : ''
  }
  return values
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE_PATTERN = /^[0-9+()\-.\s]{6,30}$/
/** N° de CIN malgache : 12 chiffres, espaces de groupement acceptés (« 101 234 567 890 »). */
const CIN_PATTERN = /^\d{12}$/
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/
const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/
const INTEGER_PATTERN = /^\d{1,4}$/
const NUMBER_PATTERN = /^\d+([.,]\d+)?$/

function isRealDate(value: string): boolean {
  if (!DATE_PATTERN.test(value)) return false
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

/** Valide une saisie ; renvoie le code d'erreur, ou `null` si elle est correcte. */
export function validateField(field: FieldDef, raw: string): FieldErrorCode | null {
  const value = raw.trim()
  if (!value) return field.required ? 'required' : null
  if (value.length > field.maxLength) return 'too_long'

  switch (field.kind) {
    case 'email':
      return EMAIL_PATTERN.test(value) ? null : 'email'
    case 'phone':
      return PHONE_PATTERN.test(value) ? null : 'phone'
    case 'cin':
      return CIN_PATTERN.test(value.replace(/\s/g, '')) ? null : 'cin'
    case 'date':
      return isRealDate(value) ? null : 'invalid'
    case 'time':
      return TIME_PATTERN.test(value) ? null : 'invalid'
    case 'integer': {
      if (!INTEGER_PATTERN.test(value)) return 'invalid'
      const number = Number(value)
      if (field.min !== undefined && number < field.min) return 'invalid'
      if (field.max !== undefined && number > field.max) return 'invalid'
      return null
    }
    case 'number':
      return NUMBER_PATTERN.test(value) ? null : 'invalid'
    case 'select':
    case 'choice':
      return field.options?.includes(value) ? null : 'invalid'
    default:
      return null
  }
}
