import { useEffect, useRef, useState, type ComponentType, type FormEvent, type ReactNode, type SVGProps } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth, useUser } from '@clerk/react'
import { ESPACE_NOTIFICATIONS, type DossierType } from '@/data/catalog'
import {
  IDENTITY_FIELDS,
  defaultsFor,
  detailFields,
  quartierFields,
  validateField,
  type FieldDef,
  type FieldErrorCode,
} from '@/data/formSchema'
import { ApiError } from '@/lib/api'
import { createDossier } from '@/lib/espaceApi'
import { cn } from '@/lib/utils'
import { useDossiers } from '@/dashboard/dossiersContext'
import { CheckIcon, ChevronLeftIcon, ChevronRightIcon, HomeIcon, PinIcon, SendIcon, SpinnerIcon } from '@/dashboard/icons'

interface DossierFormProps {
  /** Type de dossier de la page de demande. */
  type: DossierType
}

type Values = Record<string, string>
type Errors = Record<string, FieldErrorCode>
type Phase = 'idle' | 'submitting' | 'success'

const AUTOCOMPLETE: Record<string, string> = {
  first_name: 'given-name',
  last_name: 'family-name',
  email: 'email',
  phone: 'tel',
  address: 'street-address',
}

/** Icône placée devant le libellé de certains champs (étape « Quartier »). */
const FIELD_ICONS: Record<string, ComponentType<SVGProps<SVGSVGElement>>> = {
  fokontany: PinIcon,
  main_residence: HomeIcon,
}

interface Step {
  key: string
  title: string
  fields: readonly FieldDef[]
}

const fieldId = (name: string) => `dossier-${name}`

/** Dans l'espace usager, tous les champs sont à remplir avant l'envoi, sauf ceux marqués facultatifs. */
const checkField = (field: FieldDef, value: string) => validateField({ ...field, required: !field.optional }, value)

/** Champs regroupés par rubrique, dans l'ordre (rubrique vide : pas de titre). */
function bySection(fields: readonly FieldDef[]): { section: string; fields: FieldDef[] }[] {
  const groups: { section: string; fields: FieldDef[] }[] = []
  for (const field of fields) {
    const section = field.section ?? ''
    const last = groups[groups.length - 1]
    if (last && last.section === section) last.fields.push(field)
    else groups.push({ section, fields: [field] })
  }
  return groups
}

/**
 * Formulaire de demande : identité + détails propres au type de dossier.
 * Actes (naissance, mariage, décès, législation) : en trois étapes — vos informations, détails
 * de la demande, quartier — avec « Suivant » entre chaque étape et « Envoyer » à la fin.
 */
