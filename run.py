#!/usr/bin/env python3
"""
run.py — Launcher universel Fantasy Boulzazen WC 2026
=====================================================
Lance automatiquement frontend + backend en un seul clic.
Fonctionne sur Windows, macOS, Linux.

Usage:
    python run.py

Cela va :
  1. Installer les dépendances (pip + npm)
  2. Démarrer le backend (FastAPI) sur http://localhost:8000
  3. Démarrer le frontend (Vite) sur http://localhost:5173
  4. Ouvrir automatiquement le navigateur
"""

import os
import sys
import subprocess
import time
import webbrowser
import platform
import shutil
from pathlib import Path
import signal
import socket

# Configuration
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

def get_lan_ip():
    """Retourne l'adresse IP du PC sur le reseau local."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return None

def get_lan_urls():
    lan_ip = get_lan_ip()
    if not lan_ip or lan_ip.startswith("127."):
        return None, None
    return f"http://{lan_ip}:{FRONTEND_PORT}", f"http://{lan_ip}:{BACKEND_PORT}"

# Couleurs pour la sortie console
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def disable():
        Colors.HEADER = ''
        Colors.BLUE = ''
        Colors.CYAN = ''
        Colors.GREEN = ''
        Colors.YELLOW = ''
        Colors.RED = ''
        Colors.ENDC = ''
        Colors.BOLD = ''

# Sur Windows, désactiver les codes ANSI
if platform.system() == "Windows":
    Colors.disable()

def print_header(msg):
    """Affiche un header formaté."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}")
    print(f" {msg}")
    print(f"{'='*60}{Colors.ENDC}\n")

def print_success(msg):
    """Affiche un message de succès."""
    print(f"{Colors.GREEN}✅ {msg}{Colors.ENDC}")

def print_error(msg):
    """Affiche un message d'erreur."""
    print(f"{Colors.RED}❌ {msg}{Colors.ENDC}")

def print_info(msg):
    """Affiche un message d'info."""
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.ENDC}")

def print_warning(msg):
    """Affiche un message d'avertissement."""
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.ENDC}")

def get_project_root():
    """Retourne le répertoire racine du projet."""
    return Path(__file__).parent

