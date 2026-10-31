import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import fr from './fr.json'
import en from './en.json'
import mg from './mg.json'
import frCatalog from './fr.catalog.json'
import enCatalog from './en.catalog.json'
import mgCatalog from './mg.catalog.json'
import frPublic from './fr.public.json'
import enPublic from './en.public.json'
import mgPublic from './mg.public.json'
import frDash from './fr.dash.json'
import enDash from './en.dash.json'
import mgDash from './mg.dash.json'

export const SUPPORTED_LANGUAGES = ['fr', 'en', 'mg'] as const
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]

const STORAGE_KEY = 'mairy-project-lang'
const DEFAULT_LANGUAGE: SupportedLanguage = 'fr'

function isSupported(value: string | null): value is SupportedLanguage {
  return value !== null && (SUPPORTED_LANGUAGES as readonly string[]).includes(value)
}

/** Langue mémorisée par le visiteur (français par défaut). */
function readStoredLanguage(): SupportedLanguage {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (isSupported(stored)) return stored
  } catch {
    // stockage indisponible (navigation privée, etc.) : on garde le défaut
  }
  return DEFAULT_LANGUAGE
}

void i18n.use(initReactI18next).init({
  resources: {
    // Chaque langue fusionne ses fichiers : socle, catalogue des services,
    // site public et espace utilisateur (clés de premier niveau distinctes).
    fr: { translation: { ...fr, ...frCatalog, ...frPublic, ...frDash } },
    en: { translation: { ...en, ...enCatalog, ...enPublic, ...enDash } },
    mg: { translation: { ...mg, ...mgCatalog, ...mgPublic, ...mgDash } },
  },
  lng: readStoredLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  interpolation: {
    escapeValue: false, // React échappe déjà le contenu
  },
})

// Garde <html lang> à jour (lecteurs d'écran, césure) et mémorise le choix.
i18n.on('languageChanged', (language: string) => {
  document.documentElement.lang = language
  try {
    window.localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // ignoré : la langue restera valable pour la session en cours
  }
})
document.documentElement.lang = i18n.language || DEFAULT_LANGUAGE

export default i18n
