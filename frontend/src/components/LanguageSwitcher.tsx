import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Globe } from 'lucide-react'
import { cn } from '@/lib/utils'

const LANGUAGES = [
  { code: 'fr', label: 'FR', name: 'Français' },
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'mg', label: 'MLG', name: 'Malagasy' },
] as const

interface LanguageSwitcherProps {
  /** Classes ajoutées au bouton (couleurs, bordure…). */
  buttonClassName?: string
  /** Classes ajoutées au menu déroulant (fond, bordure…). */
  menuClassName?: string
  /** Classes ajoutées à chaque option. */
  itemClassName?: string
  /** Classe de l'option active. */
  activeItemClassName?: string
  /** Menu aligné à droite (défaut) ou à gauche du bouton. */
  align?: 'left' | 'right'
  /** Affiche uniquement l'icône (sans le code de langue). */
  iconOnly?: boolean
}

/** Sélecteur de langue FR / EN / MLG : le changement est immédiat, sans rechargement. */
function LanguageSwitcher({
  buttonClassName,
  menuClassName,
  itemClassName,
  activeItemClassName = 'text-primary',
  align = 'right',
  iconOnly = false,
}: LanguageSwitcherProps) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  const current = LANGUAGES.find((l) => l.code === i18n.language) ?? LANGUAGES[0]

  useEffect(() => {
    if (!open) return

    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const choose = (code: string) => {
    void i18n.changeLanguage(code)
    setOpen(false)
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={t('header.language')}
        className={cn(
          'flex items-center gap-1.5 rounded-lg border border-white/15 px-3 py-1.5 text-xs font-semibold text-white/80 transition-colors hover:border-white/30 hover:text-white',
          buttonClassName,
        )}
      >
        <Globe className="size-3.5" aria-hidden="true" />
        {!iconOnly && current.label}
      </button>

      {open && (
        <div
          role="listbox"
          aria-label={t('header.language')}
          className={cn(
            'absolute z-50 mt-2 w-36 overflow-hidden rounded-lg border border-white/10 bg-[#0a0a0a] shadow-xl',
            align === 'right' ? 'right-0' : 'left-0',
            menuClassName,
          )}
        >
          {LANGUAGES.map((language) => (
            <button
              key={language.code}
              type="button"
              role="option"
              aria-selected={i18n.language === language.code}
              onClick={() => choose(language.code)}
              className={cn(
                'flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-xs font-medium text-white/80 transition-colors hover:bg-white/10',
                itemClassName,
                i18n.language === language.code && activeItemClassName,
              )}
            >
              <span>{language.name}</span>
              <span className="text-[10px] opacity-70">{language.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default LanguageSwitcher
