import { useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { buildNavEntries, type NavEntry } from '@/dashboard/navEntries'
import { SearchIcon } from '@/dashboard/icons'
import { useDismiss } from '@/hooks/useDismiss'
import { matchesQuery, normalizeText } from '@/lib/siteSearch'
import { cn } from '@/lib/utils'

const MAX_RESULTS = 8

/** Barre de recherche de l'espace : ne cherche que parmi les pages de l'espace (demandes, notifications). */
function DashSearch() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const listId = useId()

  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)

  const entries = useMemo(() => buildNavEntries(t), [t])

  const results = useMemo<NavEntry[]>(() => {
    const needle = normalizeText(query)
    if (!needle) return []
    const matches = entries.filter((entry) => matchesQuery(`${entry.label} ${entry.hint}`, query))
    const inLabel = (entry: NavEntry) => (normalizeText(entry.label).includes(needle) ? 0 : 1)
    return [...matches].sort((a, b) => inLabel(a) - inLabel(b)).slice(0, MAX_RESULTS)
  }, [entries, query])

  useDismiss(rootRef, open, () => setOpen(false))

  const go = (entry: NavEntry) => {
    setOpen(false)
    setQuery('')
    navigate(entry.path)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setActive((index) => Math.min(index + 1, Math.max(results.length - 1, 0)))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((index) => Math.max(index - 1, 0))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      const entry = results[active] ?? results[0]
      if (entry) go(entry)
    }
  }

  const showList = open && query.trim() !== ''

  return (
    <div ref={rootRef} className="relative min-w-0 flex-1 sm:max-w-sm md:max-w-md">
      <SearchIcon className="d-muted pointer-events-none absolute left-3 top-1/2 size-[18px] -translate-y-1/2" />
      <input
        type="search"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-label={t('dash.topbar.searchLabel')}
        aria-activedescendant={showList && results[active] ? `${listId}-${active}` : undefined}
        placeholder={t('dash.topbar.searchPlaceholder')}
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setActive(0)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        className="d-input"
        style={{ paddingLeft: '2.5rem' }}
      />

      {showList && (
        <ul
          id={listId}
          role="listbox"
          aria-label={t('dash.topbar.searchLabel')}
          className="d-popover absolute left-0 right-0 z-50 mt-2 max-h-80 overflow-y-auto py-1"
        >
          {results.length === 0 ? (
            <li className="d-muted px-3 py-2.5 text-sm">{t('dash.topbar.noResults')}</li>
          ) : (
            results.map((entry, index) => (
              <li
                key={entry.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === active}
                onMouseEnter={() => setActive(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => go(entry)}
                className={cn('d-menu-item cursor-pointer', index === active && 'bg-[var(--d-surface-2)]')}
              >
                <span className="min-w-0 truncate">{entry.label}</span>
                <span className="d-muted shrink-0 text-xs">{entry.hint}</span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  )
}

export default DashSearch
