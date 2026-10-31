import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { THEME_IDS, type ThemeId } from '@/dashboard/theme'
import { CheckIcon, SunIcon } from '@/dashboard/icons'
import { useDismiss } from '@/hooks/useDismiss'
import { cn } from '@/lib/utils'

/** Couleur d'aperçu de chaque apparence dans le menu. */
const SWATCH: Record<ThemeId, string> = {
  nuit: '#2aa9ff',
  clair: '#f1f4fa',
  ocean: '#22d3ee',
  foret: '#34d399',
  crepuscule: '#a78bfa',
}

interface ThemeMenuProps {
  theme: ThemeId
  onChange: (theme: ThemeId) => void
}

/** Icône soleil : choix parmi les cinq apparences de l'espace personnel. */
function ThemeMenu({ theme, onChange }: ThemeMenuProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useDismiss(rootRef, open, () => setOpen(false))

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t('dash.topbar.appearance')}
        title={t('dash.topbar.appearance')}
        className="d-icon-btn"
      >
        <SunIcon className="size-5" />
      </button>

      {open && (
        <div
          role="menu"
          aria-label={t('dash.topbar.appearance')}
          className="d-popover absolute right-0 z-50 mt-2 w-48 overflow-hidden py-1"
        >
          {THEME_IDS.map((id) => (
            <button
              key={id}
              type="button"
              role="menuitemradio"
              aria-checked={theme === id}
              onClick={() => {
                onChange(id)
                setOpen(false)
              }}
              className={cn('d-menu-item', theme === id && 'd-menu-item-active')}
            >
              <span className="flex items-center gap-2.5">
                <span
                  aria-hidden="true"
                  className="inline-block size-3.5 rounded-full border border-white/30"
                  style={{ backgroundColor: SWATCH[id] }}
                />
                {t(`dash.themes.${id}`)}
              </span>
              {theme === id && <CheckIcon className="size-4" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default ThemeMenu
