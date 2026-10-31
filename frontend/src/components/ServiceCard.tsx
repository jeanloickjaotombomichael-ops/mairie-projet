import { Link } from 'react-router'
import { ChevronRightIcon } from '@/components/icons'

interface ServiceCardProps {
  to: string
  title: string
  description: string
  cta: string
}

/** Carte cliquable d'un service (liste des services et de l'état civil), effet verre dépoli sur le fond bleu. */
function ServiceCard({ to, title, description, cta }: ServiceCardProps) {
  return (
    <Link
      to={to}
      className="group flex h-full flex-col rounded-2xl border border-white/15 bg-gradient-to-br from-white/[0.13] to-white/[0.03] shadow-lg shadow-black/20 backdrop-blur-md p-5 transition-all hover:-translate-y-0.5 hover:border-white/35 hover:from-white/[0.2] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
    >
      <h2 className="text-lg font-bold text-white">{title}</h2>
      <p className="mt-2 line-clamp-3 flex-1 text-sm leading-relaxed text-white/70">{description}</p>
      <span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary">
        {cta}
        <ChevronRightIcon className="size-3.5 transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  )
}

export default ServiceCard
