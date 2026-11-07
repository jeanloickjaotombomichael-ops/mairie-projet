import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import AnimatedBackground from '@/components/AnimatedBackground'
import ServiceCard from '@/components/ServiceCard'
import SiteSearchBar from '@/components/SiteSearchBar'
import { ChevronLeftIcon, ChevronRightIcon, MailIcon, ScanIcon } from '@/components/icons'
import { ESPACE_HOME, SERVICE_SLUGS, publicPath, slugToType } from '@/data/catalog'
import { useScrollRow } from '@/hooks/useScrollRow'
import { useTypewriter } from '@/hooks/useTypewriter'
import { actionClass } from '@/lib/ui'

const arrowClass =
  'inline-flex size-10 items-center justify-center rounded-full border border-white/20 bg-white/5 text-white transition-colors hover:bg-white hover:text-[#0a0a0a] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-white/5 disabled:hover:text-white'

interface Step {
  title: string
  text: string
}

/** Titre de section. */
function SectionTitle({ title }: { title: string }) {
  return <h2 className="text-2xl font-black tracking-tight text-white sm:text-3xl">{title}</h2>
}

/** Page d'accueil : photo et recherche, puis services, étapes, vérification et aide. */
function Home() {
  const { t } = useTranslation()
  const typedWords = t('home.typedWords', { returnObjects: true }) as string[]
  const typed = useTypewriter(typedWords)
  const steps = t('home.steps', { returnObjects: true }) as Step[]
  const services = useScrollRow<HTMLUListElement>()

  return (
    <main className="-mt-16 flex flex-1 flex-col bg-[#0a0a0a] text-white">
      {/*
        Présentation : le bloc fait la hauteur de l'écran, sous l'en-tête semi-transparent (4rem).
        Écran en largeur (ordinateur) : la photo entière est étirée pour remplir de gauche à droite.
        Écran en hauteur (téléphone, tablette debout) : elle garde ses proportions sur toute la
        largeur, et la même image floutée remplit le haut et le bas.
      */}
      <section className="relative overflow-hidden bg-[#0a0a0a]">
        <div
          aria-hidden="true"
          className="absolute inset-0 scale-110 bg-cover bg-center opacity-60 blur-2xl"
          style={{ backgroundImage: 'url(/mairie-bg.jpg)' }}
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[length:100%_auto] bg-center bg-no-repeat landscape:bg-[length:100%_100%]"
          style={{ backgroundImage: 'url(/mairie-bg.jpg)' }}
        />
        <div aria-hidden="true" className="absolute inset-0 bg-[#0a0a0a]/60" />
        <AnimatedBackground className="opacity-50" />

        <div className="relative flex min-h-svh items-center justify-center px-4 pb-16 pt-32 sm:px-6 lg:px-8">
          <div className="fx-rise relative mx-auto w-full max-w-3xl text-center">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">
              {t('home.kicker')}
            </p>

            <h1 className="mt-5 text-4xl font-black tracking-tight text-white sm:text-5xl md:text-6xl">
              {t('home.title')}
            </h1>

            <p className="mt-3 text-lg font-semibold text-white/80 sm:text-xl">{t('home.subtitle')}</p>

            {/* Mots qui s'écrivent puis s'effacent, comme sur l'accueil de l'administration */}
            <p className="mt-4 min-h-[2.5em] text-xl font-bold text-white sm:min-h-0 sm:text-2xl">
              {t('home.typedLead')}{' '}
              <span aria-hidden="true" className="text-white/55">{typed}</span>
              <span aria-hidden="true" className="typed-caret" />
              <span className="sr-only">{typedWords.join(', ')}</span>
            </p>

            <SiteSearchBar />
          </div>
        </div>
      </section>

      {/* Sous la photo : fond bleu sous un voile noir transparent, comme le pied de page */}
      <div className="bg-fond-voile relative overflow-hidden">
        <AnimatedBackground grid />
        {/* Services : une seule rangée, flèches gauche / droite */}
        <section className="relative bg-black/25 px-4 py-14 sm:px-6 sm:py-16 lg:px-8" aria-labelledby="home-services-title">
          <div className="mx-auto max-w-6xl">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div className="max-w-2xl">
                <h2 id="home-services-title" className="text-2xl font-black tracking-tight text-white sm:text-3xl">
                  {t('home.servicesTitle')}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-white/65 sm:text-base">{t('home.servicesIntro')}</p>
              </div>
              <div className="flex items-center gap-4">
                <Link
                  to="/services"
                  className="inline-flex items-center gap-1 text-sm font-semibold text-white/80 transition-colors hover:text-white"
                >
                  {t('home.allServices')}
                  <ChevronRightIcon className="size-4" />
                </Link>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => services.scroll(-1)}
                    disabled={!services.canPrev}
                    aria-label={t('home.prev')}
                    aria-controls="home-services"
                    className={arrowClass}
                  >
                    <ChevronLeftIcon className="size-5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => services.scroll(1)}
                    disabled={!services.canNext}
                    aria-label={t('home.next')}
                    aria-controls="home-services"
                    className={arrowClass}
                  >
                    <ChevronRightIcon className="size-5" />
                  </button>
                </div>
              </div>
            </div>

            <ul
              id="home-services"
              ref={services.trackRef}
              className="mt-8 grid snap-x snap-mandatory auto-cols-[85%] grid-flow-col gap-4 overflow-x-auto pb-2 [scrollbar-width:none] sm:auto-cols-[calc((100%-1rem)/2)] lg:auto-cols-[calc((100%-2rem)/3)] [&::-webkit-scrollbar]:hidden"
            >
              {SERVICE_SLUGS.map((slug) => {
                const type = slugToType(slug)
                return (
                  <li key={slug} className="snap-start">
                    <ServiceCard
                      to={publicPath(type)}
                      title={t(`catalog.types.${type}.title`)}
                      description={t(`catalog.types.${type}.description`)}
                      cta={t('servicesPage.viewService')}
                    />
                  </li>
                )
              })}
              <li className="snap-start">
                <ServiceCard
                  to="/services/etat-civil"
                  title={t('catalog.civil.title')}
                  description={t('catalog.civil.description')}
                  cta={t('servicesPage.viewService')}
                />
              </li>
            </ul>
          </div>
        </section>

        {/* Étapes */}
        <section className="relative px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
          <div className="mx-auto max-w-6xl">
            <SectionTitle title={t('home.stepsTitle')} />
            <ol className="mt-8 grid gap-4 md:grid-cols-3">
              {steps.map((step, index) => (
                <li key={step.title} className="rounded-2xl border border-white/15 bg-gradient-to-br from-white/[0.13] to-white/[0.03] shadow-lg shadow-black/20 backdrop-blur-md p-6">
                  <span className="grid size-10 place-items-center rounded-full bg-primary text-sm font-black text-primary-foreground">
                    {index + 1}
                  </span>
                  <h3 className="mt-4 text-lg font-bold">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-white/65">{step.text}</p>
                </li>
              ))}
            </ol>
            <div className="mt-8 flex justify-center">
              <Link to={ESPACE_HOME} className={actionClass('primary', 'lg')}>
                {t('home.ctaRequest')}
                <ChevronRightIcon className="size-4" />
              </Link>
            </div>
          </div>
        </section>

        {/* Vérification et aide */}
        <section className="relative bg-black/25 px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
          <div className="mx-auto grid max-w-6xl gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="flex flex-col gap-5 rounded-2xl border border-white/15 bg-gradient-to-br from-white/[0.13] to-white/[0.03] shadow-lg shadow-black/20 backdrop-blur-md p-6 sm:flex-row sm:items-center sm:p-8">
              <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-primary text-primary-foreground">
                <ScanIcon className="size-7" />
              </span>
              <div className="flex-1">
                <h2 className="text-xl font-bold">{t('home.verifyTitle')}</h2>
                <p className="mt-2 text-sm leading-relaxed text-white/65">{t('home.verifyText')}</p>
                {/* Affiché seulement : ne mène nulle part (non cliquable). */}
                <span className={actionClass('primary', 'md', 'mt-4 pointer-events-none cursor-default')}>
                  {t('home.ctaScan')}
                </span>
              </div>
            </div>

            <div className="rounded-2xl border border-white/15 bg-gradient-to-br from-white/[0.13] to-white/[0.03] shadow-lg shadow-black/20 backdrop-blur-md p-6 sm:p-8">
              <h2 className="text-xl font-bold">{t('home.helpTitle')}</h2>
              <p className="mt-2 text-sm leading-relaxed text-white/65">{t('home.helpText')}</p>
              <div className="mt-4 flex flex-wrap gap-3">
                <Link to="/contact" className={actionClass('outline')}>
                  <MailIcon className="size-4" />
                  {t('home.helpContact')}
                </Link>
                <Link to="/faq" className={actionClass('ghost')}>
                  {t('home.helpFaq')}
                </Link>
              </div>
              <Link
                to="/demande-agent"
                className="mt-5 inline-flex items-center gap-1 text-xs font-semibold text-white/60 transition-colors hover:text-white"
              >
                {t('home.ctaAgent')}
                <ChevronRightIcon className="size-3.5" />
              </Link>
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}

export default Home
