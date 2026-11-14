@echo off
rem VFD Studio - lancador para Windows (duplo clique).
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente .venv ^(so na primeira vez^)...
  %PY% -m venv .venv || goto erro
)
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || goto erro
".venv\Scripts\python.exe" app.py
goto fim
:erro
echo.
echo Algo deu errado. Confira se o Python 3 esta instalado ^(python.org, marcando "Add to PATH"^).
pause
:fim
