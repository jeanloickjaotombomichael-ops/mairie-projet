import { useEffect, useState } from 'react'

/**
 * Écrit chaque mot lettre par lettre, le laisse affiché un instant, l'efface
 * puis passe au suivant (en boucle). Sans animation si l'utilisateur a
 * demandé de réduire les mouvements : le premier mot reste affiché.
 */
export function useTypewriter(words: string[]) {
  const [text, setText] = useState('')
  const key = words.join('|')

  useEffect(() => {
    if (!words.length) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setText(words[0])
      return
    }
    let word = 0
    let letters = 0
    let deleting = false
    let timer: number

    const step = () => {
      const current = words[word]
      letters += deleting ? -1 : 1
      setText(current.slice(0, letters))
      let delay = deleting ? 45 : 90
      if (!deleting && letters === current.length) {
        deleting = true
        delay = 1600
      } else if (deleting && letters === 0) {
        deleting = false
        word = (word + 1) % words.length
        delay = 350
      }
      timer = window.setTimeout(step, delay)
    }
    step()
    return () => window.clearTimeout(timer)
  }, [key])

  return text
}
