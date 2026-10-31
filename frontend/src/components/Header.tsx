import { useRef, useState } from 'react'
import { Link, NavLink } from 'react-router'
import { useTranslation } from 'react-i18next'
import { SignInButton, UserButton, useAuth } from '@clerk/react'
import { Menu, UserRound, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import ServicesMenu from '@/components/ServicesMenu'
import { ChevronDownIcon } from '@/components/icons'
import { CIVIL_SLUGS, ESPACE_HOME, SERVICE_SLUGS, publicPath, slugToType } from '@/data/catalog'
import { API_URL } from '@/lib/api'
import { cn } from '@/lib/utils'

const LANGUAGES = [
  { code: 'fr', label: 'FR' },
  { code: 'en', label: 'EN' },
  { code: 'mg', label: 'MLG' },
] as const

const desktopLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'text-sm font-medium transition-colors hover:text-white',
    isActive ? 'text-white' : 'text-white/70',
  )

const mobileLinkClass =
  'block rounded-lg px-3 py-2.5 text-sm font-medium text-white/80 hover:bg-white/10 hover:text-white'

/**
 * Raccourci vers l'administration : 20 appuis rapides sur l'icône de profil ouvrent la page
 * d'accueil du backend (le serveur Django doit tourner ; la connexion à l'admin reste exigée).
 */
const BACKEND_TAPS = 20
// 127.0.0.1 plutôt que localhost : c'est l'adresse affichée par runserver, celle où le
// navigateur a enregistré les identifiants (il les classe par adresse exacte).
const BACKEND_HOME = `${API_URL.replace('//localhost', '//127.0.0.1')}/`
const TAP_GAP_MS = 1500

const profileIconClass =
  'inline-flex size-8 shrink-0 items-center justify-center rounded-full border border-white/15 bg-white/10 text-white/80 transition-colors hover:bg-white/20 hover:text-white'

const mobileSubLinkClass =
  'block rounded-lg px-3 py-2 text-sm text-white/70 hover:bg-white/10 hover:text-white'