def check_python_version():
    """Vérifie que Python ≥ 3.9."""
    print_header("Vérification Python")
    version = sys.version_info
    print_info(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print_error(f"Python 3.9+ requis, vous avez Python {version.major}.{version.minor}")
        sys.exit(1)
    
    print_success("Python version OK")

def check_nodejs_version():
    """Vérifie que Node.js ≥ 16."""
    print_header("Vérification Node.js")
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        version_str = result.stdout.strip()  # ex: "v18.12.0"
        print_info(f"Node.js {version_str}")
        
        version_num = int(version_str.replace('v', '').split('.')[0])
        if version_num < 16:
            print_error(f"Node.js 16+ requis, vous avez {version_str}")
            sys.exit(1)
        
        print_success("Node.js version OK")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print_error("Node.js non trouvé. Installez-le depuis https://nodejs.org/")
        sys.exit(1)

def setup_backend():
    """Installe les dépendances du backend."""
    print_header("Setup Backend")
    root = get_project_root()
    backend_dir = root / "backend"
    
    if not backend_dir.exists():
        print_error(f"Répertoire backend non trouvé : {backend_dir}")
        sys.exit(1)
    
    # Créer le venv
    venv_dir = backend_dir / "venv"
    if venv_dir.exists() and not (venv_dir / "pyvenv.cfg").exists():
        print_warning("Virtualenv backend incomplet detecte, reconstruction...")
        shutil.rmtree(venv_dir)

    if not venv_dir.exists():
        print_info("Création du virtualenv...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        print_success("Virtualenv créé")
    else:
        print_info("Virtualenv existant trouvé")
    
    # Déterminer le chemin du pip
    if platform.system() == "Windows":
        pip_path = venv_dir / "Scripts" / "pip.exe"
        python_path = venv_dir / "Scripts" / "python.exe"
    else:
        pip_path = venv_dir / "bin" / "pip"
        python_path = venv_dir / "bin" / "python"
    
    # Installer les dépendances
    requirements_file = backend_dir / "requirements.txt"
    if requirements_file.exists():
        print_info("Installation des dépendances Python...")
        subprocess.run([str(pip_path), "install", "-r", str(requirements_file)], check=True)
        print_success("Dépendances Python installées")
    
    # Créer les fichiers .env s'ils n'existent pas
    env_file = backend_dir / ".env"
    if not env_file.exists():
        print_info("Création du fichier .env (backend)...")
        env_template = backend_dir / ".env.example"
        if env_template.exists():
            import shutil
            shutil.copy(str(env_template), str(env_file))
        else:
            with open(env_file, 'w') as f:
                f.write("""# Backend Configuration
DATABASE_URL=sqlite:///./fantasy_wc2026.db
SUPABASE_JWT_SECRET=dev-secret-key-for-development-only
GROQ_API_KEY=
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
""")
        print_success(".env backend créé")
    
    return python_path

def setup_frontend():
    """Installe les dépendances du frontend."""
    print_header("Setup Frontend")
    root = get_project_root()
    frontend_dir = root / "frontend"
    
    if not frontend_dir.exists():
        print_error(f"Répertoire frontend non trouvé : {frontend_dir}")
        sys.exit(1)
    
    # Vérifier package.json
    if not (frontend_dir / "package.json").exists():
        print_error("package.json non trouvé dans frontend/")
        sys.exit(1)
    
    # npm install
    print_info("Installation des dépendances Node...")
    subprocess.run(["npm", "install"], cwd=str(frontend_dir), check=True)
    print_success("Dépendances Node installées")
    
    # Créer .env s'il n'existe pas
    env_file = frontend_dir / ".env"
    if not env_file.exists():
        print_info("Création du fichier .env (frontend)...")
        env_template = frontend_dir / ".env.example"
        if env_template.exists():
            import shutil
            shutil.copy(str(env_template), str(env_file))
        else:
            with open(env_file, 'w') as f:
                f.write("""VITE_API_BASE=http://localhost:8000
VITE_SUPABASE_URL=https://example.supabase.co
VITE_SUPABASE_ANON_KEY=example-anon-key
""")
        print_success(".env frontend créé")

def start_backend(python_path):
    """Démarre le backend FastAPI."""
    print_header("Démarrage du Backend")
    root = get_project_root()
    backend_dir = root / "backend"
    
    print_info(f"Backend sur {BACKEND_URL}")
    print_info("Appuyez sur Ctrl+C pour arrêter le backend...")
    
    # Définir les variables d'environnement
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    
    try:
        subprocess.run(
            [str(python_path), "-m", "uvicorn", "app.main:app", 
             "--host", "0.0.0.0", "--port", str(BACKEND_PORT), "--reload"],
            cwd=str(backend_dir),
            env=env,
            check=False
        )
    except KeyboardInterrupt:
        print_warning("Backend arrêté")
        sys.exit(0)

def start_frontend():
    """Démarre le frontend Vite."""
    print_header("Démarrage du Frontend")
    root = get_project_root()
    frontend_dir = root / "frontend"
    
    print_info(f"Frontend sur {FRONTEND_URL}")
    print_info("Appuyez sur Ctrl+C pour arrêter le frontend...")
    
    try:
        subprocess.run(
            ["npm", "run", "dev"],
            cwd=str(frontend_dir),
            check=False
        )
    except KeyboardInterrupt:
        print_warning("Frontend arrêté")
        sys.exit(0)

def wait_for_service(url, max_attempts=30, timeout=1):
    """Attend que le service soit disponible."""
    import urllib.request
    import urllib.error
    
    for attempt in range(max_attempts):
        try:
            urllib.request.urlopen(url, timeout=timeout)
            return True
        except (urllib.error.URLError, urllib.error.HTTPError):
            time.sleep(1)
            if attempt % 5 == 0:
                print_info(f"Attente du service... ({attempt}/{max_attempts})")
    
    return False

def main():
    """Fonction principale."""
    print_header("🎮 Fantasy Boulzazen WC 2026 — Launcher")
    print_info(f"Plateforme détectée : {platform.system()}")
    lan_frontend_url, lan_backend_url = get_lan_urls()
    
    # Vérifications initiales
    check_python_version()
    check_nodejs_version()
    
    # Setup
    python_path = setup_backend()
    setup_frontend()
    
    # Lancer les deux services en parallèle via des sous-processus
    print_header("Démarrage des services")
    
    import threading
    
    # Variables partagées
    services = {
        "backend": None,
        "frontend": None,
    }
    
    def run_backend():
        """Thread pour le backend."""
        try:
            root = get_project_root()
            backend_dir = root / "backend"
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            
            services["backend"] = subprocess.Popen(
                [str(python_path), "-m", "uvicorn", "app.main:app",
                 "--host", "0.0.0.0", "--port", str(BACKEND_PORT), "--reload"],
                cwd=str(backend_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as e:
            print_error(f"Erreur backend : {e}")
    
    def run_frontend():
        """Thread pour le frontend."""
        try:
            root = get_project_root()
            frontend_dir = root / "frontend"
            time.sleep(3)  # Attendre un peu avant de lancer le frontend
            
            services["frontend"] = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=str(frontend_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as e:
            print_error(f"Erreur frontend : {e}")
    
    # Lancer les threads
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    frontend_thread = threading.Thread(target=run_frontend, daemon=True)
    
    backend_thread.start()
    frontend_thread.start()
    
    # Attendre que les services soient prêts
    print_info("Attente du démarrage des services...")
    time.sleep(5)
    
    # Vérifier que les services sont actifs
    print_info("Vérification du backend...")
    if wait_for_service(f"{BACKEND_URL}/health"):
        print_success(f"Backend prêt : {BACKEND_URL}")
    else:
        print_warning(f"Backend peut ne pas être prêt, essayez manuellement : {BACKEND_URL}")
    
    time.sleep(2)
    
    print_info("Vérification du frontend...")
    if wait_for_service(FRONTEND_URL):
        print_success(f"Frontend prêt : {FRONTEND_URL}")
    else:
        print_warning(f"Frontend peut ne pas être prêt, essayez manuellement : {FRONTEND_URL}")
    
    # Ouvrir le navigateur
    print_header("Ouverture du navigateur")
    print_info(f"Ouverture de {FRONTEND_URL}...")
    webbrowser.open(FRONTEND_URL)
    
    print_success("Application prête !")
    print_info("Les services tournent en arrière-plan.")
    print_info("Fermez cette fenêtre pour arrêter l'application.")
    print_info("")
    print_info(f"PC        : {FRONTEND_URL}")
    if lan_frontend_url:
        print_info(f"Android   : {lan_frontend_url}")
        print_info("Ouvrez cette adresse sur le telephone connecte au meme Wi-Fi.")
    else:
        print_warning("Adresse Android non detectee. Verifiez que le PC est connecte au Wi-Fi.")
    print_info(f"Backend   : {BACKEND_URL}")
    if lan_backend_url:
        print_info(f"Backend LAN : {lan_backend_url}")
    print_info(f"API Docs  : {BACKEND_URL}/docs")
    print_info("")
    
    # Attendre que les processus se terminent
    try:
        while True:
            if services["backend"] and services["backend"].poll() is not None:
                print_warning("Backend s'est arrêté")
            if services["frontend"] and services["frontend"].poll() is not None:
                print_warning("Frontend s'est arrêté")
            time.sleep(1)
    except KeyboardInterrupt:
        print_header("Arrêt de l'application")
        if services["backend"]:
            services["backend"].terminate()
            try:
                services["backend"].wait(timeout=5)
            except subprocess.TimeoutExpired:
                services["backend"].kill()
        if services["frontend"]:
            services["frontend"].terminate()
            try:
                services["frontend"].wait(timeout=5)
            except subprocess.TimeoutExpired:
                services["frontend"].kill()
        print_success("Application arrêtée")
        sys.exit(0)

if __name__ == "__main__":
    main()
