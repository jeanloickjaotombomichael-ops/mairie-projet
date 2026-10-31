import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth, useUser } from '@clerk/react'
import BackLink from '@/components/BackLink'
import { ESPACE_HOME } from '@/data/catalog'
import { useMails } from '@/dashboard/espaceContext'
import { ArrowLeftIcon, CloseIcon, InboxIcon, MailIcon, ReplyIcon, SendIcon, SpinnerIcon } from '@/dashboard/icons'
import { ApiError } from '@/lib/api'
import { sendMail, type CitizenMail } from '@/lib/espaceApi'
import { formatDateTime } from '@/lib/format'

type Folder = 'inbox' | 'sent'

interface ComposeState {
  service: string
  subject: string
  body: string
}

const EMPTY_COMPOSE: ComposeState = { service: '', subject: '', body: '' }

/** Date courte façon Gmail : l'heure aujourd'hui, sinon le jour et le mois. */
function shortDate(iso: string, language: string): string {
  const date = new Date(iso)
  const today = new Date()
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString(language, { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString(language, {
    day: 'numeric',
    month: 'short',
    ...(date.getFullYear() !== today.getFullYear() ? { year: 'numeric' } : {}),
  })
}

/** Mail : l'usager écrit à un guichet ou à l'administration et lit les réponses des agents. */
function MailPage() {
  const { t, i18n } = useTranslation()
  const { getToken } = useAuth()
  const { user } = useUser()
  const { items, services, status, unread, reload, markRead, add } = useMails()
  const [params, setParams] = useSearchParams()
  const [folder, setFolder] = useState<Folder>('inbox')
  const [openedId, setOpenedId] = useState<number | null>(null)
  const [compose, setCompose] = useState<ComposeState | null>(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  // « ?nouveau=1 » (lien de l'assistant) ouvre directement la fenêtre de rédaction.
  useEffect(() => {
    if (params.get('nouveau')) {
      setCompose(EMPTY_COMPOSE)
      setParams({}, { replace: true })
    }
  }, [params, setParams])

  const shown = useMemo(() => items.filter((mail) => mail.folder === folder), [items, folder])
  const opened = items.find((mail) => mail.id === openedId) ?? null

  const open = (mail: CitizenMail) => {
    setOpenedId(mail.id)
    if (mail.folder === 'inbox' && !mail.is_read) void markRead(mail.id)
  }

  const reply = (mail: CitizenMail) => {
    const subject = /^re\s*:/i.test(mail.subject) ? mail.subject : `Re: ${mail.subject}`
    setCompose({ service: mail.service, subject, body: '' })
    setError('')
  }

  const onSend = async (event: FormEvent) => {
    event.preventDefault()
    if (!compose) return
    setSending(true)
    setError('')
    try {
      const sent = await sendMail(getToken, {
        ...compose,
        sender_name: user?.fullName ?? '',
        sender_email: user?.primaryEmailAddress?.emailAddress ?? '',
      })
      add(sent)
      setCompose(null)
      setNotice(t('dash.mail.sent'))
      window.setTimeout(() => setNotice(''), 6000)
    } catch (caught) {
      const kind = caught instanceof ApiError ? caught.kind : 'server'
      setError(t(`dash.form.errors.${kind === 'validation' ? 'global' : kind}`, t('dash.form.errors.server')))
    } finally {
      setSending(false)
    }
  }

  const tabs: { value: Folder; label: string; count: number }[] = [
    { value: 'inbox', label: t('dash.mail.inbox'), count: unread },
    { value: 'sent', label: t('dash.mail.sentFolder'), count: 0 },
  ]

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <BackLink fallback={ESPACE_HOME} variant="space" />
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="d-page-heading text-xl font-bold">{t('dash.sidebar.mail')}</h1>
          <p className="d-page-muted mt-1 text-sm">{t('dash.mail.intro')}</p>
        </div>
        <button
          type="button"
          className="d-mail-compose-btn"
          onClick={() => {
            setCompose(EMPTY_COMPOSE)
            setError('')
          }}
        >
          <MailIcon className="size-5" />
          {t('dash.mail.new')}
        </button>
      </header>

      {notice && (
        <p role="status" className="d-notice d-notice-success">
          {notice}
        </p>
      )}

      <section className="d-card overflow-hidden">
        <div className="d-mail-tabs" role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.value}
              type="button"
              role="tab"
              aria-selected={folder === tab.value}
              className={`d-mail-tab${folder === tab.value ? ' is-active' : ''}`}
              onClick={() => {
                setFolder(tab.value)
                setOpenedId(null)
              }}
            >
              {tab.value === 'inbox' ? <InboxIcon className="size-4" /> : <SendIcon className="size-4" />}
              {tab.label}
              {tab.count > 0 && <span className="d-mail-count">{tab.count}</span>}
            </button>
          ))}
        </div>

        {opened ? (
          <article className="p-5 sm:p-7">
            <button type="button" className="d-btn-ghost mb-5" onClick={() => setOpenedId(null)}>
              <ArrowLeftIcon className="size-4" />
              {t('dash.mail.back')}
            </button>
            <h2 className="d-heading text-xl font-semibold">{opened.subject || t('dash.mail.noSubject')}</h2>
            <div className="mt-4 flex flex-wrap items-start gap-3">
              <span className="d-mail-avatar">{(opened.folder === 'inbox' ? opened.sender_name : user?.fullName ?? '?').charAt(0).toUpperCase()}</span>
              <div className="min-w-0 flex-1 text-sm">
                <p className="d-heading font-semibold">
                  {opened.folder === 'inbox' ? opened.sender_name : t('dash.mail.me')}
                </p>
                <p className="d-muted">
                  {opened.folder === 'inbox'
                    ? t('dash.mail.fromService', { service: opened.service_label })
                    : t('dash.mail.toService', { service: opened.service_label })}
                </p>
              </div>
              <span className="d-muted text-xs">{formatDateTime(opened.created_at, i18n.language)}</span>
            </div>
            <div className="d-heading mt-6 whitespace-pre-line break-words text-sm leading-relaxed">{opened.body}</div>
            <button type="button" className="d-btn-ghost mt-7" onClick={() => reply(opened)}>
              <ReplyIcon className="size-4" />
              {opened.folder === 'inbox' ? t('dash.mail.reply') : t('dash.mail.writeAgain')}
            </button>
          </article>
        ) : status === 'loading' && items.length === 0 ? (
          <p className="d-muted flex items-center gap-3 p-6 text-sm" role="status">
            <SpinnerIcon className="size-5 animate-spin" />
            {t('dash.notifications.loading')}
          </p>
        ) : status === 'error' && items.length === 0 ? (
          <div className="space-y-3 p-6">
            <p role="alert" className="d-notice d-notice-error">
              {t('dash.mail.loadError')}
            </p>
            <button type="button" className="d-btn-ghost" onClick={() => void reload()}>
              {t('dash.notifications.retry')}
            </button>
          </div>
        ) : shown.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <p className="d-heading text-lg">
              {folder === 'inbox' ? t('dash.mail.emptyInbox') : t('dash.mail.emptySent')}
            </p>
            <p className="d-muted mx-auto mt-2 max-w-md text-sm">{t('dash.mail.emptyHint')}</p>
          </div>
        ) : (
          <ul>
            {shown.map((mail) => {
              const unreadRow = mail.folder === 'inbox' && !mail.is_read
              return (
                <li key={mail.id}>
                  <button
                    type="button"
                    className={`d-mail-row${unreadRow ? ' is-unread' : ''}`}
                    onClick={() => open(mail)}
                  >
                    <span className="d-mail-from">
                      {mail.folder === 'inbox' ? mail.sender_name : t('dash.mail.toShort', { service: mail.service_label })}
                    </span>
                    <span className="d-mail-line">
                      <span className="d-mail-subject">{mail.subject || t('dash.mail.noSubject')}</span>
                      <span className="d-muted"> — {mail.body}</span>
                    </span>
                    <span className="d-mail-date">{shortDate(mail.created_at, i18n.language)}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {compose && (
        <section className="d-compose d-popover" role="dialog" aria-label={t('dash.mail.new')}>
          <header className="d-compose-head">
            <span className="min-w-0 flex-1 truncate">{compose.subject || t('dash.mail.new')}</span>
            <button type="button" className="d-icon-btn !size-8" onClick={() => setCompose(null)} aria-label={t('dash.sidebar.close')}>
              <CloseIcon className="size-4" />
            </button>
          </header>
          <form onSubmit={(event) => void onSend(event)}>
            <label className="d-compose-field">
              <span className="d-muted">{t('dash.mail.to')}</span>
              <select
                required
                value={compose.service}
                onChange={(event) => setCompose({ ...compose, service: event.target.value })}
              >
                <option value="">{t('dash.form.select')}</option>
                {services.map((service) => (
                  <option key={service.value} value={service.value}>
                    {service.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="d-compose-field">
              <span className="sr-only">{t('dash.mail.subject')}</span>
              <input
                required
                maxLength={255}
                placeholder={t('dash.mail.subject')}
                value={compose.subject}
                onChange={(event) => setCompose({ ...compose, subject: event.target.value })}
              />
            </label>
            <label className="sr-only" htmlFor="d-compose-body">
              {t('dash.mail.body')}
            </label>
            <textarea
              id="d-compose-body"
              required
              maxLength={5000}
              rows={10}
              className="d-compose-body"
              value={compose.body}
              onChange={(event) => setCompose({ ...compose, body: event.target.value })}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                  event.currentTarget.form?.requestSubmit()
                }
              }}
            />
            {error && (
              <p role="alert" className="d-error px-4">
                {error}
              </p>
            )}
            <footer className="d-compose-foot">
              <button type="submit" className="d-btn !rounded-full !px-6" disabled={sending}>
                {sending ? <SpinnerIcon className="size-4 animate-spin" /> : <SendIcon className="size-4" />}
                {t('dash.mail.send')}
              </button>
              <span className="d-muted text-xs">{t('dash.mail.repliesHere')}</span>
            </footer>
          </form>
        </section>
      )}
    </div>
  )
}

export default MailPage
