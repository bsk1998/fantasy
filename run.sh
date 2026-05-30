#!/bin/bash
# run.sh — Launcher pour macOS et Linux
# =====
# Démarre automatiquement backend + frontend en un clic
# Usage: bash run.sh

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cleanup() {
    echo ""
    echo -e "${GREEN}Arrêt de l'application...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}✅ Application arrêtée${NC}"
    exit 0
}

trap cleanup INT TERM

echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}🎮 Fantasy Boulzazen WC 2026 — Launcher${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 non trouvé${NC}"
    echo "Installez Python depuis https://python.org"
    exit 1
fi

# Vérifier Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js non trouvé${NC}"
    echo "Installez Node.js depuis https://nodejs.org"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [ -z "$LAN_IP" ] && command -v ip >/dev/null 2>&1; then
    LAN_IP="$(ip route get 8.8.8.8 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") {print $(i+1); exit}}')"
fi

# Setup Backend
echo -e "${BLUE}=== Setup Backend ===${NC}"
cd backend

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Création du virtualenv...${NC}"
    python3 -m venv venv
fi

source venv/bin/activate

echo -e "${YELLOW}Installation des dépendances Python...${NC}"
pip install -q -r requirements.txt 2>/dev/null || pip install -r requirements.txt

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Création du fichier .env...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
    else
        cat > .env << 'EOF'
DATABASE_URL=sqlite:///./fantasy_wc2026.db
SUPABASE_JWT_SECRET=dev-secret-key-for-development-only
GROQ_API_KEY=
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
EOF
    fi
fi

echo -e "${GREEN}✅ Backend prêt${NC}"
cd ..

# Setup Frontend
echo ""
echo -e "${BLUE}=== Setup Frontend ===${NC}"
cd frontend

echo -e "${YELLOW}Installation des dépendances Node...${NC}"
npm install --silent 2>/dev/null || npm install

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Création du fichier .env...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
    else
        cat > .env << 'EOF'
VITE_API_BASE=http://localhost:8000
VITE_SUPABASE_URL=https://example.supabase.co
VITE_SUPABASE_ANON_KEY=example-anon-key
EOF
    fi
fi

echo -e "${GREEN}✅ Frontend prêt${NC}"
cd ..

# Démarrer les services
echo ""
echo -e "${BLUE}=== Démarrage des services ===${NC}"
echo ""

(
    cd backend
    source venv/bin/activate
    echo -e "${YELLOW}Backend sur http://localhost:8000${NC}"
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
) &
BACKEND_PID=$!

sleep 3

(
    cd frontend
    echo -e "${YELLOW}Frontend sur http://localhost:5173${NC}"
    npm run dev
) &
FRONTEND_PID=$!

sleep 3

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Application prête !${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Frontend  : http://localhost:5173${NC}"
if [ -n "$LAN_IP" ]; then
    echo -e "${BLUE}Android   : http://$LAN_IP:5173${NC}"
    echo -e "${YELLOW}Ouvrez cette adresse sur le telephone connecte au meme Wi-Fi.${NC}"
else
    echo -e "${YELLOW}Android   : IP locale non detectee. Verifiez le Wi-Fi du PC.${NC}"
fi
echo -e "${BLUE}Backend   : http://localhost:8000${NC}"
echo -e "${BLUE}API Docs  : http://localhost:8000/docs${NC}"
echo ""
echo -e "${YELLOW}Appuyez sur Ctrl+C pour arrêter${NC}"
echo ""

# Attendre l'interruption
wait
