@echo off
rem Gera o VFD Studio empacotado para Windows: dist\VFD Studio\VFD Studio.exe (+ zip).
rem Rodar neste mesmo Windows, dentro da pasta do projeto. Precisa de internet na primeira vez.
chcp 65001 >nul
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente .venv...
  where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv) || goto erro
)
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt -r requirements-dev.txt || goto erro
echo Gerando o executavel (1 a 3 minutos)...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean vfd_studio.spec || goto erro
copy /y cenas.json "dist\VFD Studio\" >nul
copy /y config.json "dist\VFD Studio\" >nul
copy /y README.md "dist\VFD Studio\LEIA-ME.md" >nul
powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\VFD Studio' -DestinationPath 'dist\VFD-Studio-2.0-windows.zip'"
echo.
echo Pronto:  dist\VFD Studio\VFD Studio.exe
echo Zip:     dist\VFD-Studio-2.0-windows.zip
echo Para usar em outro PC: descompacte e de duplo clique em "VFD Studio.exe". Nao precisa de Python.
goto fim
:erro
echo.
echo Algo deu errado. Veja a mensagem acima.
:fim
pause
