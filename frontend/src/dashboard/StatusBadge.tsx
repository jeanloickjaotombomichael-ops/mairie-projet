import { useTranslation } from 'react-i18next'
import type { DossierStatus } from '@/data/catalog'
import { cn } from '@/lib/utils'

const STATUS_CLASS: Record<DossierStatus, string> = {
  PENDING: 'd-badge-pending',
  IN_PROGRESS: 'd-badge-progress',
  APPROVED: 'd-badge-approved',
  REJECTED: 'd-badge-rejected',
  COMPLETED: 'd-badge-completed',
}

/** Pastille de statut d'une demande (couleur selon l'état). */
function StatusBadge({ status }: { status: DossierStatus }) {
  const { t } = useTranslation()
  return <span className={cn('d-badge', STATUS_CLASS[status])}>{t(`dash.status.${status}`)}</span>
}

export default StatusBadge
