/**
 * Client minimal pour l'API Django (Mairy Project).
 * Toutes les erreurs sont normalisées en `ApiError` pour que les pages
 * n'aient à gérer que quelques cas : réseau, introuvable, limitation, serveur.
 */

const RAW_API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
export const API_URL = RAW_API_URL.replace(/\/+$/, '')

export type ApiErrorKind =
  | 'network'
  | 'not_found'
  | 'throttled'
  | 'validation'
  | 'unauthenticated'
  | 'server'

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly fieldErrors: Record<string, string[]>

  constructor(kind: ApiErrorKind, fieldErrors: Record<string, string[]> = {}) {
    super(kind)
    this.name = 'ApiError'
    this.kind = kind
    this.fieldErrors = fieldErrors
  }
}

/* ------------------------------------------------------------------ */
/* Vérification d'un document                                          */
/* ------------------------------------------------------------------ */

export type VerifyStatus = 'VALID' | 'REVOKED' | 'EXPIRED' | 'INVALID'

export interface VerifiedDocument {
  document_type: string
  document_type_label: string
  holder_first_name: string
  holder_last_name: string
  holder_national_id: string | null
  holder_photo_url: string | null
  issue_date: string
  signature_fingerprint: string
  pdf_url: string | null
}

export interface VerifyResponse {
  id: string
  is_authentic: boolean
  status: VerifyStatus
  hash_matches: boolean
  signature_valid: boolean
  /** Renseigné uniquement si le document est authentique (masquage sinon). */
  document: VerifiedDocument | null
}

async function request(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch (error) {
    // Une annulation volontaire (AbortController) doit rester une annulation.
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    throw new ApiError('network')
  }
}

export async function verifyDocument(token: string, signal?: AbortSignal): Promise<VerifyResponse> {
  // Le backend n'accepte que des UUID en minuscules.
  const response = await request(`${API_URL}/api/verify/${token.toLowerCase()}/`, {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (response.status === 404) {
    throw new ApiError('not_found')
  }
  if (!response.ok) {
    throw new ApiError('server')
  }

  try {
    return (await response.json()) as VerifyResponse
  } catch {
    throw new ApiError('server')
  }
}

/* ------------------------------------------------------------------ */
/* Demande d'accès agent                                               */
/* ------------------------------------------------------------------ */

export interface AgentRequestPayload {
  first_name: string
  last_name: string
  phone_number: string
  email: string
  request_type: string
  message: string
}

export async function submitAgentRequest(payload: AgentRequestPayload): Promise<void> {
  const response = await request(`${API_URL}/api/agent-requests/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload),
  })

  if (response.status === 201) {
    return
  }
  if (response.status === 429) {
    throw new ApiError('throttled')
  }
  if (response.status === 400) {
    let errors: Record<string, string[]> = {}
    try {
      const data = (await response.json()) as { errors?: Record<string, string[]> }
      errors = data.errors ?? {}
    } catch {
      // corps illisible : on retombe sur un message générique
    }
    throw new ApiError('validation', errors)
  }
  throw new ApiError('server')
}

/** URL de l'image PNG du QR code d'un document (utile pour l'impression). */
export function qrCodeUrl(token: string): string {
  return `${API_URL}/api/documents/${token.toLowerCase()}/qr.png`
}

/* ------------------------------------------------------------------ */
/* Page « Contact »                                                    */
/* ------------------------------------------------------------------ */

export interface ContactPayload {
  first_name: string
  last_name: string
  phone: string
  email: string
  message: string
}

/** Envoie un message depuis la page publique « Contact » (aucune connexion requise). */
export async function submitContact(payload: ContactPayload): Promise<void> {
  const response = await request(`${API_URL}/api/contact/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload),
  })

  if (response.status === 201) {
    return
  }
  if (response.status === 429) {
    throw new ApiError('throttled')
  }
  if (response.status === 400) {
    let errors: Record<string, string[]> = {}
    try {
      const data = (await response.json()) as { errors?: Record<string, string[]> }
      errors = data.errors ?? {}
    } catch {
      // corps illisible : on retombe sur un message générique
    }
    throw new ApiError('validation', errors)
  }
  throw new ApiError('server')
}
