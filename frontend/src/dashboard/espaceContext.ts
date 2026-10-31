import { createContext, useContext } from 'react'
import type { CitizenMail, MailService } from '@/lib/espaceApi'

export interface MailsState {
  /** Messages de l'usager (reçus et envoyés), les plus récents d'abord. */
  items: CitizenMail[]
  services: MailService[]
  status: 'loading' | 'ready' | 'error'
  /** Messages reçus pas encore lus. */
  unread: number
  reload: () => Promise<void>
  markRead: (id: number) => Promise<void>
  /** Ajoute un message que l'usager vient d'envoyer. */
  add: (mail: CitizenMail) => void
}

export const MailsContext = createContext<MailsState | null>(null)

export function useMails(): MailsState {
  const value = useContext(MailsContext)
  if (!value) {
    throw new Error('useMails doit être utilisé dans <MailsProvider>.')
  }
  return value
}

