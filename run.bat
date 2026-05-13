@echo off
setlocal

rem ---------- backend ----------
pushd backend
if not exist .venv (
    echo [claw] creating python venv...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
echo [claw] installing backend deps...
pip install -q -r requirements.txt
if not exist .env (
    copy .env.example .env >nul
    echo [claw] created backend\.env from template — edit it to add VK/LLM keys
)
start "claw-backend" cmd /k "call .venv\Scripts\activate.bat && uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload"
popd

rem ---------- frontend ----------
pushd frontend
if not exist node_modules (
    echo [claw] installing frontend deps...
    call npm install
)
start "claw-frontend" cmd /k "npm run dev"
popd

echo.
echo [claw] backend  -> http://127.0.0.1:8765
echo [claw] frontend -> http://127.0.0.1:5173
echo [claw] open the frontend URL in your browser.
endlocal
