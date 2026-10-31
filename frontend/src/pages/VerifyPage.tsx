import { useEffect, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import Backdrop from '@/components/Backdrop'
import {
  CheckIcon,
  CrossIcon,
  DownloadIcon,
  SpinnerIcon,
  WarningIcon,
} from '@/components/icons'
import { ApiError, verifyDocument, type VerifyResponse, type VerifiedDocument } from '@/lib/api'
import { actionClass } from '@/lib/ui'
import { cn } from '@/lib/utils'
import { isUuid } from '@/lib/uuid'

type ViewState =
  | { kind: 'loading' }
  | { kind: 'result'; data: VerifyResponse }
  | { kind: 'not_found' }
  | { kind: 'error' }

type Tone = 'success' | 'warning' | 'danger'

const TONE_BADGE: Record<Tone, string> = {
  success: 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300',
  warning: 'border-amber-500/30 bg-amber-500/15 text-amber-300',
  danger: 'border-red-500/30 bg-red-500/15 text-red-300',
}

function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-bold uppercase tracking-wide',
        TONE_BADGE[tone],
      )}
    >
      {children}
    </span>
  )
}

function SubCheck({ ok, label, okText, koText }: { ok: boolean; label: string; okText: string; koText: string }) {
  return (
    <div
      className={cn(
        'flex-1 rounded-lg border px-3 py-2.5 text-xs font-semibold',
        ok
          ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300'
          : 'border-red-500/25 bg-red-500/10 text-red-300',
      )}
    >
      <span className="flex items-center gap-1.5">
        {ok ? <CheckIcon className="size-3.5" /> : <CrossIcon className="size-3.5" />}
        {ok ? okText : koText}
      </span>
      <span className="mt-1 block text-[10px] font-medium uppercase tracking-wider opacity-70">{label}</span>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="border-b border-dashed border-white/10 py-3 last:border-b-0">
      <dt className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm font-semibold text-foreground sm:text-base">{children}</dd>
    </div>
  )
}

function CardHeader() {
  const { t } = useTranslation()
  return (
    <div className="mb-6 flex items-center gap-4 border-b border-white/10 pb-5">
      <img src="/logo-mahajanga.png" alt="" className="h-14 w-14 shrink-0 object-contain" />
      <div className="min-w-0">
        <h1 className="text-sm font-extrabold uppercase tracking-wide text-foreground sm:text-base">
          Repoblikan'i Madagasikara
        </h1>
        <p className="mt-0.5 text-[11px] font-semibold italic text-emerald-400">{t('verify.motto')}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{t('verify.subtitle')}</p>
      </div>
    </div>
  )
}

function formatDate(iso: string, language: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  try {
    return new Intl.DateTimeFormat(language, { dateStyle: 'long', timeStyle: 'short' }).format(date)
  } catch {
    return date.toLocaleString()
  }
}

function AuthenticDetails({ document, id, language }: { document: VerifiedDocument; id: string; language: string }) {
  const { t } = useTranslation()
  return (
    <>
      {document.holder_photo_url && (
        <img
          src={document.holder_photo_url}
          alt=""
          className="mb-5 h-[105px] w-[90px] rounded-md border-2 border-white/20 bg-white object-cover p-0.5"
        />
      )}

      <h2 className="text-lg font-bold text-foreground">{t('verify.detailsTitle')}</h2>
      <dl className="mt-2">
        <Field label={t('verify.fields.documentType')}>{document.document_type_label}</Field>
        <Field label={t('verify.fields.holder')}>
          {document.holder_first_name} {document.holder_last_name}
        </Field>
        {document.holder_national_id && (
          <Field label={t('verify.fields.nationalId')}>{document.holder_national_id}</Field>
        )}
        <Field label={t('verify.fields.issueDate')}>{formatDate(document.issue_date, language)}</Field>
        <Field label={t('verify.fields.identifier')}>
          <code className="break-all rounded bg-white/10 px-1.5 py-0.5 font-mono text-xs">{id}</code>
        </Field>
        <Field label={t('verify.fields.fingerprint')}>
          <code className="break-all rounded bg-white/10 px-1.5 py-0.5 font-mono text-[11px]">
            {document.signature_fingerprint}
          </code>
        </Field>
      </dl>

      {document.pdf_url && (
        <a
          href={document.pdf_url}
          download
          target="_blank"
          rel="noopener noreferrer"
          className={actionClass('primary', 'lg', 'mt-6 w-full')}
        >
          <DownloadIcon className="size-4" />
          {t('verify.download')}
        </a>
      )}
    </>
  )
}

