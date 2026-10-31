import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { Html5Qrcode } from 'html5-qrcode'
import Backdrop from '@/components/Backdrop'
import { CameraIcon, SpinnerIcon } from '@/components/icons'
import { actionClass } from '@/lib/ui'
import { cn } from '@/lib/utils'
import { extractUuid } from '@/lib/uuid'

const READER_ID = 'qr-reader'

type CameraState = 'idle' | 'starting' | 'scanning' | 'denied' | 'error' | 'insecure'

function isPermissionError(error: unknown): boolean {
  const text = error instanceof Error ? `${error.name} ${error.message}` : String(error)
  return /NotAllowed|Permission|denied/i.test(text)
}

function ScanPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const scannerRef = useRef<Html5Qrcode | null>(null)
  const handledRef = useRef(false)

  const [camera, setCamera] = useState<CameraState>('idle')
  const [unrecognized, setUnrecognized] = useState(false)
  const [manual, setManual] = useState('')
  const [manualError, setManualError] = useState(false)

  const stopCamera = useCallback(async () => {
    const scanner = scannerRef.current
    scannerRef.current = null
    if (!scanner) return
    try {
      await scanner.stop()
    } catch {
      // la caméra n'était pas (ou plus) démarrée
    }
    try {
      scanner.clear()
    } catch {
      // rien à nettoyer
    }
  }, [])

  // Libère la caméra quand on quitte la page.
  useEffect(() => {
    return () => {
      void stopCamera()
    }
  }, [stopCamera])

  const goToVerification = useCallback(
    (uuid: string) => {
      navigate(`/verifier/${uuid}`)
    },
    [navigate],
  )

  const startCamera = async () => {
    setUnrecognized(false)
    handledRef.current = false

    // getUserMedia n'existe qu'en HTTPS ou sur localhost.
    if (!window.isSecureContext) {
      setCamera('insecure')
      return
    }

    setCamera('starting')
    const scanner = new Html5Qrcode(READER_ID)
    scannerRef.current = scanner

    try {
      await scanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 240, height: 240 }, aspectRatio: 1 },
        (decodedText) => {
          if (handledRef.current) return

          // On ne réutilise JAMAIS le texte scanné comme adresse : seul l'UUID extrait compte.
          const uuid = extractUuid(decodedText)
          if (!uuid) {
            setUnrecognized(true)
            return
          }

          handledRef.current = true
          void stopCamera().then(() => goToVerification(uuid))
        },
        () => {
          // échec de lecture d'une image : normal, on continue de scanner
        },
      )
      setCamera('scanning')
    } catch (error) {
      scannerRef.current = null
      try {
        scanner.clear()
      } catch {
        // rien à nettoyer
      }
      setCamera(isPermissionError(error) ? 'denied' : 'error')
    }
  }

  const onManualSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const uuid = extractUuid(manual)
    if (!uuid) {
      setManualError(true)
      return
    }
    setManualError(false)
    void stopCamera().then(() => goToVerification(uuid))
  }

  const cameraMessage =
    camera === 'denied'
      ? t('scan.cameraDenied')
      : camera === 'error'
        ? t('scan.cameraError')
        : camera === 'insecure'
          ? t('scan.insecure')
          : null

  const cameraActive = camera === 'starting' || camera === 'scanning'

  return (
    <Backdrop className="flex flex-1 items-start justify-center sm:items-center" back={{ to: '/', width: 'max-w-md' }}>
      <div className="mx-auto w-full max-w-md rounded-2xl border border-white/15 bg-card/95 p-5 text-center shadow-2xl backdrop-blur sm:p-8">
        <img src="/logo-mahajanga.png" alt="" className="mx-auto h-14 w-14 object-contain" />
        <h1 className="mt-3 text-xl font-bold text-foreground">{t('scan.title')}</h1>
        <span className="mt-2 inline-block rounded-full border border-emerald-500/30 bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-300">
          {t('scan.badge')}
        </span>

        {/* Zone caméra : le conteneur existe toujours, la librairie y injecte la vidéo */}
        <div
          id={READER_ID}
          className={cn(
            'mx-auto mt-5 w-full overflow-hidden rounded-xl border-2 border-dashed border-emerald-600 bg-black',
            cameraActive ? 'block' : 'hidden',
          )}
        />

        {camera === 'starting' && (
          <p className="mt-4 flex items-center justify-center gap-2 text-sm text-muted-foreground" role="status">
            <SpinnerIcon className="size-4 animate-spin" />
            {t('scan.starting')}
          </p>
        )}

        {cameraMessage && (
          <p role="alert" className="mt-4 rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-xs leading-relaxed text-amber-200">
            {cameraMessage}
          </p>
        )}

        {unrecognized && camera === 'scanning' && (
          <p role="alert" className="mt-4 rounded-lg border border-red-500/25 bg-red-500/10 p-3 text-xs leading-relaxed text-red-300">
            {t('scan.unrecognized')}
          </p>
        )}

        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">{t('scan.instructions')}</p>

        <div className="mt-4">
          {cameraActive ? (
            <button
              type="button"
              onClick={() => {
                void stopCamera().then(() => setCamera('idle'))
              }}
              className={actionClass('outline', 'lg', 'w-full')}
            >
              {t('scan.stop')}
            </button>
          ) : (
            <button type="button" onClick={() => void startCamera()} className={actionClass('primary', 'lg', 'w-full')}>
              <CameraIcon className="size-4" />
              {t('scan.start')}
            </button>
          )}
        </div>

        {/* Saisie manuelle : indispensable si la caméra est refusée ou indisponible */}
        <form onSubmit={onManualSubmit} className="mt-6 border-t border-white/10 pt-5 text-left" noValidate>
          <label htmlFor="manual-id" className="text-sm font-semibold text-foreground">
            {t('scan.manualTitle')}
          </label>
          <p className="mt-1 text-xs text-muted-foreground">{t('scan.manualHelp')}</p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <input
              id="manual-id"
              type="text"
              value={manual}
              onChange={(event) => {
                setManual(event.target.value)
                setManualError(false)
              }}
              placeholder={t('scan.manualPlaceholder')}
              autoComplete="off"
              spellCheck={false}
              aria-invalid={manualError}
              className="h-10 w-full min-w-0 rounded-lg border border-white/15 bg-white/5 px-3 font-mono text-xs text-white placeholder:text-white/35 focus:border-white/40 focus:outline-none focus:ring-2 focus:ring-white/20 aria-invalid:border-red-400/70"
            />
            <button type="submit" className={actionClass('primary', 'md', 'sm:w-auto')}>
              {t('scan.manualButton')}
            </button>
          </div>
          {manualError && (
            <p role="alert" className="mt-2 text-xs text-red-300">
              {t('scan.manualError')}
            </p>
          )}
        </form>

        <Link to="/" className={actionClass('ghost', 'md', 'mt-5 w-full')}>
          {t('common.backHome')}
        </Link>
      </div>
    </Backdrop>
  )
}

export default ScanPage
