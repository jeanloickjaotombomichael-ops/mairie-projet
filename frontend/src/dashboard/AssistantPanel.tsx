import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@clerk/react'
import { askAssistant, type AssistantItem } from '@/lib/espaceApi'
import { CloseIcon, SendIcon, SparklesIcon } from '@/dashboard/icons'

interface Entry {
  from: 'me' | 'bot'
  text: string
  items?: AssistantItem[]
}

interface AssistantPanelProps {
  open: boolean
  onClose: () => void
}

const STORAGE_KEY = 'mairy-espace-assistant'

function readHistory(): Entry[] {
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) ?? '[]') as unknown
    return Array.isArray(saved) ? (saved as Entry[]) : []
  } catch {
    return []
  }
}

/** Assistant IA de l'espace usager : suivi des demandes, réponses, documents, démarches. */
function AssistantPanel({ open, onClose }: AssistantPanelProps) {
  const { t } = useTranslation()
  const { getToken } = useAuth()
  const [history, setHistory] = useState<Entry[]>(readHistory)
  const [draft, setDraft] = useState('')
  const [waiting, setWaiting] = useState(false)
  const logRef = useRef<HTMLOListElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const welcome: Entry = { from: 'bot', text: t('dash.assistant.welcome') }
  const shown = history.length ? history : [welcome]
  const suggestions = [
    t('dash.assistant.suggestStatus'),
    t('dash.assistant.suggestDocuments'),
    t('dash.assistant.suggestProcedure'),
  ]

  useEffect(() => {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-30)))
    } catch {
      // stockage indisponible : l'historique reste en mémoire
    }
  }, [history])

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight })
  }, [history, waiting, open])

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  const send = async (message: string) => {
    const text = message.trim()
    if (!text || waiting) return
    setDraft('')
    setHistory((current) => [...current, { from: 'me', text }])
    setWaiting(true)
    try {
      const reply = await askAssistant(getToken, text)
      setHistory((current) => [...current, { from: 'bot', text: reply.text, items: reply.items }])
    } catch {
      setHistory((current) => [...current, { from: 'bot', text: t('dash.assistant.error') }])
    } finally {
      setWaiting(false)
    }
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    void send(draft)
  }

  if (!open) return null

  return (
    <section className="d-assistant d-popover" role="dialog" aria-label={t('dash.sidebar.assistant')}>
      <header className="d-assistant-head">
        <span className="d-assistant-avatar">
          <SparklesIcon className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <strong className="block text-sm">{t('dash.sidebar.assistant')}</strong>
          <span className="d-muted block text-xs">{t('dash.assistant.subtitle')}</span>
        </div>
        {history.length > 0 && (
          <button type="button" className="d-btn-ghost !px-2 !py-1" onClick={() => setHistory([])}>
            {t('dash.assistant.clear')}
          </button>
        )}
        <button type="button" className="d-icon-btn" onClick={onClose} aria-label={t('dash.sidebar.close')}>
          <CloseIcon className="size-5" />
        </button>
      </header>

      <ol ref={logRef} className="d-assistant-log" aria-live="polite">
        {shown.map((entry, index) => (
          <li key={index} className={`d-assistant-msg ${entry.from === 'me' ? 'is-me' : 'is-bot'}`}>
            <div className="d-assistant-bubble">{entry.text}</div>
            {entry.items
              ?.filter((item) => item.url.startsWith('/'))
              .map((item) => (
                <Link key={item.url + item.label} to={item.url} className="d-assistant-item" onClick={onClose}>
                  <strong>{item.label}</strong>
                  {item.meta && <span className="d-muted">{item.meta}</span>}
                </Link>
              ))}
          </li>
        ))}
        {waiting && (
          <li className="d-assistant-msg is-bot">
            <div className="d-assistant-bubble d-assistant-typing" aria-label={t('dash.assistant.thinking')}>
              <span />
              <span />
              <span />
            </div>
          </li>
        )}
      </ol>

      {history.length === 0 && (
        <div className="d-assistant-suggestions">
          {suggestions.map((text) => (
            <button key={text} type="button" className="d-btn-ghost" onClick={() => void send(text)}>
              {text}
            </button>
          ))}
        </div>
      )}

      <form className="d-assistant-form" onSubmit={onSubmit}>
        <label htmlFor="d-assistant-input" className="sr-only">
          {t('dash.assistant.inputLabel')}
        </label>
        <input
          ref={inputRef}
          id="d-assistant-input"
          className="d-input"
          value={draft}
          maxLength={1000}
          autoComplete="off"
          placeholder={t('dash.assistant.placeholder')}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button type="submit" className="d-btn !px-3" disabled={!draft.trim() || waiting} aria-label={t('dash.assistant.send')}>
          <SendIcon className="size-4" />
        </button>
      </form>
    </section>
  )
}

export default AssistantPanel
