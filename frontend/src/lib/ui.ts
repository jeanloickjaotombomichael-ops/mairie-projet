import { cn } from '@/lib/utils'

/**
 * Classes Tailwind pour les liens/boutons "pleins" des pages.
 * Indépendant de `button.tsx` : un <Link> ou un <button type="submit">
 * garde ainsi un rendu identique sans dépendre de l'API du composant Base UI.
 */
const base =
  'inline-flex items-center justify-center gap-2 rounded-lg text-sm font-semibold whitespace-nowrap transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 disabled:pointer-events-none disabled:opacity-50'

const variants = {
  primary: 'bg-primary text-primary-foreground hover:bg-primary/85',
  outline: 'border border-white/25 bg-white/5 text-white hover:bg-white/10',
  ghost: 'text-white/80 hover:bg-white/10 hover:text-white',
} as const

const sizes = {
  md: 'h-10 px-4',
  lg: 'h-11 px-6',
} as const

export function actionClass(
  variant: keyof typeof variants = 'primary',
  size: keyof typeof sizes = 'md',
  extra?: string,
) {
  return cn(base, variants[variant], sizes[size], extra)
}
