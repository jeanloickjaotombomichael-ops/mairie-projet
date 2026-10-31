import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { UserButton } from '@clerk/react'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import { ESPACE_HOME, ESPACE_NOTIFICATIONS } from '@/data/catalog'
import DashSearch from '@/dashboard/DashSearch'
import ThemeMenu from '@/dashboard/ThemeMenu'
import { useDossiers } from '@/dashboard/dossiersContext'
import { BellIcon, FileIcon, MenuIcon } from '@/dashboard/icons'
import type { ThemeId } from '@/dashboard/theme'

interface TopbarProps {
  theme: ThemeId
  onThemeChange: (theme: ThemeId) => void
  menuOpen: boolean
  onMenuToggle: () => void
}

/** Barre supérieure : menu, logo, recherche, apparence, langue, notifications et compte. */
function Topbar({ theme, onThemeChange, menuOpen, onMenuToggle }: TopbarProps) {
  const { t } = useTranslation()
  const { total, unread } = useDossiers()

  return (
    <header className="d-topbar sticky top-0 z-30 flex h-16 items-center gap-2 px-4 sm:gap-3 sm:px-6">
      <button
        type="button"
        className="d-icon-btn -ml-1"
        onClick={onMenuToggle}
        aria-expanded={menuOpen}
        aria-controls="dash-sidebar"
        aria-label={t('dash.sidebar.open')}
        title={t('dash.sidebar.open')}
      >
        <MenuIcon className="size-6" />
      </button>
      <Link to={ESPACE_HOME} className="flex shrink-0 items-center gap-2.5" aria-label={t('dash.nav.home')}>
        <img src="/logo-mahajanga.png" alt="" className="size-9 object-contain" />
        <span className="d-heading hidden max-w-40 text-sm font-extrabold leading-tight lg:block">
          {t('dash.brand')}
        </span>
      </Link>

      <DashSearch />

      <div className="ml-auto flex shrink-0 items-center gap-1 sm:gap-2">
        {/* Nombre de demandes envoyées (`.d-badge` fixe son display : on masque le conteneur) */}
        <span className="hidden sm:inline-flex">
          <Link
            to={ESPACE_NOTIFICATIONS}
            className="d-badge d-badge-progress"
            title={t('dash.topbar.requestsSent', { count: total })}
          >
            <FileIcon className="size-3.5" />
            {t('dash.topbar.requestsSent', { count: total })}
          </Link>
        </span>

        <ThemeMenu theme={theme} onChange={onThemeChange} />

        <LanguageSwitcher
          buttonClassName="d-lang-btn"
          menuClassName="d-popover"
          itemClassName="d-menu-item"
          activeItemClassName="d-menu-item-active"
          iconOnly
        />

        <Link
          to={ESPACE_NOTIFICATIONS}
          className="d-icon-btn"
          aria-label={
            unread > 0
              ? `${t('dash.topbar.notifications')} — ${t('dash.topbar.notificationsUnread', { count: unread })}`
              : t('dash.topbar.notifications')
          }
          title={t('dash.topbar.notifications')}
        >
          <BellIcon className="size-5" />
          {unread > 0 && <span className="d-count-badge">{unread > 9 ? '9+' : unread}</span>}
        </Link>

        <div className="ml-1 flex items-center">
          <UserButton />
        </div>
      </div>
    </header>
  )
}

export default Topbar
