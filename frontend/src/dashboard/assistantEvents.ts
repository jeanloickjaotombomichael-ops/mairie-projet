/** Événement émis quand l'usager vient d'envoyer une demande : l'assistant lui répond peu après. */
export const DOSSIER_SENT_EVENT = 'mairy:dossier-sent'

/** Délai avant l'accusé de réception de l'assistant. */
export const DOSSIER_ACK_DELAY_MS = 5_000

export interface DossierSentDetail {
  reference: string
}

export function announceDossierSent(reference: string): void {
  window.dispatchEvent(new CustomEvent<DossierSentDetail>(DOSSIER_SENT_EVENT, { detail: { reference } }))
}
