#!/bin/bash
# AI Content Empire quick launcher for macOS

set -euo pipefail

REPO_DIR="/Users/bluewirks.max/dev/apps/Empire"
BACKEND_PORT=8800
FRONTEND_PORT=3000
BACKEND_APP_MODULE="${BACKEND_APP_MODULE:-backend.main:app}"

echo "🚀 Starting AI Content Empire..."
echo "ℹ︎ Backend module: ${BACKEND_APP_MODULE}"

# Clear existing app ports so the launcher always brings up fresh processes.
# Port 8000 is included because older builds used it and any leftover process
# would let the frontend hit a stale backend (empty presets == "old UI").
for port in 8000 ${BACKEND_PORT} ${FRONTEND_PORT}; do
    lsof -ti:${port} | xargs kill -9 2>/dev/null || true
done

echo "✓ Ports 8000, ${BACKEND_PORT} and ${FRONTEND_PORT} cleared"

# Drop the Next.js build cache so the UI picks up the latest components/presets
# on every launch (stale .next was shipping the old panel layout).
rm -rf "${REPO_DIR}/frontend/.next" 2>/dev/null || true
echo "✓ Frontend .next cache cleared"

# Load local secrets for backend startup. Priority:
# 1) .env.local in repo root (git-ignored)
# 2) macOS Keychain item: EMPIRE_ELEVENLABS_API_KEY
BACKEND_SECRET_BOOTSTRAP='if [ -f .env.local ]; then set -a; . ./.env.local; set +a; fi; if [ -z "${ELEVENLABS_API_KEY:-}" ]; then export ELEVENLABS_API_KEY="$(security find-generic-password -a "$USER" -s EMPIRE_ELEVENLABS_API_KEY -w 2>/dev/null || true)"; fi'
BACKEND_SECRET_BOOTSTRAP_ESCAPED="${BACKEND_SECRET_BOOTSTRAP//\"/\\\"}"

# Start backend in a new Terminal window
osascript <<EOF
tell application "Terminal"
    do script "cd ${REPO_DIR} && ${BACKEND_SECRET_BOOTSTRAP_ESCAPED} && backend/.venv/bin/uvicorn ${BACKEND_APP_MODULE} --host 0.0.0.0 --port ${BACKEND_PORT} --reload 2>&1"
    set custom title of front window to "Empire - Backend :${BACKEND_PORT}"
    activate
end tell
EOF

sleep 1

# Start frontend in another Terminal window
osascript <<EOF
tell application "Terminal"
    do script "cd ${REPO_DIR}/frontend && NEXT_PUBLIC_API_URL=http://localhost:${BACKEND_PORT} npm run dev 2>&1"
    set custom title of front window to "Empire - Frontend :${FRONTEND_PORT}"
    activate
end tell
EOF

echo "⏳ Waiting for services to warm up..."

# Poll the backend until it responds so we don't open the browser before the
# API is ready to serve requests.
for i in {1..30}; do
    if curl -s "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; then
        echo "✓ Backend responding on :${BACKEND_PORT}"
        break
    fi
    sleep 1
done

# Poll the frontend dev server too.
for i in {1..30}; do
    if curl -s "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1; then
        echo "✓ Frontend responding on :${FRONTEND_PORT}"
        break
    fi
    sleep 1
done

open "http://localhost:${FRONTEND_PORT}"

echo "✅ Empire opened at http://localhost:${FRONTEND_PORT}"
