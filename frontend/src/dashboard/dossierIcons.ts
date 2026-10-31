import {
  Baby,
  Building2,
  Bus,
  Files,
  Flower2,
  HandCoins,
  Heart,
  MapPinned,
  ReceiptText,
  Scale,
  Store,
  type LucideIcon,
} from 'lucide-react'
import type { DossierType } from '@/data/catalog'

/** Icône de chaque type de demande (cartes de l'accueil et en-tête du formulaire). */
export const DOSSIER_ICONS: Record<DossierType, LucideIcon> = {
  recette: HandCoins,
  transport: Bus,
  urbanisme: Building2,
  marche: Store,
  cadastre: MapPinned,
  impot_foncier: ReceiptText,
  naissance: Baby,
  mariage: Heart,
  deces: Flower2,
  legislation: Scale,
  actes_divers: Files,
}
