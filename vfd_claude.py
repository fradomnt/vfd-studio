#!/usr/bin/env python3
"""
vfd_claude.py: conversa com o Claude e mostra a resposta, em tempo real,
na tela VFD Noritake GU256X128C-3900 (RS-232, 38400 8N1).

Instalar: pip install pyserial pillow anthropic
Uso (Windows PowerShell):
    $env:ANTHROPIC_API_KEY="sk-ant-..."
    python vfd_claude.py
Uso (Mac/Linux):
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 vfd_claude.py

Variáveis opcionais:
    VFD_PORTA   (ex.: COM5; por padrão detecta o conversor sozinho)
    VFD_MODELO  (padrão claude-sonnet-5-5)
    VFD_LOGO    (padrão ~/Downloads/logo_vfd.bin; mostrado na abertura, se existir)
"""
import os, sys, time, unicodedata
import anthropic
from vfd import VFD as _Serial       # biblioteca vfd.py da mesma pasta (pyserial)

MODELO = os.environ.get("VFD_MODELO", "claude-sonnet-5-5")
LOGO   = os.path.expanduser(os.environ.get("VFD_LOGO", "~/Downloads/logo_vfd.bin"))
COLS   = 42          # fonte padrão 6x8 -> 42 colunas x 16 linhas

SISTEMA = ("Você responde numa tela VFD pequena de 42 colunas por 16 linhas. "
           "Responda em português, de forma curta e direta, em texto puro: "
           "sem markdown, sem asteriscos, sem tabelas e sem emojis.")

# ---------------------------------------------------------------- serial
class VFD:
    def __init__(self, base):
        self.base, self.col, self.palavra = base, 0, ""

    def raw(self, b, pausa=0.0):
        self.base.raw(b, pausa)

    def iniciar(self):
        self.raw(b"\x1b\x40", 0.3)             # inicializa
        self.raw(b"\x1f\x58\x18", 0.05)        # brilho 100 %
        self.raw(b"\x1f\x02", 0.05)            # modo rolagem vertical
        self.limpar()

    def limpar(self):
        self.raw(b"\x0c", 0.05)
        self.col, self.palavra = 0, ""

    def logo(self, caminho, segundos=2.0):
        if not os.path.exists(caminho):
            return
        dados = open(caminho, "rb").read()
        self.limpar()
        for i in range(0, len(dados), 128):    # buffer da tela = 256 B
            self.raw(dados[i:i+128], 0.05)
        time.sleep(segundos)
        self.limpar()

    # --- texto com quebra de linha por palavra
    @staticmethod
    def ascii(txt):
        trocas = {"“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-",
                  "…": "...", "•": "-", "°": "o", "º": "o", "ª": "a"}
        txt = "".join(trocas.get(c, c) for c in txt)
        txt = unicodedata.normalize("NFKD", txt)
        return "".join(c for c in txt if 32 <= ord(c) < 127 or c == "\n")

    def _nova_linha(self):
        self.raw(b"\r\n")
        self.col = 0

    def _sai_palavra(self):
        p = self.palavra
        self.palavra = ""
        while p:
            if self.col and self.col + len(p) > COLS:
                self._nova_linha()
            pedaco, p = p[:COLS - self.col], p[COLS - self.col:]
            self.raw(pedaco.encode("ascii"))
            self.col += len(pedaco)
            if self.col >= COLS:
                self.col = 0                   # a tela já quebrou sozinha

    def escrever(self, txt):
        for c in self.ascii(txt):
            if c in "*#`_":                    # restos de markdown
                continue
            if c == "\n":
                self._sai_palavra()
                if self.col: self._nova_linha()
            elif c == " ":
                self._sai_palavra()
                if 0 < self.col < COLS:
                    self.raw(b" ")
                    self.col += 1
            else:
                self.palavra += c

    def fim(self):
        self._sai_palavra()

# ---------------------------------------------------------------- main
def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Defina ANTHROPIC_API_KEY antes de rodar (export ANTHROPIC_API_KEY=...).")
    base = _Serial()
    vfd = VFD(base)
    vfd.iniciar()
    vfd.logo(LOGO)
    vfd.escrever("Pronto. Pergunte no Terminal.")
    vfd.fim()

    cliente = anthropic.Anthropic()
    historico = []
    print(f"Tela: {base.porta} | Modelo: {MODELO} | 'sair' para encerrar\n")
    while True:
        try:
            pergunta = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not pergunta:
            continue
        if pergunta.lower() in ("sair", "exit", "quit"):
            break

        historico.append({"role": "user", "content": pergunta})
        vfd.limpar()
        vfd.escrever("> " + pergunta + "\n")

        resposta = ""
        print("Claude: ", end="", flush=True)
        with cliente.messages.stream(model=MODELO, max_tokens=1024,
                                     system=SISTEMA, messages=historico) as stream:
            for trecho in stream.text_stream:
                print(trecho, end="", flush=True)
                vfd.escrever(trecho)
                resposta += trecho
        vfd.fim()
        print("\n")
        historico.append({"role": "assistant", "content": resposta})

    vfd.limpar()
    vfd.escrever("Ate logo!")
    vfd.fim()

if __name__ == "__main__":
    main()
