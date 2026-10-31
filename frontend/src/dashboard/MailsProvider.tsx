import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useAuth } from '@clerk/react'
import { listMails, markMailRead, type CitizenMail, type MailService } from '@/lib/espaceApi'
import { MailsContext, type MailsState } from '@/dashboard/espaceContext'

/** Les réponses des agents arrivent sans recharger la page. */
const REFRESH_MS = 60_000

/** Charge les messages de l'usager et les partage avec l'espace (badge du menu, page Mail). */
function MailsProvider({ children }: { children: ReactNode }) {
  const { getToken } = useAuth()
  const [items, setItems] = useState<CitizenMail[]>([])
  const [services, setServices] = useState<MailService[]>([])
  const [status, setStatus] = useState<MailsState['status']>('loading')

  const getTokenRef = useRef(getToken)
  useEffect(() => {
    getTokenRef.current = getToken
  }, [getToken])

  const fetchItems = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await listMails(() => getTokenRef.current(), signal)
      setItems(data.results)
      setServices(data.services)
      setStatus('ready')
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      setStatus((current) => (current === 'ready' ? 'ready' : 'error'))
    }
  }, [])

  const reload = useCallback(() => fetchItems(), [fetchItems])

  useEffect(() => {
    const controller = new AbortController()
    void fetchItems(controller.signal)
    const refresh = () => {
      if (document.visibilityState === 'visible') void fetchItems()
    }
    const timer = window.setInterval(refresh, REFRESH_MS)
    window.addEventListener('focus', refresh)
    return () => {
      controller.abort()
      window.clearInterval(timer)
      window.removeEventListener('focus', refresh)
    }
  }, [fetchItems])

  const markRead = useCallback(
    async (id: number) => {
      setItems((current) => current.map((mail) => (mail.id === id ? { ...mail, is_read: true } : mail)))
      try {
        await markMailRead(() => getTokenRef.current(), id)
      } catch {
        await fetchItems()
      }
    },
    [fetchItems],
  )

  const add = useCallback((mail: CitizenMail) => setItems((current) => [mail, ...current]), [])

  const value = useMemo<MailsState>(
    () => ({
      items,
      services,
      status,
      unread: items.filter((mail) => mail.folder === 'inbox' && !mail.is_read).length,
      reload,
      markRead,
      add,
    }),
    [items, services, status, reload, markRead, add],
  )

  return <MailsContext.Provider value={value}>{children}</MailsContext.Provider>
}

export default MailsProvider
