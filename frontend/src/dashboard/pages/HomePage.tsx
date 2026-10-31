import type { ComponentType, SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import BackLink from '@/components/BackLink'
import { DOSSIER_TYPES, isCivilType } from '@/data/catalog'
import RequestRow from '@/dashboard/RequestRow'
import { useDossiers } from '@/dashboard/dossiersContext'
import { BellIcon, FileIcon, InboxIcon, PlusIcon } from '@/dashboard/icons'

const SERVICE_TYPES = DOSSIER_TYPES.filter((type) => !isCivilType(type))
const CIVIL_TYPES = DOSSIER_TYPES.filter((type) => isCivilType(type))

interface StatCardProps {
  title: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  values: { value: number; label: string }[]
}

/** Carte de chiffres (non cliquable) ; le « + » est décoratif. */
function StatCard({ title, icon: Icon, values }: StatCardProps) {
  return (
    <div className="d-stat-card">
      <p className="flex min-w-0 items-center gap-2 text-sm font-semibold">
        <Icon className="size-5 shrink-0" aria-hidden="true" />
        {title}
      </p>
      <div className="mt-4 flex items-end justify-between gap-3">
        <dl className="flex gap-4 sm:gap-6">
          {values.map(({ value, label }) => (
            <div key={label} className="flex flex-col-reverse">
              <dt className="text-xs text-white/80">{label}</dt>
              <dd className="text-2xl font-extrabold leading-tight">{value}</dd>
            </div>
          ))}
        </dl>
        <span className="d-stat-plus max-sm:hidden" aria-hidden="true">
          <PlusIcon className="size-4" />
        </span>
      </div>
    </div>
  )
}

/** Accueil de l'espace : chiffres clés, puis les demandes et l'état civil en rangées défilantes. */
function HomePage() {
  const { t } = useTranslation()
  const { total, pending, done, unread } = useDossiers()

  return (
    <div className="mx-auto max-w-6xl space-y-10">
      <BackLink fallback="/" label={t('dash.nav.backToSite')} variant="space" className="-mb-4" />
      <section className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4" aria-label={t('dash.home.stats.requests')}>
        <StatCard
          title={t('dash.home.stats.requests')}
          icon={FileIcon}
          values={[
            { value: total, label: t('dash.home.stats.sent') },
            { value: pending, label: t('dash.home.stats.inProgress') },
          ]}
        />
        <StatCard
          title={t('dash.home.stats.responses')}
          icon={BellIcon}
          values={[
            { value: unread, label: t('dash.home.stats.unread') },
            { value: done, label: t('dash.home.stats.done') },
          ]}
        />
        <StatCard
          title={t('dash.home.stats.services')}
          icon={InboxIcon}
          values={[{ value: SERVICE_TYPES.length, label: t('dash.home.stats.procedures') }]}
        />
        <StatCard
          title={t('dash.home.stats.civil')}
          icon={FileIcon}
          values={[{ value: CIVIL_TYPES.length, label: t('dash.home.stats.acts') }]}
        />
      </section>

      <RequestRow id="row-services" title={t('dash.home.servicesTitle')} types={SERVICE_TYPES} />
      <RequestRow id="row-civil" title={t('dash.home.civilTitle')} types={CIVIL_TYPES} />
    </div>
  )
}

export default HomePage
