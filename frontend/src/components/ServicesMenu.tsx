import { useCallback, useRef, useState, type FocusEvent, type PointerEvent } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { CIVIL_SLUGS, SERVICE_SLUGS, publicPath, slugToType } from '@/data/catalog'
import { ChevronDownIcon, ChevronRightIcon } from '@/components/icons'
import { useDismiss } from '@/hooks/useDismiss'
import { cn } from '@/lib/utils'

const itemClass =
  'flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm text-white/80 transition-colors hover:bg-white/10 hover:text-white focus-visible:bg-white/10 focus-visible:text-white focus-visible:outline-none'

const panelClass = 'rounded-xl border border-white/10 bg-[#0a0a0a] p-1.5 shadow-2xl'

/**
 * Menu « Services » de l'en-tête (ordinateur et tablette).
 * S'ouvre au survol de la souris ou au clic ; « État civil » ouvre un second
 * menu (naissance, mariage, décès, législation, actes divers) au survol.
 */
function ServicesMenu() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [civilOpen, setCivilOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  // Un appui tactile ne « survole » pas : le clic doit alors ouvrir/fermer le menu.
  const lastPointer = useRef<'mouse' | 'other'>('other')

  const close = useCallback(() => {
    setOpen(false)
    setCivilOpen(false)
  }, [])

  useDismiss(rootRef, open, close)

  const onTriggerPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    lastPointer.current = event.pointerType === 'mouse' ? 'mouse' : 'other'
  }

  const onTriggerClick = () => {
    if (lastPointer.current === 'mouse') {
      setOpen(true)
    } else {
      setOpen((value) => !value)
    }
    lastPointer.current = 'other'
  }

  // Ferme le menu quand le focus clavier en sort.
  const onBlur = (event: FocusEvent<HTMLDivElement>) => {
    const next = event.relatedTarget as Node | null
    if (next && rootRef.current && !rootRef.current.contains(next)) close()
  }

  return (
    <div
      ref={rootRef}
      className="relative"
      onPointerEnter={(event) => {
        if (event.pointerType === 'mouse') setOpen(true)
      }}
      onPointerLeave={(event) => {
        if (event.pointerType === 'mouse') close()
      }}
      onBlur={onBlur}
    >
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onPointerDown={onTriggerPointerDown}
        onClick={onTriggerClick}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown') {
            event.preventDefault()
            setOpen(true)
          }
        }}
        className={cn(
          'flex items-center gap-1 text-sm font-medium transition-colors hover:text-white',
          open ? 'text-white' : 'text-white/70',
        )}
      >
        {t('header.nav.services')}
        <ChevronDownIcon className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        // `pt-2` (et non une marge) : le pointeur reste dans la zone du menu en descendant.
        <div className="absolute left-0 top-full z-50 w-64 pt-2">
          <ul role="menu" aria-label={t('nav.servicesMenu')} className={panelClass}>
            <li role="none">
              <Link role="menuitem" to="/services" onClick={close} className={cn(itemClass, 'font-semibold text-white')}>
                {t('catalog.backToServices')}
              </Link>
            </li>
            <li role="separator" className="my-1 h-px bg-white/10" />

            {SERVICE_SLUGS.map((slug) => {
              const type = slugToType(slug)
              return (
                <li key={slug} role="none">
                  <Link role="menuitem" to={publicPath(type)} onClick={close} className={itemClass}>
                    {t(`catalog.types.${type}.title`)}
                  </Link>
                </li>
              )
            })}

            <li
              role="none"
              className="relative"
              onPointerEnter={(event) => {
                if (event.pointerType === 'mouse') setCivilOpen(true)
              }}
              onPointerLeave={(event) => {
                if (event.pointerType === 'mouse') setCivilOpen(false)
              }}
            >
              <Link
                role="menuitem"
                to="/services/etat-civil"
                aria-haspopup="menu"
                aria-expanded={civilOpen}
                onClick={close}
                onFocus={() => setCivilOpen(true)}
                className={itemClass}
              >
                {t('catalog.civil.title')}
                <ChevronRightIcon className="size-3.5 shrink-0" />
              </Link>

              {civilOpen && (
                <div className="absolute left-full top-0 z-50 w-56 pl-2">
                  <ul role="menu" aria-label={t('nav.civilMenu')} className={panelClass}>
                    {CIVIL_SLUGS.map((slug) => {
                      const type = slugToType(slug)
                      return (
                        <li key={slug} role="none">
                          <Link role="menuitem" to={publicPath(type)} onClick={close} className={itemClass}>
                            {t(`catalog.types.${type}.title`)}
                          </Link>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )}
            </li>
          </ul>
        </div>
      )}
    </div>
  )
}

export default ServicesMenu
