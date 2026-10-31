import { useTranslation } from 'react-i18next'
import Backdrop from '@/components/Backdrop'
import ServiceCard from '@/components/ServiceCard'
import { SERVICE_SLUGS, publicPath, slugToType } from '@/data/catalog'

/** Liste de tous les services municipaux, avec l'état civil. */
function ServicesPage() {
  const { t } = useTranslation()

  return (
    <Backdrop className="flex-1" back={{ to: '/' }}>
      <div className="mx-auto max-w-6xl">
        <header className="max-w-2xl">
          <h1 className="text-3xl font-black tracking-tight text-white sm:text-4xl">
            {t('catalog.servicesTitle')}
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-white/75 sm:text-base">
            {t('catalog.servicesIntro')}
          </p>
        </header>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SERVICE_SLUGS.map((slug) => {
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

          <ServiceCard
            to="/services/etat-civil"
            title={t('catalog.civil.title')}
            description={t('catalog.civil.description')}
            cta={t('servicesPage.viewService')}
          />
        </div>
      </div>
    </Backdrop>
  )
}

export default ServicesPage
