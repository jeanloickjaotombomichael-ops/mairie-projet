import type { SVGProps } from 'react'

/**
 * Illustration de la page « Contact » : enveloppe ouverte, téléphone, bulle d'information,
 * tasse de café et personnage. Dessin vectoriel original (aucune image à charger).
 */
function ContactIllustration(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 460 340" role="img" aria-hidden="true" {...props}>
      {/* Décor : cercles, @ et feuilles */}
      <circle cx="46" cy="176" r="24" fill="#dbe8ff" />
      <circle cx="26" cy="262" r="5" fill="#bcd4ff" />
      <circle cx="430" cy="40" r="6" fill="#c9f0a8" />
      <circle cx="408" cy="300" r="4" fill="#cdbcff" />
      <text x="62" y="96" fontSize="30" fontWeight="700" fill="#3b82f6" fontFamily="system-ui, sans-serif">
        @
      </text>
      <ellipse cx="340" cy="40" rx="9" ry="20" fill="#9ccc65" transform="rotate(-35 340 40)" />
      <ellipse cx="362" cy="52" rx="8" ry="17" fill="#7cb342" transform="rotate(20 362 52)" />

      {/* Enveloppe : fond */}
      <rect x="110" y="120" width="250" height="172" rx="12" fill="#f2a71b" />

      {/* Lettre qui dépasse */}
      <rect x="136" y="58" width="198" height="156" rx="8" fill="#ffffff" stroke="#e5e7eb" />
      <g stroke="#d1d5db" strokeWidth="3" strokeLinecap="round">
        <path d="M158 88h154" />
        <path d="M158 108h154" />
        <path d="M158 128h154" />
        <path d="M158 148h110" />
      </g>

      {/* Enveloppe : poche avant */}
      <path
        d="M110 150 L235 236 L360 150 V280 a12 12 0 0 1 -12 12 H122 a12 12 0 0 1 -12 -12 Z"
        fill="#fbc34a"
      />
      <path d="M110 292 L205 215 M360 292 L265 215" stroke="#f2a71b" strokeWidth="3" strokeLinecap="round" />

      {/* Téléphone rouge et son cordon */}
      <path d="M72 112 C44 144 50 202 92 230" fill="none" stroke="#d6332b" strokeWidth="24" strokeLinecap="round" />
      <path d="M72 112 C44 144 50 202 92 230" fill="none" stroke="#ef5a4f" strokeWidth="6" strokeLinecap="round" />
      <path
        d="M96 232 q12 16 26 4 t26 4 t26 4"
        fill="none"
        stroke="#b3261e"
        strokeWidth="3"
        strokeLinecap="round"
      />

      {/* Bulle d'information */}
      <circle cx="204" cy="288" r="26" fill="#2b6fde" stroke="#ffffff" strokeWidth="4" />
      <circle cx="204" cy="278" r="3.2" fill="#ffffff" />
      <rect x="201" y="284" width="6" height="17" rx="3" fill="#ffffff" />

      {/* Tasse de café */}
      <ellipse cx="318" cy="312" rx="38" ry="9" fill="#e5e9f2" />
      <path d="M296 282 h44 v18 a22 22 0 0 1 -44 0 Z" fill="#ffffff" stroke="#e5e7eb" />
      <path d="M340 288 a10 10 0 0 1 0 18" fill="none" stroke="#e5e7eb" strokeWidth="4" strokeLinecap="round" />
      <ellipse cx="318" cy="283" rx="22" ry="4.5" fill="#8b5a2b" />

      {/* Personnage */}
      <rect x="388" y="190" width="14" height="96" rx="5" fill="#2f55b3" />
      <rect x="406" y="190" width="14" height="96" rx="5" fill="#2f55b3" />
      <rect x="384" y="282" width="21" height="9" rx="4" fill="#1f2937" />
      <rect x="403" y="282" width="21" height="9" rx="4" fill="#1f2937" />
      <rect x="380" y="116" width="48" height="84" rx="14" fill="#f08a3c" />
      <path d="M382 128 L350 98" stroke="#f4c7a1" strokeWidth="9" strokeLinecap="round" />
      <path d="M426 130 L440 176" stroke="#f4c7a1" strokeWidth="9" strokeLinecap="round" />
      <circle cx="404" cy="96" r="16" fill="#f4c7a1" />
      <path d="M388 94 a17 17 0 0 1 32 -4 c-6 -6 -18 -8 -32 4 Z" fill="#2b2118" />
    </svg>
  )
}

export default ContactIllustration
