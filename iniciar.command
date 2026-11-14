#!/bin/bash
# VFD Studio — lançador para macOS (duplo clique no Finder). Funciona em Mac Intel e Apple Silicon.
#
# Se o Finder disser que "não pode ser aberto": clique com o botão direito > Abrir, ou rode no Terminal
#   xattr -d com.apple.quarantine iniciar.command ; chmod +x iniciar.command
cd "$(dirname "$0")" || exit 1

pausar() { read -r -p "Enter para fechar..." _; }

# O /usr/bin/python3 do macOS é só um atalho que pede para instalar as Command Line Tools.
# Preferimos o Python do python.org (instala em /Library/Frameworks) ou do Homebrew.
PY=""
for candidato in /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 \
                 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [ -x "$candidato" ]; then PY="$candidato"; fi
done
if [ -z "$PY" ]; then
  if xcode-select -p >/dev/null 2>&1 && [ -x /usr/bin/python3 ]; then
    PY=/usr/bin/python3            # Command Line Tools já instaladas: o python3 da Apple serve
  else
    echo "Python 3 não encontrado."
    echo "Baixe o instalador para macOS em https://www.python.org/downloads/ , instale e rode de novo."
    pausar; exit 1
  fi
fi
echo "Python: $PY ($("$PY" --version 2>&1))"

if [ ! -x .venv/bin/python ]; then
  echo "Criando ambiente .venv (só na primeira vez)..."
  "$PY" -m venv .venv || { echo "Não consegui criar o .venv."; pausar; exit 1; }
fi
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt \
  || { echo "Falha ao instalar as dependências. Confira a internet e tente de novo."; pausar; exit 1; }

echo "Abrindo o VFD Studio... (feche esta janela para encerrar)"
.venv/bin/python app.py
pausar
