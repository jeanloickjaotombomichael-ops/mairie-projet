import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useAuth } from '@clerk/react'
import { listDossiers, markAllRead as apiMarkAllRead, markDossierRead, type DossierSummary } from '@/lib/espaceApi'
import { DossiersContext, type DossiersState, type DossiersStatus } from '@/dashboard/dossiersContext'

/** Intervalle de rafraîchissement : les réponses de la Commune arrivent sans recharger la page. */
const REFRESH_MS = 60_000

function hasResponse(dossier: DossierSummary): boolean {
  return dossier.response_message.trim() !== ''
}

/** Charge les demandes de l'utilisateur et les partage avec tout l'espace personnel. */
function DossiersProvider({ children }: { children: ReactNode }) {
  const { getToken } = useAuth()
  const [items, setItems] = useState<DossierSummary[]>([])
  const [status, setStatus] = useState<DossiersStatus>('loading')

  // `getToken` change d'identité à chaque rendu chez Clerk : on garde la dernière version.
  const getTokenRef = useRef(getToken)
  useEffect(() => {
    getTokenRef.current = getToken
  }, [getToken])

  const fetchItems = useCallback(async (signal?: AbortSignal) => {
    try {
      const list = await listDossiers(() => getTokenRef.current(), signal)
      setItems(list)
      setStatus('ready')
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      // En cas d'échec d'un rafraîchissement, on garde ce qui est déjà affiché.
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
      setItems((current) =>
        current.map((dossier) => (dossier.id === id ? { ...dossier, response_read: true } : dossier)),
      )
      try {
        await markDossierRead(() => getTokenRef.current(), id)
      } catch {
        await fetchItems()
      }
    },
    [fetchItems],
  )

  const markAllRead = useCallback(async () => {
    setItems((current) =>
      current.map((dossier) => (hasResponse(dossier) ? { ...dossier, response_read: true } : dossier)),
    )
    try {
      await apiMarkAllRead(() => getTokenRef.current())
    } catch {
      await fetchItems()
    }
  }, [fetchItems])

  const value = useMemo<DossiersState>(() => {
    let pending = 0
    let done = 0
    let unread = 0
    for (const dossier of items) {
      if (dossier.status === 'PENDING' || dossier.status === 'IN_PROGRESS') pending += 1
      if (dossier.status === 'APPROVED' || dossier.status === 'COMPLETED') done += 1
      if (hasResponse(dossier) && !dossier.response_read) unread += 1
    }
    return { items, status, total: items.length, pending, done, unread, reload, markRead, markAllRead }
  }, [items, status, reload, markRead, markAllRead])

  return <DossiersContext.Provider value={value}>{children}</DossiersContext.Provider>
}

export default DossiersProvider
