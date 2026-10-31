import { Link, useParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import { SignInButton, useAuth } from '@clerk/react'
import Backdrop from '@/components/Backdrop'
import { ArrowLeftIcon, CheckIcon } from '@/components/icons'
import {
  isCivilSlug,
  isServiceSlug,
  requestPath,
  slugToType,
  type DossierSlug,
} from '@/data/catalog'
import NotFoundPage from '@/pages/NotFoundPage'
import { rememberReturnTo } from '@/lib/returnTo'
import { actionClass } from '@/lib/ui'

interface ServiceDetailPageProps {
  /** « service » : /services/:slug ; « civil » : /services/etat-civil/:slug. */
  kind: 'service' | 'civil'
}

/** Page de présentation d'un service ou d'un dossier d'état civil. */
function ServiceDetailPage({ kind }: ServiceDetailPageProps) {
  const { t } = useTranslation()
  const { isSignedIn } = useAuth()
  const { slug } = useParams()

  const valid = kind === 'civil' ? isCivilSlug(slug) : isServiceSlug(slug)
  if (!valid || slug === undefined) {
    return <NotFoundPage />
  }

  const type = slugToType(slug as DossierSlug)
  const target = requestPath(type)
  const pieces = t(`catalog.types.${type}.pieces`, { returnObjects: true }) as unknown
  const pieceList = Array.isArray(pieces) ? (pieces as string[]) : []

  const backTo = kind === 'civil' ? '/services/etat-civil' : '/services'
  const backLabel = kind === 'civil' ? t('catalog.civil.title') : t('catalog.backToServices')

  return (
    <Backdrop className="flex-1">
      <div className="mx-auto max-w-3xl">
        <Link
          to={backTo}
          className="inline-flex items-center gap-2 text-sm font-medium text-white/70 transition-colors hover:text-white"
        >
          <ArrowLeftIcon className="size-4" />
          {backLabel}
        </Link>

        <article className="mt-5 rounded-2xl border border-white/25 bg-gradient-to-br from-white/[0.24] via-sky-300/[0.12] to-indigo-400/[0.16] p-6 shadow-2xl shadow-blue-950/40 backdrop-blur-xl sm:p-8">
          <h1 className="text-3xl font-black tracking-tight text-white sm:text-4xl">
            {t(`catalog.types.${type}.title`)}
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-white/90 sm:text-base">
            {t(`catalog.types.${type}.description`)}
          </p>

          {pieceList.length > 0 && (
            <section className="mt-8">
              <h2 className="text-sm font-bold uppercase tracking-widest text-sky-200">
                {t('catalog.piecesTitle')}
              </h2>
              <ul className="mt-3 space-y-2.5">
                {pieceList.map((piece) => (
                  <li
                    key={piece}
                    className="flex items-start gap-3 rounded-xl border border-white/15 bg-white/10 px-4 py-3 text-sm leading-relaxed text-white"
                  >
                    <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-emerald-400 text-slate-900">
                      <CheckIcon className="size-3.5" />
                    </span>
                    <span>{piece}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-xs leading-relaxed text-white/70">{t('catalog.piecesNote')}</p>
            </section>
          )}

          <div className="mt-8">
            {isSignedIn ? (
              <Link to={target} className={actionClass('primary', 'lg', 'w-full sm:w-auto')}>
                {t('catalog.requestCta')}
              </Link>
            ) : (
              /* La capture du clic mémorise le formulaire visé : après connexion, on y arrive directement. */
              <span className="block sm:inline-block" onClickCapture={() => rememberReturnTo(target)}>
                <SignInButton mode="modal">
                  <button type="button" className={actionClass('primary', 'lg', 'w-full sm:w-auto')}>
                    {t('servicesPage.signInToRequest')}
                  </button>
                </SignInButton>
              </span>
            )}
          </div>
        </article>
      </div>
    </Backdrop>
  )
}

export default ServiceDetailPage
