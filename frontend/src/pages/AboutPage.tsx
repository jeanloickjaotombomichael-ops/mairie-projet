import type { LucideIcon } from 'lucide-react'
import {
  Building2,
  Bus,
  Eye,
  FileText,
  Handshake,
  HeartHandshake,
  Landmark,
  Laptop,
  Leaf,
  MapPinned,
  Scale,
  ShieldCheck,
  Store,
  Target,
  Users,
  Wallet,
} from 'lucide-react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import Backdrop from '@/components/Backdrop'
import { ESPACE_HOME } from '@/data/catalog'
import { actionClass } from '@/lib/ui'

interface Item {
  title: string
  text: string
}

/** Icônes des missions, dans l'ordre de `about.missions.items`. */
const MISSION_ICONS: LucideIcon[] = [FileText, MapPinned, Wallet, Store, Bus, Leaf, HeartHandshake, ShieldCheck, Scale]

/** Icônes des objectifs, dans l'ordre de `about.goals.items`. */
const GOAL_ICONS: LucideIcon[] = [Users, Eye, Laptop, Building2, Handshake]

const cardClass = 'rounded-2xl border border-white/10 bg-[#0a0a0a]/70 p-5 shadow-lg backdrop-blur-sm'

function SectionTitle({ id, icon: Icon, title, intro }: { id: string; icon: LucideIcon; title: string; intro?: string }) {
  return (
    <div className="max-w-2xl">
      <h2 id={id} className="flex items-center gap-2.5 text-2xl font-black tracking-tight text-white sm:text-3xl">
        <Icon className="size-6 shrink-0 text-primary" aria-hidden="true" />
        {title}
      </h2>
      {intro && <p className="mt-2 text-sm leading-relaxed text-white/75 sm:text-base">{intro}</p>}
    </div>
  )
}

/** Présentation de la Commune : rôle, missions, objectifs, valeurs et plateforme numérique. */
function AboutPage() {
  const { t } = useTranslation()
  const missions = t('about.missions.items', { returnObjects: true }) as Item[]
  const goals = t('about.goals.items', { returnObjects: true }) as Item[]
  const values = t('about.values.items', { returnObjects: true }) as Item[]
  const digital = t('about.digital.items', { returnObjects: true }) as string[]

  return (
    <Backdrop className="flex-1" back={{ to: '/' }}>
      <div className="mx-auto max-w-6xl space-y-14 sm:space-y-16">
        <header className="max-w-3xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">{t('about.kicker')}</p>
          <h1 className="mt-3 text-3xl font-black tracking-tight text-white sm:text-4xl md:text-5xl">
            {t('about.title')}
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-white/80 sm:text-base">{t('about.intro')}</p>
        </header>

        <section className={`${cardClass} grid gap-6 p-6 sm:p-8 md:grid-cols-[auto_1fr]`} aria-labelledby="about-mission">
          <span className="grid size-14 place-items-center rounded-2xl bg-primary/15 text-primary">
            <Landmark className="size-7" aria-hidden="true" />
          </span>
          <div>
            <h2 id="about-mission" className="text-xl font-black text-white sm:text-2xl">
              {t('about.mission.title')}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-white/80 sm:text-base">{t('about.mission.text')}</p>
          </div>
        </section>

        <section aria-labelledby="about-missions">
          <SectionTitle id="about-missions" icon={Building2} title={t('about.missions.title')} intro={t('about.missions.intro')} />
          <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {missions.map((item, index) => {
              const Icon = MISSION_ICONS[index] ?? FileText
              return (
                <li key={item.title} className={cardClass}>
                  <Icon className="size-6 text-primary" aria-hidden="true" />
                  <h3 className="mt-3 text-base font-bold text-white">{item.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-white/70">{item.text}</p>
                </li>
              )
            })}
          </ul>
        </section>

        <section aria-labelledby="about-goals">
          <SectionTitle id="about-goals" icon={Target} title={t('about.goals.title')} intro={t('about.goals.intro')} />
          <ol className="mt-6 grid gap-4 md:grid-cols-2">
            {goals.map((item, index) => {
              const Icon = GOAL_ICONS[index] ?? Target
              return (
                <li key={item.title} className={`${cardClass} flex gap-4`}>
                  <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-white/10 text-primary">
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <div>
                    <h3 className="text-base font-bold text-white">
                      <span className="mr-1.5 text-primary">{index + 1}.</span>
                      {item.title}
                    </h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-white/70">{item.text}</p>
                  </div>
                </li>
              )
            })}
          </ol>
        </section>

        <section aria-labelledby="about-values">
          <SectionTitle id="about-values" icon={HeartHandshake} title={t('about.values.title')} />
          <ul className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {values.map((item) => (
              <li key={item.title} className={cardClass}>
                <h3 className="text-base font-bold text-primary">{item.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-white/70">{item.text}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className={`${cardClass} p-6 sm:p-8`} aria-labelledby="about-digital">
          <SectionTitle id="about-digital" icon={Laptop} title={t('about.digital.title')} intro={t('about.digital.intro')} />
          <ul className="mt-5 grid gap-2.5 sm:grid-cols-2">
            {digital.map((line) => (
              <li key={line} className="flex gap-2.5 text-sm leading-relaxed text-white/80">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                {line}
              </li>
            ))}
          </ul>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <Link to={ESPACE_HOME} className={actionClass('primary', 'lg')}>
              {t('about.cta.request')}
            </Link>
            <Link to="/contact" className={actionClass('outline', 'lg')}>
              {t('about.cta.contact')}
            </Link>
          </div>
        </section>
      </div>
    </Backdrop>
  )
}

export default AboutPage