function Header() {
  const { t, i18n } = useTranslation()
  // « Se connecter » reste visible tant que l'usager n'est pas connecté, même pendant le chargement de Clerk.
  const { isSignedIn } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [servicesOpen, setServicesOpen] = useState(false)
  const [civilOpen, setCivilOpen] = useState(false)
  const taps = useRef({ count: 0, last: 0 })

  const tapProfile = () => {
    const now = Date.now()
    taps.current.count = now - taps.current.last > TAP_GAP_MS ? 1 : taps.current.count + 1
    taps.current.last = now
    if (taps.current.count >= BACKEND_TAPS) {
      taps.current.count = 0
      window.location.assign(BACKEND_HOME)
    }
  }

  const profileButton = (
    <button type="button" onClick={tapProfile} aria-label={t('header.profile')} className={profileIconClass}>
      <UserRound className="size-4" />
    </button>
  )

  const closeMobile = () => {
    setMobileOpen(false)
    setServicesOpen(false)
    setCivilOpen(false)
  }

  const changeLanguage = (code: string) => {
    void i18n.changeLanguage(code)
  }

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-black/55 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex min-w-0 items-center gap-3" onClick={closeMobile}>
          <img
            src="/logo-mahajanga.png"
            alt="Blason de Mahajanga"
            className="h-9 w-9 shrink-0 object-contain"
          />
          <span className="truncate text-sm font-black leading-tight tracking-tight text-white lg:text-base">
            Commune Urbaine de Mahajanga<span className="text-primary">.</span>
          </span>
        </Link>

        {/* Navigation — ordinateur et tablette */}
        <nav aria-label="Navigation principale" className="hidden shrink-0 items-center gap-5 md:flex lg:gap-8">
          <NavLink to="/" end className={desktopLinkClass}>
            {t('header.nav.home')}
          </NavLink>
          <ServicesMenu />
          <NavLink to="/a-propos" className={desktopLinkClass}>
            {t('header.nav.about')}
          </NavLink>
          <NavLink to="/contact" className={desktopLinkClass}>
            {t('header.nav.contact')}
          </NavLink>
        </nav>

        <div className="hidden shrink-0 items-center gap-3 md:flex">
          <LanguageSwitcher />

          {isSignedIn ? (
            <>
              <Link
                to={ESPACE_HOME}
                className="inline-flex h-8 items-center rounded-lg bg-white/10 px-3 text-xs font-semibold text-white transition-colors hover:bg-white/20"
              >
                {t('nav.mySpace')}
              </Link>
              <UserButton />
            </>
          ) : (
            <>
              {profileButton}
              <SignInButton mode="modal">
                <Button variant="secondary" size="sm">
                  {t('header.login')}
                </Button>
              </SignInButton>
            </>
          )}
        </div>

        {/* Bouton menu — téléphone : regroupe navigation, langue et connexion */}
        <button
          type="button"
          className="inline-flex shrink-0 items-center justify-center rounded-lg p-2 text-white md:hidden"
          aria-label={mobileOpen ? t('header.menuClose') : t('header.menuOpen')}
          aria-expanded={mobileOpen}
          onClick={() => (mobileOpen ? closeMobile() : setMobileOpen(true))}
        >
          {mobileOpen ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </div>

      {/* Panneau mobile */}
      {mobileOpen && (
        <div className="max-h-[calc(100svh_-_4rem)] overflow-y-auto border-t border-white/10 bg-black/35 px-4 pb-5 pt-3 md:hidden">
          <nav aria-label="Navigation principale" className="flex flex-col gap-1">
            <NavLink to="/" end onClick={closeMobile} className={mobileLinkClass}>
              {t('header.nav.home')}
            </NavLink>

            <div>
              <button
                type="button"
                aria-expanded={servicesOpen}
                onClick={() => setServicesOpen((value) => !value)}
                className={cn(mobileLinkClass, 'flex w-full items-center justify-between text-left')}
              >
                {t('header.nav.services')}
                <ChevronDownIcon className={cn('size-4 transition-transform', servicesOpen && 'rotate-180')} />
              </button>

              {servicesOpen && (
                <div className="ml-3 mt-1 flex flex-col gap-0.5 border-l border-white/10 pl-3">
                  <Link to="/services" onClick={closeMobile} className={cn(mobileSubLinkClass, 'font-semibold text-white')}>
                    {t('catalog.backToServices')}
                  </Link>

                  {SERVICE_SLUGS.map((slug) => {
                    const type = slugToType(slug)
                    return (
                      <Link key={slug} to={publicPath(type)} onClick={closeMobile} className={mobileSubLinkClass}>
                        {t(`catalog.types.${type}.title`)}
                      </Link>
                    )
                  })}

                  <button
                    type="button"
                    aria-expanded={civilOpen}
                    onClick={() => setCivilOpen((value) => !value)}
                    className={cn(mobileSubLinkClass, 'flex w-full items-center justify-between text-left')}
                  >
                    {t('catalog.civil.title')}
                    <ChevronDownIcon className={cn('size-4 transition-transform', civilOpen && 'rotate-180')} />
                  </button>

                  {civilOpen && (
                    <div className="ml-3 flex flex-col gap-0.5 border-l border-white/10 pl-3">
                      {CIVIL_SLUGS.map((slug) => {
                        const type = slugToType(slug)
                        return (
                          <Link key={slug} to={publicPath(type)} onClick={closeMobile} className={mobileSubLinkClass}>
                            {t(`catalog.types.${type}.title`)}
                          </Link>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>

            <NavLink to="/a-propos" onClick={closeMobile} className={mobileLinkClass}>
              {t('header.nav.about')}
            </NavLink>

            <NavLink to="/contact" onClick={closeMobile} className={mobileLinkClass}>
              {t('header.nav.contact')}
            </NavLink>
          </nav>

          {/* Sélecteur de langue mobile */}
          <div className="mt-3 flex items-center gap-2 border-t border-white/10 pt-3">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                type="button"
                onClick={() => changeLanguage(lang.code)}
                aria-pressed={i18n.language === lang.code}
                className={cn(
                  'flex-1 rounded-lg border px-2 py-2 text-xs font-semibold transition-colors',
                  i18n.language === lang.code
                    ? 'border-primary text-primary'
                    : 'border-white/15 text-white/70',
                )}
              >
                {lang.label}
              </button>
            ))}
          </div>

          <div className="mt-3 border-t border-white/10 pt-3">
            {isSignedIn ? (
              <div className="flex items-center justify-center gap-3">
                <Link
                  to={ESPACE_HOME}
                  onClick={closeMobile}
                  className="inline-flex h-9 items-center rounded-lg bg-white/10 px-4 text-sm font-semibold text-white hover:bg-white/20"
                >
                  {t('nav.mySpace')}
                </Link>
                <UserButton />
              </div>
            ) : (
              <div className="flex items-center gap-2">
                {profileButton}
                <SignInButton mode="modal">
                  <Button variant="secondary" size="sm" className="flex-1">
                    {t('header.login')}
                  </Button>
                </SignInButton>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  )
}

export default Header
