import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@clerk/react'
import { DownloadIcon, FileIcon, SpinnerIcon } from '@/dashboard/icons'
import { downloadDossierDocument, type DossierDocument } from '@/lib/espaceApi'

interface DocumentDownloadsProps {
  dossierId: number
  documents: DossierDocument[] | undefined
}

/** Documents envoyés par l'agent pour une demande, avec un bouton « Télécharger » pour chacun. */
function DocumentDownloads({ dossierId, documents }: DocumentDownloadsProps) {
  const { t } = useTranslation()
  const { getToken } = useAuth()
  const [busy, setBusy] = useState<string | null>(null)
  const [failed, setFailed] = useState<string | null>(null)

  if (!documents || documents.length === 0) return null

  const download = async (document: DossierDocument) => {
    setBusy(document.id)
    setFailed(null)
    try {
      await downloadDossierDocument(getToken, dossierId, document)
    } catch {
      setFailed(document.id)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="mt-4">
      <p className="d-muted text-xs font-semibold uppercase tracking-wider">{t('dash.notifications.documentsTitle')}</p>
      <ul className="mt-2 space-y-2">
        {documents.map((document) => (
          <li key={document.id} className="d-doc-row">
            <FileIcon className="size-5 shrink-0" />
            <span className="d-heading min-w-0 flex-1 basis-40 break-words text-sm font-semibold sm:truncate">{document.label}</span>
            <button
              type="button"
              className="d-btn"
              onClick={() => void download(document)}
              disabled={busy === document.id}
              aria-label={`${t('dash.notifications.download')} — ${document.label}`}
            >
              {busy === document.id ? (
                <>
                  <SpinnerIcon className="size-4 animate-spin" />
                  {t('dash.notifications.downloading')}
                </>
              ) : (
                <>
                  <DownloadIcon className="size-4" />
                  {t('dash.notifications.download')}
                </>
              )}
            </button>
            {failed === document.id && (
              <p role="alert" className="d-error w-full">
                {t('dash.notifications.downloadError')}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default DocumentDownloads
