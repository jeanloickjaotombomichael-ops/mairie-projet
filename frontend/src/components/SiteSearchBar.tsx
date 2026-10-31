import { useId, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { Search } from 'lucide-react'
import { ScanIcon } from '@/components/icons'
import { useDismiss } from '@/hooks/useDismiss'
import { buildSiteEntries, searchSiteEntries, type SiteSearchEntry } from '@/lib/siteSearch'
import { cn } from '@/lib/utils'

/**
 * Barre de recherche de l'accueil : cherche uniquement dans les informations de
 * la plateforme (services, pages). La loupe lance la recherche, l'icône de
 * scanner ouvre directement la page de scan.
 */
function SiteSearchBar() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const listId = useId()

  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const rootRef = useRef<HTMLFormElement>(null)

  const entries = useMemo(() => buildSiteEntries(t), [t])
  const results = useMemo(() => searchSiteEntries(entries, query), [entries, query])

  useDismiss(rootRef, open, () => setOpen(false))

  const go = (entry: SiteSearchEntry) => {
    setOpen(false)
    setQuery('')
    navigate(entry.path)
  }

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!query.trim()) return
    const entry = results[active] ?? results[0]
    if (entry) {
      go(entry)
    } else {
      setOpen(true) // affiche « Aucun résultat »
    }
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setActive((index) => Math.min(index + 1, Math.max(results.length - 1, 0)))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((index) => Math.max(index - 1, 0))
    }
  }

  const showList = open && query.trim() !== ''

  return (
    <form
      ref={rootRef}
      role="search"
      onSubmit={onSubmit}
      className="relative mx-auto mt-8 w-full max-w-md text-left"
    >
      <div className="flex items-center gap-1 rounded-full border border-white/20 bg-white/10 py-1.5 pl-1.5 pr-1.5 shadow-sm backdrop-blur-sm transition-colors focus-within:border-white/50">
        <button
          type="submit"
          aria-label={t('search.submit')}
          title={t('search.submit')}
          className="inline-flex size-9 shrink-0 items-center justify-center rounded-full text-white/70 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
        >
          <Search className="size-4" aria-hidden="true" />
        </button>

        <input
          type="search"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-label={t('search.label')}
          aria-activedescendant={showList && results[active] ? `${listId}-${active}` : undefined}
          placeholder={t('home.searchPlaceholder')}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setActive(0)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className="min-w-0 flex-1 bg-transparent px-1 text-sm text-white placeholder:text-white/50 focus:outline-none"
        />

        <Link
          to="/scanner"
          aria-label={t('search.scan')}
          title={t('search.scan')}
          className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-colors hover:bg-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
        >
          <ScanIcon className="size-[18px]" />
        </Link>
      </div>

      {showList && (
        <ul
          id={listId}
          role="listbox"
          aria-label={t('search.resultsLabel')}
          className="absolute left-0 right-0 z-30 mt-2 max-h-72 overflow-y-auto rounded-xl border border-white/10 bg-[#0a0a0a]/95 py-1 shadow-2xl backdrop-blur"
        >
          {results.length === 0 ? (
            <li className="px-4 py-3 text-sm text-white/60">{t('search.noResults', { query: query.trim() })}</li>
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
                className={cn(
                  'flex cursor-pointer items-center justify-between gap-3 px-4 py-2.5 text-sm text-white/85',
                  index === active && 'bg-white/10 text-white',
                )}
              >
                <span className="min-w-0 truncate">{entry.title}</span>
                <span className="shrink-0 text-[11px] uppercase tracking-wide text-white/45">
                  {entry.group === 'service' ? t('search.groupService') : t('search.groupPage')}
                </span>
              </li>
            ))
          )}
        </ul>
      )}
    </form>
  )
}

export default SiteSearchBar
