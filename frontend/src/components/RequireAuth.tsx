import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { SignInButton, useAuth } from '@clerk/react'
import { SpinnerIcon } from '@/components/icons'
import { actionClass } from '@/lib/ui'

/** Réserve une page aux usagers connectés ; les autres voient une invitation à se connecter. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const { isLoaded, isSignedIn } = useAuth()

  if (!isLoaded) {
    return (
      <div role="status" className="full-height grid place-items-center bg-[#0a0a0a] text-white">
        <SpinnerIcon className="size-7 animate-spin" />
        <span className="sr-only">{t('auth.loading')}</span>
      </div>
    )
  }

  if (!isSignedIn) {
    return (
      <main className="full-height grid place-items-center bg-[#0a0a0a] px-4 text-white">
        <div className="w-full max-w-md rounded-2xl border border-white/10 bg-white/5 p-8 text-center">
          <img
            src="/logo-mahajanga.png"
            alt=""
            className="mx-auto size-14 object-contain"
          />
          <h1 className="mt-4 text-xl font-black tracking-tight">{t('auth.requiredTitle')}</h1>
          <p className="mt-2 text-sm leading-relaxed text-white/70">{t('auth.requiredText')}</p>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <SignInButton mode="modal">
              <button type="button" className={actionClass('primary', 'lg')}>
                {t('auth.signIn')}
              </button>
            </SignInButton>
            <Link to="/" className={actionClass('outline', 'lg')}>
              {t('common.backHome')}
            </Link>
          </div>
        </div>
      </main>
    )
  }

  return <>{children}</>
}

export default RequireAuth
