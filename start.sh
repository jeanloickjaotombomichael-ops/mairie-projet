#!/usr/bin/env bash
# Lance le frontend (http://localhost:5173) ; Vite démarre aussi le backend Django
# (http://localhost:8000, voir vite.config.ts). Ctrl+C arrête les deux.
set -e
cd "$(dirname "$0")/frontend"
npm run dev
