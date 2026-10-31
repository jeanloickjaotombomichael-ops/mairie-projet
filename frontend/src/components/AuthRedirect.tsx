import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useUser } from '@clerk/react'
import { ESPACE_HOME } from '@/data/catalog'
import { consumeReturnTo } from '@/lib/returnTo'

/** Dernière connexion déjà traitée (évite de rediriger à chaque rechargement de page). */
const HANDLED_KEY = 'mairy-project-login-handled'

/** Une connexion est « récente » si elle date de moins de ce délai (marge pour l'écart d'horloge). */
const FRESH_LOGIN_MS = 10 * 60 * 1000

function readHandled(): string | null {
  try {
    return window.localStorage.getItem(HANDLED_KEY)
  } catch {
    return null
  }
}

function writeHandled(value: string): void {
  try {
    window.localStorage.setItem(HANDLED_KEY, value)
  } catch {
    // stockage indisponible : au pire, la redirection est refaite au prochain chargement
  }
}

/**
 * Envoie l'usager vers son espace personnel dès qu'il vient de se connecter ou de
 * s'inscrire. Fonctionne aussi quand la connexion recharge la page (Google, etc.),
 * car elle repose sur l'heure de dernière connexion du compte et non sur l'état
 * en mémoire. Une session ancienne rouverte plus tard ne provoque aucune redirection.
 */
function AuthRedirect() {
  const { isLoaded, isSignedIn, user } = useUser()
  const navigate = useNavigate()

  useEffect(() => {
    if (!isLoaded || !isSignedIn || !user) return

    const loginAt = (user.lastSignInAt ?? user.createdAt)?.getTime()
    if (!loginAt) return

    const stamp = String(loginAt)
    if (readHandled() === stamp) return
    writeHandled(stamp)

    if (Math.abs(Date.now() - loginAt) > FRESH_LOGIN_MS) return

    navigate(consumeReturnTo() ?? ESPACE_HOME, { replace: true })
  }, [isLoaded, isSignedIn, user, navigate])

  return null
}

export default AuthRedirect
