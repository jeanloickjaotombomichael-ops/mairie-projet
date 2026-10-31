import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import Backdrop from '@/components/Backdrop'
import { ArrowLeftIcon } from '@/components/icons'
import { actionClass } from '@/lib/ui'

interface ComingSoonPageProps {
  /** Clé sous `pages.*` dans les fichiers de traduction. */
  page: 'faq' | 'join'
}

function ComingSoonPage({ page }: ComingSoonPageProps) {
  const { t } = useTranslation()

  return (
    <Backdrop className="flex flex-1 items-center" back={{ to: '/', width: 'max-w-xl' }}>
      <div className="mx-auto w-full max-w-xl rounded-2xl border border-white/10 bg-[#0a0a0a]/85 p-8 text-center shadow-xl backdrop-blur-sm">
        <h1 className="text-2xl font-black tracking-tight text-white sm:text-3xl">
          {t(`pages.${page}.title`)}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-white/70">{t(`pages.${page}.text`)}</p>
        <Link to="/" className={actionClass('outline', 'lg', 'mt-6')}>
          <ArrowLeftIcon className="size-4" />
          {t('common.backHome')}
        </Link>
      </div>
    </Backdrop>
  )
}

export default ComingSoonPage
