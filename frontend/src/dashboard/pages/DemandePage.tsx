import { Link, useParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import { ESPACE_HOME, isDossierSlug, publicPath, slugToType } from '@/data/catalog'
import DossierForm from '@/dashboard/DossierForm'
import { DOSSIER_ICONS } from '@/dashboard/dossierIcons'
import { ChevronLeftIcon } from '@/dashboard/icons'

/** Page dédiée d'une demande (Recette, Urbanisme, Transport, Marché, Cadastre, Impôt foncier, état civil…). */
function DemandePage() {
  const { t } = useTranslation()
  const { slug } = useParams()

  if (!isDossierSlug(slug)) {
    return (
      <div className="mx-auto max-w-2xl">
        <p role="alert" className="d-notice d-notice-error">
          {t('dash.demande.invalid')}
        </p>
        <Link to={ESPACE_HOME} className="d-page-link mt-4 inline-block text-sm">
          {t('common.backHome')}
        </Link>
      </div>
    )
  }

  const type = slugToType(slug)
  const title = t(`catalog.types.${type}.title`)
  const Icon = DOSSIER_ICONS[type]

  return (
    <div className="mx-auto max-w-4xl">
      <Link to={ESPACE_HOME} className="d-page-link mb-4 inline-flex items-center gap-1 text-sm">
        <ChevronLeftIcon className="size-4" />
        {t('dash.demande.back')}
      </Link>
      <section className="d-glass p-5 sm:p-8">
        <div className="mb-7 flex items-start gap-4">
          <span className="d-request-icon shrink-0" aria-hidden="true">
            <Icon className="size-5" strokeWidth={1.8} />
          </span>
          <div className="min-w-0">
            <h1 className="d-heading text-xl font-bold sm:text-2xl">{t('dash.demande.title', { type: title })}</h1>
            <p className="d-muted mt-1 text-sm">{t('dash.demande.intro', { type: title })}</p>
            <Link to={publicPath(type)} className="d-link mt-2 inline-block text-xs">
              {t('dash.demande.publicPage')}
            </Link>
          </div>
        </div>
        {/* `key` : repart d'un formulaire vierge quand on change de rubrique. */}
        <DossierForm key={type} type={type} />
      </section>
    </div>
  )
}

export default DemandePage
