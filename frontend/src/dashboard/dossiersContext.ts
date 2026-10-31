import { createContext, useContext } from 'react'
import type { DossierSummary } from '@/lib/espaceApi'

export type DossiersStatus = 'loading' | 'ready' | 'error'

export interface DossiersState {
  /** Demandes de l'utilisateur, les plus récentes d'abord. */
  items: DossierSummary[]
  status: DossiersStatus
  /** Demandes envoyées. */
  total: number
  /** Demandes en attente ou en cours de traitement. */
  pending: number
  /** Demandes approuvées ou terminées. */
  done: number
  /** Réponses de la Commune pas encore lues. */
  unread: number
  reload: () => Promise<void>
  markRead: (id: number) => Promise<void>
  markAllRead: () => Promise<void>
}

export const DossiersContext = createContext<DossiersState | null>(null)

export function useDossiers(): DossiersState {
  const value = useContext(DossiersContext)
  if (!value) {
    throw new Error('useDossiers doit être utilisé dans <DossiersProvider>.')
  }
  return value
}
