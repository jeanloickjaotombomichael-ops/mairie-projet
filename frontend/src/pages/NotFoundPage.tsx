import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import Backdrop from '@/components/Backdrop'
import { ArrowLeftIcon } from '@/components/icons'
import { actionClass } from '@/lib/ui'

function NotFoundPage() {
  const { t } = useTranslation()

  return (
    <Backdrop className="flex flex-1 items-center" back={{ to: '/', width: 'max-w-xl' }}>
      <div className="mx-auto w-full max-w-xl rounded-2xl border border-white/10 bg-[#0a0a0a]/85 p-8 text-center shadow-xl backdrop-blur-sm">
        <p className="text-6xl font-black tracking-tight text-primary">404</p>
        <h1 className="mt-3 text-2xl font-black tracking-tight text-white sm:text-3xl">
          {t('notFound.title')}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-white/70">{t('notFound.text')}</p>
        <Link to="/" className={actionClass('primary', 'lg', 'mt-6')}>
          <ArrowLeftIcon className="size-4" />
          {t('common.backHome')}
        </Link>
      </div>
    </Backdrop>
  )
}

export default NotFoundPage
