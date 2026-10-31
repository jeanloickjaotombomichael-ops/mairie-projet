import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { requestPath, type DossierType } from '@/data/catalog'
import { DOSSIER_ICONS } from '@/dashboard/dossierIcons'
import { ChevronLeftIcon, ChevronRightIcon } from '@/dashboard/icons'
import { useScrollRow } from '@/hooks/useScrollRow'

interface RequestRowProps {
  id: string
  title: string
  types: readonly DossierType[]
}

/** Rangée défilante de demandes, avec flèches gauche / droite ; chaque carte ouvre son formulaire. */
function RequestRow({ id, title, types }: RequestRowProps) {
  const { t } = useTranslation()
  const { trackRef, canPrev, canNext, scroll } = useScrollRow<HTMLUListElement>()

  const headingId = `${id}-title`

  return (
    <section aria-labelledby={headingId}>
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 id={headingId} className="d-page-heading text-xl font-bold">
          {title}
        </h2>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => scroll(-1)}
            disabled={!canPrev}
            aria-label={t('dash.home.prev')}
            aria-controls={id}
            className="d-row-arrow"
          >
            <ChevronLeftIcon className="size-5" />
          </button>
          <button
            type="button"
            onClick={() => scroll(1)}
            disabled={!canNext}
            aria-label={t('dash.home.next')}
            aria-controls={id}
            className="d-row-arrow"
          >
            <ChevronRightIcon className="size-5" />
          </button>
        </div>
      </div>

      <ul id={id} ref={trackRef} className="d-row-track">
        {types.map((type) => {
          const Icon = DOSSIER_ICONS[type]
          return (
            <li key={type} className="d-row-item">
              <Link to={requestPath(type)} className="d-request-card group">
                <span className="d-request-icon" aria-hidden="true">
                  <Icon className="size-5" strokeWidth={1.8} />
                </span>
                <h3 className="d-request-title mt-4 text-lg font-bold">{t(`catalog.types.${type}.title`)}</h3>
                <p className="d-request-text mt-1.5 line-clamp-3 flex-1 text-sm leading-relaxed">
                  {t(`catalog.types.${type}.description`)}
                </p>
                <span className="d-request-cta">
                  {t('dash.home.cta')}
                  <ChevronRightIcon className="size-3.5 transition-transform group-hover:translate-x-0.5" />
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export default RequestRow
