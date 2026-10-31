/**
 * Client de l'API « espace utilisateur » (dossiers et notifications).
 *
 * Toutes les requêtes sont authentifiées par le jeton de session Clerk
 * (en-tête `Authorization: Bearer …`). Les erreurs sont normalisées en
 * `ApiError`, comme dans `api.ts`.
 */
import type { DossierStatus, DossierType } from '@/data/catalog'
import { API_URL, ApiError } from '@/lib/api'

/** Fournit le jeton de session Clerk (`getToken` de `useAuth()`). */
export type GetToken = () => Promise<string | null>

/** Document (ex. acte de naissance) envoyé par l'agent à l'usager pour sa demande. */
export interface DossierDocument {
  id: string
  label: string
  filename: string
  sent_at: string | null
}

/** Une demande de dossier, telle que listée par l'API. */
export interface DossierSummary {
  id: number
  reference: string
  dossier_type: DossierType
  /** Numéro du guichet qui traite la demande (« 1 » à « 5 »), attribué selon son type. */
  guichet: string
  status: DossierStatus
  created_at: string
  updated_at: string
  /** Réponse de la Commune : vide tant qu'elle n'a pas répondu. */
  response_message: string
  responded_at: string | null
  response_read: boolean
  /** Documents téléchargeables (envoyés par l'agent). */
  documents: DossierDocument[]
}

export interface CreateDossierPayload {
  dossier_type: DossierType
  guichet: string
  identity: Record<string, string>
  details: Record<string, string>
}

export interface CreateDossierResult {
  id: number
  reference: string
  status: DossierStatus
  created_at: string
}

