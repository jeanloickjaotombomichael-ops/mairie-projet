import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import BackLink from '@/components/BackLink'
import { ESPACE_HOME, typeToSlug, isDossierType } from '@/data/catalog'
import DocumentDownloads from '@/dashboard/DocumentDownloads'
import StatusBadge from '@/dashboard/StatusBadge'
import { useDossiers } from '@/dashboard/dossiersContext'
import { CheckIcon, InboxIcon, SpinnerIcon } from '@/dashboard/icons'
import { formatDate, formatDateTime } from '@/lib/format'
import type { DossierSummary } from '@/lib/espaceApi'

function hasResponse(dossier: DossierSummary): boolean {
  return dossier.response_message.trim() !== ''
}

/** Notifications : les réponses de la Commune, puis la liste de toutes les demandes envoyées. */
function NotificationsPage() {
  const { t, i18n } = useTranslation()
  const { items, status, unread, reload, markRead, markAllRead } = useDossiers()

  const typeTitle = (dossier: DossierSummary): string =>
    isDossierType(dossier.dossier_type) && typeToSlug(dossier.dossier_type)
      ? t(`catalog.types.${dossier.dossier_type}.title`)
      : dossier.dossier_type

  // Réponses non lues d'abord, puis les plus récentes.
  const responses = useMemo(
    () =>
      items
        .filter(hasResponse)
        .sort(
          (a, b) =>
            Number(a.response_read) - Number(b.response_read) ||
            new Date(b.responded_at ?? 0).getTime() - new Date(a.responded_at ?? 0).getTime(),
        ),
    [items],
  )

  if (status === 'loading' && items.length === 0) {
    return (
      <div className="d-page-muted mx-auto flex max-w-4xl items-center gap-3 py-10 text-sm" role="status">
        <SpinnerIcon className="size-5 animate-spin" />
        {t('dash.notifications.loading')}
      </div>
    )
  }

  if (status === 'error' && items.length === 0) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <p role="alert" className="d-notice d-notice-error">
          {t('dash.notifications.loadError')}
        </p>
        <button type="button" className="d-btn-ghost" onClick={() => void reload()}>
          {t('dash.notifications.retry')}
        </button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <BackLink fallback={ESPACE_HOME} variant="space" />
      <header>
        <h1 className="d-page-heading text-xl font-bold">{t('dash.notifications.title')}</h1>
        <p className="d-page-muted mt-1 text-sm">{t('dash.notifications.intro')}</p>
      </header>

      <section className="space-y-3" aria-labelledby="responses-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="responses-title" className="d-page-heading text-base font-bold">
            {t('dash.notifications.responsesTitle')}
          </h2>
          {unread > 0 && (
            <button type="button" className="d-btn-ghost" onClick={() => void markAllRead()}>
              <CheckIcon className="size-4" />
              {t('dash.notifications.markAllRead')}
            </button>
          )}
        </div>

        {responses.length === 0 ? (
          <div className="d-card d-muted flex items-center gap-3 p-5 text-sm">
            <InboxIcon className="size-5 shrink-0" />
            <p>{t('dash.notifications.empty')}</p>
          </div>
        ) : (
          <ul className="space-y-3">
            {responses.map((dossier) => {
              const isUnread = !dossier.response_read
              return (
                <li key={dossier.id} className="d-card p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="d-heading flex items-center gap-2 text-sm font-bold">
                        {isUnread && <span className="d-dot" aria-hidden="true" />}
                        {typeTitle(dossier)}
                        {isUnread && (
                          <span className="d-badge d-badge-progress">{t('dash.notifications.newBadge')}</span>
                        )}
                      </p>
                      <p className="d-muted mt-1 text-xs">
                        {t('dash.notifications.reference')} {dossier.reference} ·{' '}
                        {t('dash.notifications.respondedOn')} {formatDateTime(dossier.responded_at, i18n.language)}
                      </p>
                    </div>
                    <StatusBadge status={dossier.status} />
                  </div>

                  <div className="d-divider mt-4 border-t pt-4">
                    <p className="d-muted text-xs font-semibold uppercase tracking-wider">
                      {t('dash.notifications.response')}
                    </p>
                    <p className="d-heading mt-1.5 whitespace-pre-line text-sm leading-relaxed">
                      {dossier.response_message}
                    </p>
                    <DocumentDownloads dossierId={dossier.id} documents={dossier.documents} />
                  </div>

                  {isUnread && (
                    <button
                      type="button"
                      className="d-btn-ghost mt-4"
                      onClick={() => void markRead(dossier.id)}
                    >
                      {t('dash.notifications.markRead')}
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <section className="space-y-3" aria-labelledby="requests-title">
        <h2 id="requests-title" className="d-page-heading text-base font-bold">
          {t('dash.notifications.requestsTitle')}
        </h2>

        {items.length === 0 ? (
          <div className="d-card d-muted p-5 text-sm">{t('dash.notifications.noRequests')}</div>
        ) : (
          <ul className="d-card divide-y divide-[var(--d-border)] overflow-hidden">
            {items.map((dossier) => (
              <li key={dossier.id} className="px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="d-heading text-sm font-semibold">{typeTitle(dossier)}</p>
                    <p className="d-muted mt-0.5 text-xs">
                      {dossier.reference} · {t('dash.notifications.sentOn')}{' '}
                      {formatDate(dossier.created_at, i18n.language)}
                      {dossier.guichet && ` · ${t('dash.notifications.guichet')} ${dossier.guichet}`}
                    </p>
                  </div>
                  <StatusBadge status={dossier.status} />
                </div>
                <DocumentDownloads dossierId={dossier.id} documents={dossier.documents} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

export default NotificationsPage
