"""
caminhos.py — onde o app procura seus arquivos, rodando do código-fonte ou empacotado (PyInstaller).

FIXOS  (static/, assets/): dentro do pacote quando empacotado (sys._MEIPASS), senão a pasta do código.
DADOS  (cenas.json, config.json, logs/): sempre ao lado do executável ou do código, para o usuário achar
        e para sobreviver a atualização do app.
"""
import sys
from pathlib import Path

VERSAO = "2.0"
EMPACOTADO = getattr(sys, "frozen", False)

if EMPACOTADO:
    FIXOS = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    DADOS = Path(sys.executable).parent
    # no .app do Mac o executável fica em VFD Studio.app/Contents/MacOS; os dados vão ao lado do .app
    if sys.platform == "darwin" and DADOS.name == "MacOS" and DADOS.parent.name == "Contents":
        DADOS = DADOS.parent.parent.parent
else:
    FIXOS = DADOS = Path(__file__).resolve().parent