async function authorizedFetch(
  getToken: GetToken,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  let token: string | null
  try {
    token = await getToken()
  } catch {
    throw new ApiError('network')
  }
  if (!token) {
    throw new ApiError('unauthenticated')
  }

  try {
    return await fetch(`${API_URL}/api${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...init.headers,
        Authorization: `Bearer ${token}`,
      },
    })
  } catch (error) {
    // Une annulation volontaire (AbortController) doit rester une annulation.
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    throw new ApiError('network')
  }
}

/** Transforme une réponse HTTP en échec `ApiError` (ne renvoie jamais). */
async function failFrom(response: Response): Promise<never> {
  if (response.status === 401) throw new ApiError('unauthenticated')
  if (response.status === 404) throw new ApiError('not_found')
  if (response.status === 429) throw new ApiError('throttled')
  if (response.status === 400) {
    let errors: Record<string, string[]> = {}
    try {
      const data = (await response.json()) as { errors?: Record<string, string[]> }
      errors = data.errors ?? {}
    } catch {
      // corps illisible : on retombe sur une erreur de validation générique
    }
    throw new ApiError('validation', errors)
  }
  throw new ApiError('server')
}

async function readJson<T>(response: Response): Promise<T> {
  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError('server')
  }
}

/** Dépose une nouvelle demande de dossier. */
export async function createDossier(
  getToken: GetToken,
  payload: CreateDossierPayload,
): Promise<CreateDossierResult> {
  const response = await authorizedFetch(getToken, '/dossiers/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (response.status !== 201) {
    return failFrom(response)
  }
  return readJson<CreateDossierResult>(response)
}

/** Liste les demandes de l'utilisateur connecté (les plus récentes d'abord). */
export async function listDossiers(
  getToken: GetToken,
  signal?: AbortSignal,
): Promise<DossierSummary[]> {
  const response = await authorizedFetch(getToken, '/dossiers/', { signal })
  if (!response.ok) {
    return failFrom(response)
  }
  const data = await readJson<{ results?: DossierSummary[] }>(response)
  return Array.isArray(data.results) ? data.results : []
}

/** Marque la réponse d'une demande comme lue. */
export async function markDossierRead(getToken: GetToken, id: number): Promise<void> {
  const response = await authorizedFetch(getToken, `/dossiers/${id}/read/`, { method: 'POST' })
  if (!response.ok) {
    return failFrom(response)
  }
}

/** Marque toutes les réponses reçues comme lues ; renvoie le nombre mis à jour. */
export async function markAllRead(getToken: GetToken): Promise<number> {
  const response = await authorizedFetch(getToken, '/dossiers/read-all/', { method: 'POST' })
  if (!response.ok) {
    return failFrom(response)
  }
  const data = await readJson<{ updated?: number }>(response)
  return typeof data.updated === 'number' ? data.updated : 0
}

/** Télécharge le PDF d'un document envoyé à l'usager (le navigateur l'enregistre). */
export async function downloadDossierDocument(
  getToken: GetToken,
  dossierId: number,
  document: DossierDocument,
): Promise<void> {
  const response = await authorizedFetch(getToken, `/dossiers/${dossierId}/documents/${document.id}/`, {
    headers: { Accept: 'application/pdf' },
  })
  if (!response.ok) {
    return failFrom(response)
  }
  const url = URL.createObjectURL(await response.blob())
  try {
    const link = window.document.createElement('a')
    link.href = url
    link.download = document.filename
    window.document.body.appendChild(link)
    link.click()
    link.remove()
  } finally {
    // Laisse au navigateur le temps de démarrer le téléchargement.
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}

/* ------------------------------------------------------------------ */
/* Mail de l'usager                                                    */
/* ------------------------------------------------------------------ */

/** Message échangé avec un guichet ou l'administration (reçu ou envoyé). */
export interface CitizenMail {
  id: number
  folder: 'inbox' | 'sent'
  /** Guichet (« 1 » à « 5 ») ou « mairie ». */
  service: string
  service_label: string
  sender_name: string
  subject: string
  body: string
  created_at: string
  is_read: boolean
}

/** Destinataire possible d'un message. */
export interface MailService {
  value: string
  label: string
}

export interface SendMailPayload {
  service: string
  subject: string
  body: string
  sender_name: string
  sender_email: string
}

/** Messages de l'usager (les plus récents d'abord) et destinataires possibles. */
export async function listMails(
  getToken: GetToken,
  signal?: AbortSignal,
): Promise<{ results: CitizenMail[]; services: MailService[] }> {
  const response = await authorizedFetch(getToken, '/mails/', { signal })
  if (!response.ok) {
    return failFrom(response)
  }
  const data = await readJson<{ results?: CitizenMail[]; services?: MailService[] }>(response)
  return {
    results: Array.isArray(data.results) ? data.results : [],
    services: Array.isArray(data.services) ? data.services : [],
  }
}

/** Envoie un message à un guichet ou à l'administration. */
export async function sendMail(getToken: GetToken, payload: SendMailPayload): Promise<CitizenMail> {
  const response = await authorizedFetch(getToken, '/mails/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    return failFrom(response)
  }
  return readJson<CitizenMail>(response)
}

/** Marque un message reçu comme lu. */
export async function markMailRead(getToken: GetToken, id: number): Promise<void> {
  const response = await authorizedFetch(getToken, `/mails/${id}/read/`, { method: 'POST' })
  if (!response.ok) {
    return failFrom(response)
  }
}

/* ------------------------------------------------------------------ */
/* Assistant IA                                                        */
/* ------------------------------------------------------------------ */

/** Lien proposé par l'assistant (chemin interne de l'application). */
export interface AssistantItem {
  label: string
  meta?: string
  url: string
}

export interface AssistantReply {
  text: string
  items: AssistantItem[]
}

/** Pose une question à l'assistant de l'espace usager. */
export async function askAssistant(getToken: GetToken, message: string): Promise<AssistantReply> {
  const response = await authorizedFetch(getToken, '/assistant/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!response.ok) {
    return failFrom(response)
  }
  const data = await readJson<Partial<AssistantReply>>(response)
  return { text: data.text ?? '', items: Array.isArray(data.items) ? data.items : [] }
}
