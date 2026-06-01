@echo off
cd /d "%~dp0"

set "LAN_IP="
for /f "tokens=2 delims=:" %%I in ('ipconfig ^| findstr /c:"IPv4"') do (
    if not defined LAN_IP (
        set "LAN_IP=%%I"
        set "LAN_IP=!LAN_IP: =!"
    )
)

cls
echo.
echo ========================================================
echo  Gaming Fantasy Boulzazen WC 2026 - Launcher
echo ========================================================
echo.

REM Verifier Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERREUR: Python non trouve
    pause
    exit /b 1
)

REM Verifier Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERREUR: Node.js non trouve
    pause
    exit /b 1
)

REM Setup Backend
echo.
echo === Setup Backend ===
cd backend

echo Installation des dependances Python...
python -m pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo ERREUR: installation Python echouee
    pause
    exit /b 1
)

if not exist ".env" (
    echo Creation du fichier .env...
    if exist ".env.example" (
        copy .env.example .env >nul
    ) else (
        (
            echo DATABASE_URL=sqlite:///./fantasy_wc2026.db
            echo SUPABASE_JWT_SECRET=dev-secret-key-for-development-only
            echo GROQ_API_KEY=
            echo ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
        ) > .env
    )
)

echo [OK] Backend ready
cd ..

REM Setup Frontend
echo.
echo === Setup Frontend ===
cd frontend

echo Installation des dependances Node...
call npm.cmd install --silent
if %errorlevel% neq 0 (
    echo ERREUR: installation Node echouee
    pause
    exit /b 1
)

if not exist ".env" (
    echo Creation du fichier .env...
    (
        echo VITE_API_BASE=http://localhost:8000
        echo VITE_SUPABASE_URL=https://example.supabase.co
        echo VITE_SUPABASE_ANON_KEY=example-anon-key
    ) > .env
)

echo [OK] Frontend ready
cd ..

REM Lancer les services
echo.
echo === Lancement des services ===
echo.

start "Fantasy Backend" cmd /k "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

start "Fantasy Frontend" cmd /k "cd frontend && npm.cmd run dev"

timeout /t 5 /nobreak >nul

cls
echo.
echo ========================================================
echo  [OK] Application prete !
echo ========================================================
echo.
echo Frontend  : http://localhost:5173
echo Backend   : http://localhost:8000
echo API Docs  : http://localhost:8000/docs
echo.
echo Les services tournent dans des fenetres separees.
echo Fermez les fenetres pour arreter l'application.
echo.

start http://localhost:5173

pause