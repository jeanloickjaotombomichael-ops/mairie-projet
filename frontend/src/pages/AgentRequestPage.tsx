import { useState, type ChangeEvent, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import Backdrop from '@/components/Backdrop'
import { CheckIcon, SpinnerIcon } from '@/components/icons'
import { ApiError, submitAgentRequest, type AgentRequestPayload } from '@/lib/api'
import { actionClass } from '@/lib/ui'
import { cn } from '@/lib/utils'

type FieldName = 'first_name' | 'last_name' | 'phone_number' | 'email'
type FieldErrors = Partial<Record<FieldName, 'required' | 'email' | 'invalid'>>
type Status = 'idle' | 'submitting' | 'success'

const EMPTY_FORM: AgentRequestPayload = {
  first_name: '',
  last_name: '',
  phone_number: '',
  email: '',
  request_type: 'AGENT_ACCESS',
  message: '',
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE_PATTERN = /^[0-9+()\-.\s]{6,30}$/

const inputClass =
  'w-full rounded-lg border border-white/15 bg-white/5 px-3 py-2.5 text-sm text-white placeholder:text-white/40 focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/60'

function validate(form: AgentRequestPayload): FieldErrors {
  const errors: FieldErrors = {}
  if (!form.first_name.trim()) errors.first_name = 'required'
  if (!form.last_name.trim()) errors.last_name = 'required'
  if (!form.phone_number.trim()) errors.phone_number = 'required'
  else if (!PHONE_PATTERN.test(form.phone_number.trim())) errors.phone_number = 'invalid'
  if (!form.email.trim()) errors.email = 'required'
  else if (!EMAIL_PATTERN.test(form.email.trim())) errors.email = 'email'
  return errors
}

function AgentRequestPage() {
  const { t } = useTranslation()
  const [form, setForm] = useState<AgentRequestPayload>(EMPTY_FORM)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [status, setStatus] = useState<Status>('idle')
  const [formError, setFormError] = useState<string | null>(null)

  const bullets = t('agent.bullets', { returnObjects: true }) as string[]

  const update =
    (name: keyof AgentRequestPayload) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      setForm((current) => ({ ...current, [name]: event.target.value }))
      if (name in fieldErrors) {
        setFieldErrors((current) => ({ ...current, [name]: undefined }))
      }
    }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (status === 'submitting') return

    const payload: AgentRequestPayload = {
      ...form,
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      phone_number: form.phone_number.trim(),
      email: form.email.trim(),
      message: form.message.trim(),
    }

    const errors = validate(payload)
    setFieldErrors(errors)
    setFormError(null)
    if (Object.keys(errors).length > 0) return

    setStatus('submitting')
    try {
      await submitAgentRequest(payload)
      setForm(EMPTY_FORM)
      setStatus('success')
    } catch (error) {
      setStatus('idle')
      if (error instanceof ApiError) {
        if (error.kind === 'validation') {
          const serverErrors: FieldErrors = {}
          for (const name of ['first_name', 'last_name', 'phone_number', 'email'] as const) {
            if (error.fieldErrors[name]) serverErrors[name] = 'invalid'
          }
          setFieldErrors(serverErrors)
          setFormError(t('agent.errors.invalid'))
        } else if (error.kind === 'throttled') {
          setFormError(t('agent.errors.throttled'))
        } else if (error.kind === 'network') {
          setFormError(t('agent.errors.network'))
        } else {
          setFormError(t('agent.errors.server'))
        }
        return
      }
      setFormError(t('agent.errors.server'))
    }
  }

  const errorText = (name: FieldName) => {
    const code = fieldErrors[name]
    if (!code) return null
    if (code === 'required') return t('agent.errors.required')
    if (code === 'email') return t('agent.errors.email')
    return t('agent.errors.invalid')
  }

  const renderField = (
    name: FieldName,
    label: string,
    placeholder: string,
    type: 'text' | 'email' | 'tel',
    autoComplete: string,
  ) => {
    const message = errorText(name)
    return (
      <div>
        <label htmlFor={name} className="mb-1.5 block text-xs font-semibold text-white/80">
          {label} <span className="text-primary">*</span>
        </label>
        <input
          id={name}
          name={name}
          type={type}
          autoComplete={autoComplete}
          value={form[name]}
          onChange={update(name)}
          placeholder={placeholder}
          aria-invalid={message ? true : undefined}
          aria-describedby={message ? `${name}-error` : undefined}
          className={cn(inputClass, message && 'border-red-500/60')}
        />
        {message && (
          <p id={`${name}-error`} className="mt-1 text-xs text-red-300">
            {message}
          </p>
        )}
      </div>
    )
  }

  return (
    <Backdrop back={{ to: '/', width: 'max-w-5xl' }}>
      <div className="mx-auto grid max-w-5xl gap-8 lg:grid-cols-2 lg:gap-12">
        <section className="flex flex-col justify-center">
          <h1 className="text-3xl font-black leading-tight tracking-tight text-white sm:text-4xl">
            {t('agent.title')}
          </h1>
          <ul className="mt-6 space-y-3">
            {bullets.map((bullet) => (
              <li key={bullet} className="flex items-start gap-3 text-sm leading-relaxed text-white/80">
                <CheckIcon className="mt-0.5 size-4 shrink-0 text-primary" />
                <span>{bullet}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-2xl border border-white/10 bg-[#0a0a0a]/85 p-5 shadow-xl backdrop-blur-sm sm:p-7">
          <h2 className="text-lg font-bold text-white">{t('agent.formTitle')}</h2>

          {status === 'success' ? (
            <div
              role="status"
              className="mt-5 flex items-start gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm leading-relaxed text-emerald-200"
            >
              <CheckIcon className="mt-0.5 size-4 shrink-0" />
              <p>{t('agent.success')}</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} noValidate className="mt-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                {renderField('first_name', t('agent.firstName'), t('agent.firstNamePlaceholder'), 'text', 'given-name')}
                {renderField('last_name', t('agent.lastName'), t('agent.lastNamePlaceholder'), 'text', 'family-name')}
              </div>
              {renderField('phone_number', t('agent.phone'), t('agent.phonePlaceholder'), 'tel', 'tel')}
              {renderField('email', t('agent.email'), t('agent.emailPlaceholder'), 'email', 'email')}

              <div>
                <label htmlFor="request_type" className="mb-1.5 block text-xs font-semibold text-white/80">
                  {t('agent.requestType')}
                </label>
                <select
                  id="request_type"
                  name="request_type"
                  value={form.request_type}
                  onChange={update('request_type')}
                  className={cn(inputClass, 'bg-[#0a0a0a]')}
                >
                  <option value="AGENT_ACCESS">{t('agent.requestTypeAgent')}</option>
                </select>
              </div>

              <div>
                <label htmlFor="message" className="mb-1.5 block text-xs font-semibold text-white/80">
                  {t('agent.message')}
                </label>
                <textarea
                  id="message"
                  name="message"
                  rows={4}
                  maxLength={2000}
                  value={form.message}
                  onChange={update('message')}
                  placeholder={t('agent.messagePlaceholder')}
                  className={cn(inputClass, 'resize-y')}
                />
              </div>

              {formError && (
                <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                  {formError}
                </p>
              )}

              <button
                type="submit"
                disabled={status === 'submitting'}
                className={actionClass('primary', 'lg', 'w-full')}
              >
                {status === 'submitting' ? (
                  <>
                    <SpinnerIcon className="size-4 animate-spin" />
                    {t('agent.submitting')}
                  </>
                ) : (
                  t('agent.submit')
                )}
              </button>
              <p className="text-center text-[11px] text-white/50">{t('agent.required')}</p>
            </form>
          )}
        </section>
      </div>
    </Backdrop>
  )
}

export default AgentRequestPage
