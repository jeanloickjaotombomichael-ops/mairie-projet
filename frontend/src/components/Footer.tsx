import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { ArrowUp, Mail } from 'lucide-react'
import { FacebookIcon, InstagramIcon, YoutubeIcon } from '@/components/icons'
import { publicPath } from '@/data/catalog'

const COLUMNS = ['townhall', 'documents', 'verification', 'support'] as const
type ColumnKey = (typeof COLUMNS)[number]

/**
 * Destination de chaque lien de colonne, dans le même ordre que les libellés
 * des fichiers de traduction. `null` = libellé informatif, non cliquable
 * (pas de lien mort devant le jury).
 */
const COLUMN_LINKS: Record<ColumnKey, (string | null)[]> = {
  townhall: ['/faq', '/demande-agent', null, null],
  documents: [publicPath('naissance'), publicPath('mariage'), publicPath('deces'), null],
  verification: ['/scanner', '/scanner', null, null],
  support: ['/faq', '/contact', null, null],
}

function Footer() {
  const { t } = useTranslation()

  return (
    <footer className="bg-fond-voile border-t border-white/10 text-white">
      {/* Ligne d'infos pratiques */}
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 border-b border-white/10 px-4 py-6 text-center sm:grid-cols-3 sm:px-6 sm:text-left lg:px-8">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-widest text-white/50">
            {t('footer.hours')}
          </p>
          <p className="mt-1 text-xs font-bold uppercase tracking-wide text-white/90">
            {t('footer.hoursValue')}
          </p>
        </div>
        <div className="sm:text-center">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-white/50">
            {t('footer.address')}
          </p>
          <p className="mt-1 text-xs font-bold uppercase tracking-wide text-white/90">
            {t('footer.addressValue')}
          </p>
        </div>
        <div className="sm:text-right">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-white/50">
            {t('footer.follow')}
          </p>
          <p className="mt-1 text-xs font-bold uppercase tracking-wide text-white/90">
            {t('footer.followValue')}
          </p>
        </div>
      </div>

      {/* Marque + réseaux sociaux + contact */}
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-6 sm:px-6 lg:px-8">
        <p className="text-sm font-black tracking-tight">{t('footer.brand')}</p>
        <div className="flex items-center gap-1 text-white/70">
          <a href="#top" aria-label="Facebook" className="tap-target transition-colors hover:text-primary">
            <FacebookIcon className="size-[18px]" />
          </a>
          <a href="#top" aria-label="Instagram" className="tap-target transition-colors hover:text-primary">
            <InstagramIcon className="size-[18px]" />
          </a>
          <a href="#top" aria-label="YouTube" className="tap-target transition-colors hover:text-primary">
            <YoutubeIcon className="size-[18px]" />
          </a>
        </div>
        <Link
          to="/contact"
          className="inline-flex items-center gap-2 rounded-lg border border-white/20 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-white/10"
        >
          {t('footer.contactButton')}
          <Mail className="size-3.5" />
        </Link>
      </div>

      {/* Colonnes de liens */}
      <div className="mx-auto grid max-w-7xl grid-cols-2 gap-8 px-4 py-9 sm:px-6 md:grid-cols-4 lg:px-8">
        {COLUMNS.map((key) => {
          const items = t(`footer.columns.${key}.items`, { returnObjects: true }) as string[]
          return (
            <div key={key}>
              <h4 className="mb-3 text-sm font-bold text-white">{t(`footer.columns.${key}.title`)}</h4>
              <ul className="space-y-2.5">
                {items.map((item, index) => {
                  const to = COLUMN_LINKS[key][index] ?? null
                  return (
                    <li key={item}>
                      {to ? (
                        <Link to={to} className="text-xs text-white/60 transition-colors hover:text-primary">
                          {item}
                        </Link>
                      ) : (
                        <span className="text-xs text-white/60">{item}</span>
                      )}
                    </li>
                  )
                })}
              </ul>
            </div>
          )
        })}
      </div>

      {/* Bas de page */}
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 border-t border-white/10 px-4 py-6 sm:px-6 lg:px-8">
        <p className="max-w-xl text-[11px] leading-relaxed text-white/40">
          &copy; {new Date().getFullYear()} {t('footer.legal.copyright')}
        </p>
        <div className="flex flex-wrap gap-4 text-[11px] text-white/60">
          <span>{t('footer.legal.terms')}</span>
          <span>{t('footer.legal.privacy')}</span>
          <span>{t('footer.legal.security')}</span>
        </div>
        <a
          href="#top"
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/20 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-white/10"
        >
          {t('footer.legal.backToTop')}
          <ArrowUp className="size-3" />
        </a>
      </div>
    </footer>
  )
}

export default Footer