function DossierForm({ type }: DossierFormProps) {
  const { t, i18n } = useTranslation()
  const { getToken } = useAuth()
  const { user } = useUser()
  const { reload } = useDossiers()

  const [values, setValues] = useState<Values>(() => ({
    ...defaultsFor(IDENTITY_FIELDS),
    ...defaultsFor(detailFields(type)),
    ...defaultsFor(quartierFields(type)),
  }))
  const [step, setStep] = useState(0)
  // Champ à focaliser après un changement d'étape (il n'existe dans la page qu'après le rendu).
  const [pendingFocus, setPendingFocus] = useState<string | null>(null)
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [reference, setReference] = useState('')

  const prefilled = useRef(false)
  const noticeRef = useRef<HTMLDivElement>(null)
  const formRef = useRef<HTMLFormElement>(null)

  const fields = detailFields(type)
  const quartier = quartierFields(type)
  const allFields = [...IDENTITY_FIELDS, ...fields, ...quartier]
  const steps: Step[] = [
    { key: 'identity', title: t('dash.form.identityTitle'), fields: IDENTITY_FIELDS },
    { key: 'details', title: t('dash.form.detailsTitle'), fields },
    ...(quartier.length ? [{ key: 'quartier', title: t('dash.form.quartierTitle'), fields: quartier }] : []),
  ]
  // Sans étape « Quartier » (autres services), tout le formulaire tient sur une page.
  const wizard = quartier.length > 0
  const lastStep = !wizard || step === steps.length - 1
  const visibleSteps = wizard ? [steps[step]] : steps
  const filled = (list: readonly FieldDef[]) =>
    list.every((field) => field.optional || (values[field.name] ?? '').trim() !== '')
  // « Suivant » et « Envoyer » restent inactifs tant qu'un champ de l'étape est vide.
  const complete = filled(wizard ? steps[step].fields : allFields)

  // Préremplit l'identité avec le compte connecté, une seule fois et sans écraser la saisie.
  useEffect(() => {
    if (prefilled.current || !user) return
    prefilled.current = true

    const known: Values = {
      first_name: user.firstName ?? '',
      last_name: user.lastName ?? '',
      email: user.primaryEmailAddress?.emailAddress ?? '',
      phone: user.primaryPhoneNumber?.phoneNumber ?? '',
    }
    setValues((current) => {
      const next = { ...current }
      for (const [name, value] of Object.entries(known)) {
        if (value && !next[name]) next[name] = value
      }
      return next
    })
  }, [user])

  // Place le focus sur le message de confirmation (lecteurs d'écran, clavier).
  useEffect(() => {
    if (phase === 'success') noticeRef.current?.focus()
  }, [phase])

  useEffect(() => {
    if (!pendingFocus) return
    document.getElementById(fieldId(pendingFocus))?.focus()
    setPendingFocus(null)
  }, [pendingFocus, step])

  const findErrors = (list: readonly FieldDef[]): Errors => {
    const found: Errors = {}
    for (const field of list) {
      const code = checkField(field, values[field.name] ?? '')
      if (code) found[field.name] = code
    }
    return found
  }

  /** Affiche l'étape du premier champ en erreur et y place le focus. */
  const showFirstError = (found: Errors): boolean => {
    const firstInvalid = allFields.find((field) => found[field.name])
    if (!firstInvalid) return false
    if (wizard) {
      const index = steps.findIndex((item) => item.fields.some((field) => field.name === firstInvalid.name))
      if (index !== -1) setStep(index)
    }
    setPendingFocus(firstInvalid.name)
    return true
  }

  const goTo = (index: number) => {
    setStep(index)
    setFormError(null)
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setPendingFocus(steps[index].fields[0]?.name ?? null)
  }

  const next = () => {
    const found = findErrors(steps[step].fields)
    setErrors((current) => ({ ...current, ...found }))
    if (!showFirstError(found)) goTo(step + 1)
  }

  const identityValues = (source: Values): Values => {
    const identity: Values = {}
    for (const field of IDENTITY_FIELDS) identity[field.name] = source[field.name] ?? ''
    return identity
  }

  const setValue = (name: string, value: string) => {
    setValues((current) => ({ ...current, [name]: value }))
    setErrors((current) => {
      if (!(name in current)) return current
      const next = { ...current }
      delete next[name]
      return next
    })
  }

  const reset = () => {
    setPhase('idle')
    setStep(0)
    setReference('')
    setErrors({})
    setFormError(null)
    setValues((current) => ({ ...identityValues(current), ...defaultsFor(fields), ...defaultsFor(quartier) }))
  }

  const errorText = (field: FieldDef, code: FieldErrorCode): string => {
    if (code === 'invalid' && field.kind === 'email') return t('dash.form.errors.email')
    if (code === 'invalid' && field.kind === 'phone') return t('dash.form.errors.phone')
    return t(`dash.form.errors.${code}`)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (phase === 'submitting') return
    // Entrée dans une étape intermédiaire : passe à l'étape suivante au lieu d'envoyer.
    if (!lastStep) {
      next()
      return
    }
    setFormError(null)

    const found = findErrors(allFields)
    setErrors(found)
    if (showFirstError(found)) return

    const identity: Values = {}
    for (const field of IDENTITY_FIELDS) {
      const value = (values[field.name] ?? '').trim()
      if (value) identity[field.name] = value
    }
    const details: Values = {}
    for (const field of [...fields, ...quartier]) {
      const value = (values[field.name] ?? '').trim()
      if (value) details[field.name] = value
    }

    setPhase('submitting')
    try {
      const result = await createDossier(getToken, {
        dossier_type: type,
        guichet: '',
        identity,
        details,
      })
      setReference(result.reference)
      setPhase('success')
      void reload()
    } catch (error) {
      setPhase('idle')
      if (error instanceof ApiError && error.kind === 'validation') {
        const mapped: Errors = {}
        for (const [key, codes] of Object.entries(error.fieldErrors)) {
          const name = key.includes('.') ? key.slice(key.indexOf('.') + 1) : key
          const code = codes[0]
          mapped[name] = code === 'required' || code === 'too_long' ? code : 'invalid'
        }
        setErrors(mapped)
        setFormError(t('dash.form.errors.global'))
        showFirstError(mapped)
        return
      }
      if (error instanceof ApiError) {
        const known = ['throttled', 'network', 'unauthenticated'] as const
        const key = known.find((kind) => kind === error.kind) ?? 'server'
        setFormError(t(`dash.form.errors.${key}`))
        return
      }
      setFormError(t('dash.form.errors.server'))
    }
  }

  const renderField = (field: FieldDef): ReactNode => {
    const id = fieldId(field.name)
    const code = errors[field.name]
    const message = code ? errorText(field, code) : null
    const value = values[field.name] ?? ''
    const describedBy = message ? `${id}-error` : undefined
    const invalid = code ? true : undefined

    let control: ReactNode
    if (field.kind === 'select') {
      control = (
        <select
          id={id}
          name={field.name}
          value={value}
          onChange={(event) => setValue(field.name, event.target.value)}
          aria-required={!field.optional}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          className="d-input"
        >
          <option value="">{t(field.placeholder ?? 'dash.form.select')}</option>
          {(field.options ?? []).map((option) => (
            <option key={option} value={option}>
              {field.rawOptions ? option : t(`dash.options.${option}`)}
            </option>
          ))}
        </select>
      )
    } else if (field.kind === 'textarea') {
      control = (
        <textarea
          id={id}
          name={field.name}
          rows={4}
          maxLength={field.maxLength}
          value={value}
          onChange={(event) => setValue(field.name, event.target.value)}
          aria-required={!field.optional}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          className="d-input resize-y"
        />
      )
    } else {
      const inputType =
        field.kind === 'email'
          ? 'email'
          : field.kind === 'phone'
            ? 'tel'
            : field.kind === 'date' || field.kind === 'time'
              ? field.kind
              : 'text'
      const inputMode: 'numeric' | 'decimal' | undefined =
        field.kind === 'integer' ? 'numeric' : field.kind === 'number' ? 'decimal' : undefined
      control = (
        <input
          id={id}
          name={field.name}
          type={inputType}
          inputMode={inputMode}
          autoComplete={AUTOCOMPLETE[field.name] ?? 'off'}
          maxLength={field.kind === 'date' || field.kind === 'time' ? undefined : field.maxLength}
          value={value}
          onChange={(event) => setValue(field.name, event.target.value)}
          aria-required={!field.optional}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          className="d-input"
        />
      )
    }

    const Icon = FIELD_ICONS[field.name]

    if (field.kind === 'choice') {
      return (
        <div key={field.name} className="sm:col-span-2">
          <p id={`${id}-label`} className={cn('d-label', Icon && 'inline-flex items-center gap-1.5')}>
            {Icon && <Icon className="size-4" />}
            {t(`dash.fields.${field.name}`)}{' '}
            <span className="d-required" aria-hidden="true">
              *
            </span>
          </p>
          <div
            id={id}
            role="radiogroup"
            aria-labelledby={`${id}-label`}
            aria-invalid={invalid}
            aria-describedby={describedBy}
            className="d-choice"
          >
            {(field.options ?? []).map((option) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={value === option}
                className={cn('d-choice-btn', value === option && 'is-active')}
                onClick={() => setValue(field.name, option)}
              >
                {value === option && <CheckIcon className="size-4" />}
                {t(`dash.options.${option}`)}
              </button>
            ))}
          </div>
          {message && (
            <p id={`${id}-error`} className="d-error">
              {message}
            </p>
          )}
        </div>
      )
    }

    return (
      <div key={field.name} className={cn((field.kind === 'textarea' || Icon) && 'sm:col-span-2')}>
        <label htmlFor={id} className={cn('d-label', Icon && 'inline-flex items-center gap-1.5')}>
          {Icon && <Icon className="size-4" />}
          {t(`dash.fields.${field.name}`)}{' '}
          {field.optional ? (
            <span className="d-muted text-xs font-normal">({t('dash.hints.optional')})</span>
          ) : (
            <span className="d-required" aria-hidden="true">
              *
            </span>
          )}
        </label>
        {control}
        {i18n.exists(`dash.hints.${field.name}`) && !message && (
          <p className="d-hint">{t(`dash.hints.${field.name}`)}</p>
        )}
        {message && (
          <p id={`${id}-error`} className="d-error">
            {message}
          </p>
        )}
      </div>
    )
  }

  if (phase === 'success') {
    return (
      <div ref={noticeRef} tabIndex={-1} role="status" className="d-notice d-notice-success outline-none">
        <p className="flex items-start gap-2 font-semibold">
          <CheckIcon className="mt-0.5 size-4 shrink-0" />
          <span>{t('dash.form.success', { reference })}</span>
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link to={ESPACE_NOTIFICATIONS} className="d-btn">
            {t('dash.form.seeNotifications')}
          </Link>
          <button type="button" className="d-btn-ghost" onClick={reset}>
            {t('dash.form.another')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} noValidate className="scroll-mt-24 space-y-7">
      {wizard && (
        <ol className="d-steps" aria-label={t('dash.form.stepOf', { current: step + 1, total: steps.length })}>
          {steps.map((item, index) => (
            <li
              key={item.key}
              className={cn('d-step', index === step && 'is-current', index < step && 'is-done')}
              aria-current={index === step ? 'step' : undefined}
            >
              <button type="button" disabled={index >= step} onClick={() => goTo(index)}>
                <span className="d-step-dot">{index < step ? <CheckIcon className="size-3.5" /> : index + 1}</span>
                <span className="d-step-label">{item.title}</span>
              </button>
            </li>
          ))}
        </ol>
      )}

      {visibleSteps.map((item) => (
        <fieldset key={item.key} className="d-fieldset">
          <legend className="d-legend">{item.title}</legend>
          {bySection(item.fields).map((group) => (
            <div key={group.section || 'main'} className={cn(group.section && 'd-subsection')}>
              {group.section && <h3 className="d-subsection-title">{t(`dash.sections.${group.section}`)}</h3>}
              <div className="grid gap-4 sm:grid-cols-2">{group.fields.map(renderField)}</div>
            </div>
          ))}
        </fieldset>
      ))}

      {formError && (
        <p role="alert" className="d-notice d-notice-error">
          {formError}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p id="dossier-submit-hint" className="d-muted text-xs">
          {complete ? t('dash.form.required') : t(wizard ? 'dash.form.fillStep' : 'dash.form.fillAll')}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          {wizard && step > 0 && (
            <button type="button" className="d-btn-ghost" onClick={() => goTo(step - 1)}>
              <ChevronLeftIcon className="size-4" />
              {t('dash.form.previous')}
            </button>
          )}
          {!lastStep ? (
            <button
              type="button"
              className="d-btn min-w-40"
              disabled={!complete}
              aria-describedby="dossier-submit-hint"
              onClick={next}
            >
              {t('dash.form.next')}
              <ChevronRightIcon className="size-4" />
            </button>
          ) : (
            <button
              type="submit"
              className="d-btn min-w-40"
              disabled={phase === 'submitting' || !complete}
              aria-describedby="dossier-submit-hint"
            >
              {phase === 'submitting' ? (
                <>
                  <SpinnerIcon className="size-4 animate-spin" />
                  {t('dash.form.submitting')}
                </>
              ) : (
                <>
                  <SendIcon className="size-4" />
                  {t('dash.form.submit')}
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </form>
  )
}

export default DossierForm
