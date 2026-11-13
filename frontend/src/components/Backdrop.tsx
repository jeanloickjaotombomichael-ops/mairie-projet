import type { ReactNode } from 'react'
import BackLink from '@/components/BackLink'
import { cn } from '@/lib/utils'

interface BackdropProps {
  children: ReactNode
  className?: string
  /** Bouton « Retour » en haut de la page : page de repli et largeur alignée sur le contenu. */
  back?: { to: string; label?: string; width?: string }
}

/**
 * Fond aux couleurs du blason partagé par les pages intérieures (classe `.bg-blason`, index.css),
 * identique à celui de l'espace usager.
 * Il remonte sous l'en-tête semi-transparent (-mt-16) ; le haut est compensé dans le padding.
 */
function Backdrop({ children, className, back }: BackdropProps) {
  return (
    <main className={cn('bg-blason relative -mt-16 overflow-hidden px-4 pb-10 pt-26 sm:px-6 sm:pb-14 sm:pt-30 lg:px-8', className)}>
      <div className={cn('relative', back && 'w-full')}>
        {back && (
          <div className={cn('mx-auto mb-5', back.width ?? 'max-w-6xl')}>
            <BackLink fallback={back.to} label={back.label} />
          </div>
        )}
        {children}
      </div>
    </main>
  )
}

export default Backdrop
