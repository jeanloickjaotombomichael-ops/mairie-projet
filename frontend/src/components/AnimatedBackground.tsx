import { cn } from '@/lib/utils'

interface AnimatedBackgroundProps {
  /** `grid` ajoute une grille lumineuse discrète (pages intérieures). */
  grid?: boolean
  className?: string
}

/**
 * Animations décoratives du fond (style « getlayer ») : halos colorés qui flottent lentement,
 * grille discrète et reflet qui balaie l'écran. À placer en premier dans un conteneur
 * `relative` ; le contenu qui suit doit être `relative` pour passer au-dessus.
 * Tout s'arrête si l'utilisateur a demandé de réduire les animations (index.css).
 */
function AnimatedBackground({ grid = false, className }: AnimatedBackgroundProps) {
  return (
    <div aria-hidden="true" className={cn('fx-layer', className)}>
      <span className="fx-glow fx-glow-1" />
      <span className="fx-glow fx-glow-2" />
      <span className="fx-glow fx-glow-3" />
      {grid && <span className="fx-grid" />}
      <span className="fx-sweep" />
    </div>
  )
}

export default AnimatedBackground
