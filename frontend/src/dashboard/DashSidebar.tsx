import { useEffect, useRef, type ComponentType, type SVGProps } from 'react'
import { Link, NavLink } from 'react-router'
import { useTranslation } from 'react-i18next'
import { ESPACE_HOME, ESPACE_MAIL, ESPACE_NOTIFICATIONS } from '@/data/catalog'
import { useMails } from '@/dashboard/espaceContext'
import { useDossiers } from '@/dashboard/dossiersContext'
import {
  ArrowLeftIcon,
  BuildingIcon,
  CloseIcon,
  FileIcon,
  HomeIcon,
  MailIcon,
  MessageIcon,
  PhoneIcon,
  QrIcon,
  SparklesIcon,
} from '@/dashboard/icons'

interface DashSidebarProps {
  open: boolean
  onClose: () => void
  onOpenAssistant: () => void
}

type Icon = ComponentType<SVGProps<SVGSVGElement>>

interface Entry {
  label: string
  hint?: string
  icon: Icon
  to: string | { pathname: string; hash: string }
  badge?: number
  end?: boolean
}

/** Menu latéral de l'espace usager, ouvert par le bouton « hamburger » de la barre supérieure. */
function DashSidebar({ open, onClose, onOpenAssistant }: DashSidebarProps) {
  const { t } = useTranslation()
  const { unread: unreadResponses } = useDossiers()
  const { unread: unreadMails } = useMails()
  const panelRef = useRef<HTMLElement>(null)

  // Échap ferme le menu ; le focus va dans le panneau à l'ouverture.
  useEffect(() => {
    if (!open) return
    panelRef.current?.querySelector<HTMLElement>('a, button')?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  const sections: { title: string; entries: Entry[] }[] = [
    {
      title: t('dash.sidebar.space'),
      entries: [
        { label: t('dash.sidebar.home'), icon: HomeIcon, to: ESPACE_HOME, end: true },
        {
          label: t('dash.sidebar.messages'),
          hint: t('dash.sidebar.messagesHint'),
          icon: MessageIcon,
          to: ESPACE_NOTIFICATIONS,
          badge: unreadResponses,
        },
        {
          label: t('dash.sidebar.mail'),
          hint: t('dash.sidebar.mailHint'),
          icon: MailIcon,
          to: ESPACE_MAIL,
          badge: unreadMails,
        },
      ],
    },
    {
      title: t('dash.sidebar.procedures'),
      entries: [
        { label: t('dash.home.servicesTitle'), icon: FileIcon, to: { pathname: ESPACE_HOME, hash: '#row-services-title' } },
        { label: t('dash.home.civilTitle'), icon: BuildingIcon, to: { pathname: ESPACE_HOME, hash: '#row-civil-title' } },
      ],
    },
    {
      title: t('dash.sidebar.townHall'),
      entries: [
        { label: t('dash.sidebar.verify'), icon: QrIcon, to: '/scanner' },
        { label: t('dash.sidebar.contact'), icon: PhoneIcon, to: '/contact' },
        { label: t('dash.nav.backToSite'), icon: ArrowLeftIcon, to: '/' },
      ],
    },
  ]

  return (
    <div className={`d-drawer-root${open ? ' is-open' : ''}`} aria-hidden={!open}>
      <div className="d-drawer-scrim" onClick={onClose} />
      <nav
        ref={panelRef}
        id="dash-sidebar"
        className="d-drawer"
        aria-label={t('dash.sidebar.label')}
        inert={!open}
      >
        <div className="d-drawer-head">
          <Link to={ESPACE_HOME} className="flex min-w-0 items-center gap-2.5" onClick={onClose}>
            <img src="/logo-mahajanga.png" alt="" className="size-9 object-contain" />
            <span className="d-heading text-sm font-extrabold leading-tight">{t('dash.brand')}</span>
          </Link>
          <button type="button" className="d-icon-btn ml-auto" onClick={onClose} aria-label={t('dash.sidebar.close')}>
            <CloseIcon className="size-5" />
          </button>
        </div>

        <div className="d-drawer-body">
          {sections.map((section, index) => (
            <div key={section.title} className="d-drawer-section">
              <h2 className="d-drawer-title">{section.title}</h2>
              <ul>
                {section.entries.map((entry) => (
                  <li key={entry.label}>
                    <NavLink
                      to={entry.to}
                      end={entry.end}
                      onClick={onClose}
                      className={({ isActive }) =>
                        `d-drawer-link${isActive && typeof entry.to === 'string' ? ' is-active' : ''}`
                      }
                    >
                      <entry.icon className="size-5 shrink-0" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate">{entry.label}</span>
                        {entry.hint && <span className="d-drawer-hint">{entry.hint}</span>}
                      </span>
                      {!!entry.badge && <span className="d-drawer-badge">{entry.badge > 99 ? '99+' : entry.badge}</span>}
                    </NavLink>
                  </li>
                ))}
                {index === 0 && (
                  <li>
                    <button
                      type="button"
                      className="d-drawer-link"
                      onClick={() => {
                        onClose()
                        onOpenAssistant()
                      }}
                    >
                      <SparklesIcon className="size-5 shrink-0" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate">{t('dash.sidebar.assistant')}</span>
                        <span className="d-drawer-hint">{t('dash.sidebar.assistantHint')}</span>
                      </span>
                    </button>
                  </li>
                )}
              </ul>
            </div>
          ))}
        </div>
      </nav>
    </div>
  )
}

export default DashSidebar