function FailureDetails({ data }: { data: VerifyResponse }) {
  const { t } = useTranslation()
  const tone: Tone = data.status === 'REVOKED' || data.status === 'EXPIRED' ? 'warning' : 'danger'
  const key = data.status === 'REVOKED' ? 'revoked' : data.status === 'EXPIRED' ? 'expired' : 'invalid'

  return (
    <>
      <Badge tone={tone}>
        {tone === 'warning' ? <WarningIcon className="size-4" /> : <CrossIcon className="size-4" />}
        {t(`verify.${key}.badge`)}
      </Badge>
      <h2 className="mt-4 text-lg font-bold text-foreground">{t(`verify.${key}.title`)}</h2>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t(`verify.${key}.text`)}</p>

      <div className="mt-5 flex flex-col gap-2 sm:flex-row">
        <SubCheck
          ok={data.hash_matches}
          label={t('verify.integrityLabel')}
          okText={t('verify.integrityOk')}
          koText={t('verify.integrityKo')}
        />
        <SubCheck
          ok={data.signature_valid}
          label={t('verify.signatureLabel')}
          okText={t('verify.signatureOk')}
          koText={t('verify.signatureKo')}
        />
      </div>

      <p className="mt-5 rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-xs leading-relaxed text-amber-200">
        {t('verify.maskedNotice')}
      </p>

      <dl className="mt-4">
        <Field label={t('verify.fields.identifier')}>
          <code className="break-all rounded bg-white/10 px-1.5 py-0.5 font-mono text-xs">{data.id}</code>
        </Field>
      </dl>
    </>
  )
}

function Notice({ tone, badge, title, text, children }: { tone: Tone; badge?: string; title: string; text: string; children?: ReactNode }) {
  return (
    <>
      {badge && (
        <Badge tone={tone}>
          <WarningIcon className="size-4" />
          {badge}
        </Badge>
      )}
      <h2 className="mt-4 text-lg font-bold text-foreground">{title}</h2>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{text}</p>
      {children}
    </>
  )
}

function VerifyPage() {
  const { t, i18n } = useTranslation()
  const { token = '' } = useParams()
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<ViewState>({ kind: 'loading' })

  const tokenIsValid = isUuid(token)

  useEffect(() => {
    if (!tokenIsValid) return

    const controller = new AbortController()
    setState({ kind: 'loading' })

    verifyDocument(token, controller.signal)
      .then((data) => setState({ kind: 'result', data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState(
          error instanceof ApiError && error.kind === 'not_found' ? { kind: 'not_found' } : { kind: 'error' },
        )
      })

    return () => controller.abort()
  }, [token, tokenIsValid, attempt])

  let content: ReactNode

  if (!tokenIsValid) {
    content = <Notice tone="danger" badge={t('verify.badId.title')} title={t('verify.badId.title')} text={t('verify.badId.text')} />
  } else if (state.kind === 'loading') {
    content = (
      <div className="flex items-center gap-3 py-8 text-sm text-muted-foreground" role="status" aria-live="polite">
        <SpinnerIcon className="size-5 animate-spin" />
        {t('verify.loading')}
      </div>
    )
  } else if (state.kind === 'not_found') {
    content = (
      <Notice
        tone="danger"
        badge={t('verify.notFound.badge')}
        title={t('verify.notFound.title')}
        text={t('verify.notFound.text')}
      />
    )
  } else if (state.kind === 'error') {
    content = (
      <Notice tone="warning" title={t('verify.error.title')} text={t('verify.error.text')}>
        <button type="button" onClick={() => setAttempt((n) => n + 1)} className={actionClass('primary', 'md', 'mt-5')}>
          {t('verify.retry')}
        </button>
      </Notice>
    )
  } else if (state.data.is_authentic && state.data.document) {
    content = (
      <>
        <Badge tone="success">
          <CheckIcon className="size-4" />
          {t('verify.verifiedBadge')}
        </Badge>
        <div className="mb-5 mt-4 flex flex-col gap-2 sm:flex-row">
          <SubCheck
            ok
            label={t('verify.integrityLabel')}
            okText={t('verify.integrityOk')}
            koText={t('verify.integrityKo')}
          />
          <SubCheck
            ok
            label={t('verify.signatureLabel')}
            okText={t('verify.signatureOk')}
            koText={t('verify.signatureKo')}
          />
        </div>
        <AuthenticDetails document={state.data.document} id={state.data.id} language={i18n.language} />
      </>
    )
  } else {
    content = <FailureDetails data={state.data} />
  }

  return (
    <Backdrop className="flex flex-1 items-start justify-center sm:items-center" back={{ to: '/scanner', width: 'max-w-lg' }}>
      <div className="mx-auto w-full max-w-lg rounded-2xl border border-white/15 bg-card/95 p-5 shadow-2xl backdrop-blur sm:p-8">
        <CardHeader />
        {content}
        <div className="mt-6 flex flex-col gap-2 border-t border-white/10 pt-5 sm:flex-row">
          <Link to="/scanner" className={actionClass('outline', 'md', 'w-full sm:w-auto')}>
            {t('verify.scanAnother')}
          </Link>
          <Link to="/" className={actionClass('ghost', 'md', 'w-full sm:w-auto')}>
            {t('common.backHome')}
          </Link>
        </div>
      </div>
    </Backdrop>
  )
}

export default VerifyPage
