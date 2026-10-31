import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import Backdrop from '@/components/Backdrop'
import { ArrowLeftIcon } from '@/components/icons'
import { CIVIL_SLUGS, publicPath, slugToType } from '@/data/catalog'
import ServiceCard from '@/components/ServiceCard'

/** Rubriques de l'état civil : naissance, mariage, décès, législation, actes divers. */
function CivilServicesPage() {
  const { t } = useTranslation()

  return (
    <Backdrop className="flex-1">
      <div className="mx-auto max-w-6xl">
        <Link
          to="/services"
          className="inline-flex items-center gap-2 text-sm font-medium text-white/70 transition-colors hover:text-white"
        >
          <ArrowLeftIcon className="size-4" />
          {t('catalog.backToServices')}
        </Link>

        <header className="mt-5 max-w-2xl">
          <h1 className="text-3xl font-black tracking-tight text-white sm:text-4xl">
            {t('catalog.civil.title')}
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-white/75 sm:text-base">
            {t('catalog.civil.description')}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-white/60">{t('servicesPage.civilIntro')}</p>
        </header>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CIVIL_SLUGS.map((slug) => {
            const type = slugToType(slug)
            return (
              <ServiceCard
                key={slug}
                to={publicPath(type)}
                title={t(`catalog.types.${type}.title`)}
                description={t(`catalog.types.${type}.description`)}
                cta={t('servicesPage.viewService')}
              />
            )
          })}
        </div>
      </div>
    </Backdrop>
  )
}

export default CivilServicesPage
