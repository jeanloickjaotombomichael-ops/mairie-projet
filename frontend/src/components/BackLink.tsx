import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { ArrowLeftIcon } from '@/components/icons'
import { cn } from '@/lib/utils'

interface BackLinkProps {
  /** Page de repli si l'on est arrivé directement sur cette page (lien partagé, QR code…). */
  fallback: string
  label?: string
  /** `site` : texte blanc sur le fond bleu ; `space` : couleurs de l'espace personnel. */
  variant?: 'site' | 'space'
  className?: string
}

/**
 * Bouton « Retour » : revient à la page précédente du site si elle existe,
 * sinon ouvre `fallback` (jamais vers un autre site).
 */
function BackLink({ fallback, label, variant = 'site', className }: BackLinkProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const goBack = (event: MouseEvent<HTMLAnchorElement>) => {
    // React Router numérote les entrées de l'historique : idx > 0 = une page du site avant celle-ci.
    const index = (window.history.state as { idx?: number } | null)?.idx ?? 0
    if (index > 0 && !event.metaKey && !event.ctrlKey) {
      event.preventDefault()
      navigate(-1)
    }
  }

  return (
    <Link
      to={fallback}
      onClick={goBack}
      className={cn(
        'inline-flex items-center gap-2 text-sm font-medium transition-colors',
        variant === 'site' ? 'text-white/70 hover:text-white' : 'd-page-link',
        className,
      )}
    >
      <ArrowLeftIcon className="size-4" />
      {label ?? t('common.back')}
    </Link>
  )
}

export default BackLink
