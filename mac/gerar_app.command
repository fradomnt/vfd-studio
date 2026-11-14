#!/bin/bash
# Gera o "VFD Studio.app" para macOS: dist/VFD Studio.app (+ zip). Rodar NO MAC, na pasta do projeto.
# O app sai sem assinatura da Apple: na primeira abertura, botão direito > Abrir (ou veja o README).
cd "$(dirname "$0")/.." || exit 1
pausar() { read -r -p "Enter para fechar..." _; }

PY=""
for c in /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  [ -x "$c" ] && PY="$c"
done
[ -z "$PY" ] && { echo "Python 3 não encontrado (python.org/downloads)."; pausar; exit 1; }
[ -x .venv/bin/python ] || "$PY" -m venv .venv || { pausar; exit 1; }
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt -r requirements-dev.txt || { pausar; exit 1; }

echo "Gerando o app (1 a 3 minutos)..."
.venv/bin/python -m PyInstaller --noconfirm --clean vfd_studio.spec || { pausar; exit 1; }
cp cenas.json config.json "dist/" 2>/dev/null
cp README.md "dist/LEIA-ME.md"
# tira a quarentena do que acabou de ser gerado aqui e assina ad hoc (abre sem aviso neste Mac)
xattr -cr "dist/VFD Studio.app" 2>/dev/null
codesign --force --deep --sign - "dist/VFD Studio.app" 2>/dev/null && echo "Assinado ad hoc."
( cd dist && ditto -c -k --sequesterRsrc --keepParent "VFD Studio.app" "VFD-Studio-2.0-mac.zip" )
echo
echo "Pronto:  dist/VFD Studio.app"
echo "Zip:     dist/VFD-Studio-2.0-mac.zip"
echo "Em outro Mac: descompacte, botão direito no app > Abrir (só na primeira vez)."
echo "cenas.json e config.json ficam AO LADO do .app."
pausar
