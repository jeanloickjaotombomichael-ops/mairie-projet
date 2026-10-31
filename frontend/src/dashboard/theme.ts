import { useCallback, useState } from 'react'

/** Les cinq apparences proposées par l'icône soleil de la barre supérieure. */
export const THEME_IDS = ['nuit', 'clair', 'ocean', 'foret', 'crepuscule'] as const
export type ThemeId = (typeof THEME_IDS)[number]

export const DEFAULT_THEME: ThemeId = 'nuit'

const STORAGE_KEY = 'mairy-project-dash-theme'

function isThemeId(value: string | null): value is ThemeId {
  return value !== null && (THEME_IDS as readonly string[]).includes(value)
}

/** Apparence mémorisée par l'utilisateur (nuit par défaut). */
function readStoredTheme(): ThemeId {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (isThemeId(stored)) return stored
  } catch {
    // stockage indisponible (navigation privée, etc.) : on garde le défaut
  }
  return DEFAULT_THEME
}

/** État de l'apparence, mémorisé dans le navigateur de l'utilisateur. */
export function useDashboardTheme(): readonly [ThemeId, (theme: ThemeId) => void] {
  const [theme, setThemeState] = useState<ThemeId>(readStoredTheme)

  const setTheme = useCallback((next: ThemeId) => {
    setThemeState(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // ignoré : le choix reste valable pour la session en cours
    }
  }, [])

  return [theme, setTheme] as const
}
