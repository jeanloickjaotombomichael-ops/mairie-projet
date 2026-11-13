import { useId, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import BackLink from '@/components/BackLink'
import ContactIllustration from '@/components/ContactIllustration'
import { ListIcon, MailIcon, PhoneIcon, PinIcon, SpinnerIcon, UserIcon } from '@/components/icons'
import { CONTACT_INFO } from '@/data/contactInfo'
import { ApiError, submitContact, type ContactPayload } from '@/lib/api'
import { cn } from '@/lib/utils'

type FieldName = keyof ContactPayload
type FieldErrorCode = 'required' | 'email' | 'phone' | 'invalid'
type FieldErrors = Partial<Record<FieldName, FieldErrorCode>>
type Phase = 'idle' | 'submitting' | 'success'

const EMPTY_FORM: ContactPayload = {
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  message: '',
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE_PATTERN = /^[0-9+()\-.\s]{6,30}$/

const MAX_LENGTH: Record<FieldName, number> = {
  first_name: 100,
  last_name: 100,
  phone: 30,
  email: 254,
  message: 2000,
}

/** Mêmes règles que le serveur (`espace/schemas.py`) : prénom, téléphone et e-mail obligatoires. */
function validate(form: ContactPayload): FieldErrors {
  const errors: FieldErrors = {}
  if (!form.first_name.trim()) errors.first_name = 'required'
  else if (form.first_name.trim().length > MAX_LENGTH.first_name) errors.first_name = 'invalid'

  if (form.last_name.trim().length > MAX_LENGTH.last_name) errors.last_name = 'invalid'

  if (!form.phone.trim()) errors.phone = 'required'
  else if (!PHONE_PATTERN.test(form.phone.trim())) errors.phone = 'phone'

  if (!form.email.trim()) errors.email = 'required'
  else if (!EMAIL_PATTERN.test(form.email.trim()) || form.email.trim().length > MAX_LENGTH.email) {
    errors.email = 'email'
  }

  if (form.message.trim().length > MAX_LENGTH.message) errors.message = 'invalid'
  return errors
}

interface FieldProps {
  name: FieldName
  label: string
  required?: boolean
  icon: ReactNode
  value: string
  error?: string | null
  type?: 'text' | 'email' | 'tel'
  autoComplete?: string
  multiline?: boolean
  onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void
}

/** Champ à fond gris clair, icône à gauche et libellé en filigrane (astérisque rouge si obligatoire). */
function Field({
  name,
  label,
  required = false,
  icon,
  value,
  error,
  type = 'text',
  autoComplete,
  multiline = false,
  onChange,
}: FieldProps) {
  const errorId = useId()
  const common = {
    id: `contact-${name}`,
    name,
    value,
    onChange,
    maxLength: MAX_LENGTH[name],
    'aria-label': label,
    'aria-required': required || undefined,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': error ? errorId : undefined,
    className: cn(
      'w-full rounded-lg border bg-slate-100/80 pl-11 pr-3 text-sm text-slate-800 outline-none transition-colors focus:border-violet-400 focus:bg-white focus:ring-2 focus:ring-violet-200',
      error ? 'border-red-400' : 'border-transparent',
    ),
  }

  return (
    <div>
      <div className="relative">
        <span
          className={cn(
            'pointer-events-none absolute left-3.5 text-slate-400',
            multiline ? 'top-3.5' : 'top-1/2 -translate-y-1/2',
          )}
        >
          {icon}
        </span>

        {multiline ? (
          <textarea {...common} rows={4} className={cn(common.className, 'min-h-28 resize-y py-3')} />
        ) : (
          <input {...common} type={type} autoComplete={autoComplete} className={cn(common.className, 'h-11')} />
        )}

        {value === '' && (
          <span
            aria-hidden="true"
            className={cn(
              'pointer-events-none absolute left-11 text-sm text-slate-400',
              multiline ? 'top-3' : 'top-1/2 -translate-y-1/2',
            )}
          >
            {label}
            {required && <span className="text-red-500"> *</span>}
          </span>
        )}
      </div>
      {error && (
        <p id={errorId} className="mt-1 text-xs text-red-500">
          {error}
        </p>
      )}
    </div>
  )
}

/** Ligne « coordonnée » : pastille à contour violet + texte (sur le fond bleu). */
function InfoRow({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li className="flex items-center gap-4">
      <span className="grid size-10 shrink-0 place-items-center rounded-full border border-violet-300 bg-violet-50 text-violet-600">
        {icon}
      </span>
      <span className="min-w-0 break-words text-sm text-white/85">{children}</span>
    </li>
  )
}

/** Page « Contact » : bandeau dégradé, illustration, coordonnées et formulaire d'envoi de message. */
function ContactPage() {
  const { t } = useTranslation()
  const [form, setForm] = useState<ContactPayload>(EMPTY_FORM)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [phase, setPhase] = useState<Phase>('idle')
  const [formError, setFormError] = useState<string | null>(null)

  const update = (name: FieldName) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setErrors((current) => (current[name] ? { ...current, [name]: undefined } : current))
    if (phase === 'success') setPhase('idle')
  }

  const errorText = (name: FieldName): string | null => {
    const code = errors[name]
    if (!code) return null
    return t(`contactPage.errors.${code}`)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (phase === 'submitting') return

    const payload: ContactPayload = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      phone: form.phone.trim(),
      email: form.email.trim(),
      message: form.message.trim(),
    }

    const found = validate(payload)
    setErrors(found)
    setFormError(null)
    if (Object.keys(found).length > 0) return

    setPhase('submitting')
    try {
      await submitContact(payload)
      setForm(EMPTY_FORM)
      setPhase('success')
    } catch (error) {
      setPhase('idle')
      if (error instanceof ApiError) {
        if (error.kind === 'validation') {
          const serverErrors: FieldErrors = {}
          for (const name of ['first_name', 'last_name', 'phone', 'email', 'message'] as const) {
            if (error.fieldErrors[name]) serverErrors[name] = 'invalid'
          }
          setErrors(serverErrors)
          setFormError(t('contactPage.errors.invalid'))
        } else if (error.kind === 'throttled') {
          setFormError(t('contactPage.errors.throttled'))
        } else if (error.kind === 'network') {
          setFormError(t('contactPage.errors.network'))
        } else {
          setFormError(t('contactPage.errors.server'))
        }
        return
      }
      setFormError(t('contactPage.errors.server'))
    }
  }

  // L'adresse e-mail de l'introduction est mise en évidence (lien vert), comme sur la maquette.
  const intro = t('contactPage.intro', { email: CONTACT_INFO.email })
  const parts = intro.split(CONTACT_INFO.email)
  const introNode =
    parts.length === 2 ? (
      <>
        {parts[0]}
        <a href={`mailto:${CONTACT_INFO.email}`} className="font-medium text-lime-300 underline-offset-2 hover:underline">
          {CONTACT_INFO.email}
        </a>
        {parts[1]}
      </>
    ) : (
      intro
    )

  return (
    <main className="bg-blason relative -mt-16 flex-1 overflow-hidden pt-16 text-slate-800">
      <div className="relative mx-auto max-w-5xl px-4 pb-16 pt-10 sm:px-6 sm:pt-12 lg:px-8">
        <BackLink fallback="/" className="mb-4" />
        <header className="mx-auto max-w-2xl text-center text-white">
          <h1 className="text-3xl font-medium tracking-tight sm:text-4xl">{t('contactPage.title')}</h1>
          <p className="mt-3 text-xs leading-relaxed text-white/85 sm:text-sm">{introNode}</p>
        </header>

        <div className="mt-10 grid gap-10 lg:grid-cols-2 lg:items-start lg:gap-14">
          {/* Illustration et coordonnées */}
          <section className="order-2 lg:order-1">
            <ContactIllustration className="mx-auto w-full max-w-md" />

            <h2 className="mt-6 text-xl font-medium text-white">{t('contactPage.getInTouch')}</h2>
            <div className="mt-2 h-px w-full bg-white/20" />
            <ul className="mt-5 space-y-4">
              <InfoRow icon={<PhoneIcon className="size-[18px]" />}>
                <a href={`tel:${CONTACT_INFO.phone.replace(/\s+/g, '')}`} className="hover:text-white">
                  {CONTACT_INFO.phone}
                </a>
              </InfoRow>
              <InfoRow icon={<MailIcon className="size-[18px]" />}>
                <a href={`mailto:${CONTACT_INFO.email}`} className="hover:text-white">
                  {CONTACT_INFO.email}
                </a>
              </InfoRow>
              <InfoRow icon={<PinIcon className="size-[18px]" />}>{CONTACT_INFO.address}</InfoRow>
            </ul>
          </section>

          {/* Formulaire */}
          <section className="order-1 rounded-2xl border border-slate-100 bg-white p-6 shadow-[0_24px_60px_-20px_rgba(76,52,170,0.45)] sm:p-7 lg:order-2">
            {phase === 'success' && (
              <p
                role="status"
                className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-sm text-emerald-700"
              >
                {t('contactPage.success')}
              </p>
            )}

            <form onSubmit={handleSubmit} noValidate className="space-y-3.5">
              <Field
                name="first_name"
                label={t('contactPage.firstName')}
                required
                icon={<UserIcon className="size-[18px]" />}
                value={form.first_name}
                error={errorText('first_name')}
                autoComplete="given-name"
                onChange={update('first_name')}
              />
              <Field
                name="last_name"
                label={t('contactPage.lastName')}
                icon={<UserIcon className="size-[18px]" />}
                value={form.last_name}
                error={errorText('last_name')}
                autoComplete="family-name"
                onChange={update('last_name')}
              />
              <Field
                name="phone"
                label={t('contactPage.phone')}
                required
                type="tel"
                icon={<PhoneIcon className="size-[18px]" />}
                value={form.phone}
                error={errorText('phone')}
                autoComplete="tel"
                onChange={update('phone')}
              />
              <Field
                name="email"
                label={t('contactPage.email')}
                required
                type="email"
                icon={<MailIcon className="size-[18px]" />}
                value={form.email}
                error={errorText('email')}
                autoComplete="email"
                onChange={update('email')}
              />
              <Field
                name="message"
                label={t('contactPage.message')}
                multiline
                icon={<ListIcon className="size-[18px]" />}
                value={form.message}
                error={errorText('message')}
                onChange={update('message')}
              />

              {formError && (
                <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">
                  {formError}
                </p>
              )}

              <button
                type="submit"
                disabled={phase === 'submitting'}
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-gradient-to-r from-[#5f9d1a] to-[#9ad82b] text-sm font-semibold uppercase tracking-wide text-white shadow-md transition hover:brightness-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime-400 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {phase === 'submitting' ? (
                  <>
                    <SpinnerIcon className="size-4 animate-spin" />
                    {t('contactPage.sending')}
                  </>
                ) : (
                  t('contactPage.send')
                )}
              </button>

              <p className="px-2 text-center text-[11px] leading-relaxed text-slate-400">
                {t('contactPage.privacy')}
              </p>
            </form>
          </section>
        </div>
      </div>
    </main>
  )
}

export default ContactPage
