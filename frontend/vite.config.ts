import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import net from 'node:net'
import path from 'node:path'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const BACKEND_DIR = path.resolve(import.meta.dirname, '../backend')
const BACKEND_PORT = 8000

/** Vrai si un serveur écoute déjà sur ce port (backend lancé à la main, par exemple). */
function portInUse(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port })
    socket.once('connect', () => {
      socket.destroy()
      resolve(true)
    })
    socket.once('error', () => resolve(false))
  })
}

/**
 * `npm run dev` démarre aussi le backend Django (http://localhost:8000) avec le Python
 * de l'environnement virtuel, sans avoir à l'activer, et l'arrête avec Vite.
 * Rien n'est lancé s'il tourne déjà, ou avec MAIRY_NO_BACKEND=1.
 */
function djangoBackend(): Plugin {
  let backend: ChildProcess | null = null
  return {
    name: 'mairy-django-backend',
    apply: 'serve',
    async configureServer(server) {
      const python = path.join(BACKEND_DIR, '.venv/bin/python')
      if (process.env.MAIRY_NO_BACKEND === '1') return
      if (!existsSync(python)) {
        server.config.logger.warn('[backend] .venv introuvable : voir « Lancer le backend » dans le README.')
        return
      }
      if (await portInUse(BACKEND_PORT)) {
        server.config.logger.info(`[backend] déjà en marche sur http://localhost:${BACKEND_PORT}`)
        return
      }
      backend = spawn(python, ['manage.py', 'runserver', String(BACKEND_PORT)], {
        cwd: BACKEND_DIR,
        stdio: 'inherit',
      })
      server.config.logger.info(`[backend] Django démarré sur http://localhost:${BACKEND_PORT}`)
      const stop = () => {
        backend?.kill()
        backend = null
      }
      server.httpServer?.once('close', stop)
      process.once('exit', stop)
      process.once('SIGINT', () => {
        stop()
        process.exit(0)
      })
      process.once('SIGTERM', () => {
        stop()
        process.exit(0)
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), djangoBackend()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
})
