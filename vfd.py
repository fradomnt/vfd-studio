#!/usr/bin/env python3
"""
vfd.py — biblioteca + linha de comando para a tela Noritake GU256X128C-3900
ligada pelo conversor PCM-KW-469 (RS-232, 38400 8N1). Funciona em Windows, macOS e Linux.

Tudo aqui foi validado na bancada em 12/10/2026 (texto, logo em bitmap,
formato de imagem, pausas de buffer).

INSTALAR (uma vez):
    Windows:   pip install pyserial pillow
    Mac/Linux: pip3 install pyserial pillow

PORTA: detectada sozinha pelo número de série do conversor (A1AEZRMT).
    Para forçar:  set VFD_PORTA=COM5        (Windows, cmd)
                  $env:VFD_PORTA="COM5"      (Windows, PowerShell)
                  export VFD_PORTA=/dev/cu.usbserial-A1AEZRMT   (Mac)
    Listar portas: python vfd.py portas

USO NA LINHA DE COMANDO:
    python vfd.py texto "Ola, Frado"          # escreve texto
    python vfd.py texto -l "linha 1" "linha 2" # várias linhas
    python vfd.py limpar                      # limpa a tela
    python vfd.py brilho 4                    # 1..8  (8 = 100 %)
    python vfd.py imagem foto.png             # qualquer PNG/JPG -> 256x128
    python vfd.py bin logo_vfd.bin            # envia um .bin já pronto
    python vfd.py desliga | liga              # apaga/acende o display
    python vfd.py teste                       # texto + xadrez + tela cheia
    python vfd.py hora                        # relógio grande ao vivo (Ctrl+C sai)

USO COMO BIBLIOTECA:
    from vfd import VFD
    with VFD() as tela:
        tela.limpar()
        tela.texto("Ola!")
        tela.imagem("foto.png")

"""
import os, sys, time, unicodedata
import serial
from serial.tools import list_ports

SERIAL_CONVERSOR = "A1AEZRMT"      # nº de série do FT232R do PCM-KW-469
PORTA_SIMULADA = "simulado"        # nome da "porta" da tela simulada (VFD_SIMULADO=1)
BYTES_POR_S = 3840                 # 38400 bps, 8N1: 10 bits por byte


def simulado():
    """VFD_SIMULADO=1 liga a tela simulada: sem serial, só a prévia. Para desenvolver sem o hardware."""
    return os.environ.get("VFD_SIMULADO", "") not in ("", "0")


def achar_porta():
    """Devolve a porta do conversor: VFD_PORTA, ou busca pelo nº de série / chip FTDI."""
    if simulado():
        return PORTA_SIMULADA
    if os.environ.get("VFD_PORTA"):
        return os.environ["VFD_PORTA"]
    portas = list(list_ports.comports())
    for p in portas:
        if p.serial_number and SERIAL_CONVERSOR in p.serial_number:
            return p.device
    for p in portas:
        if p.vid == 0x0403:                       # qualquer FTDI
            return p.device
    nomes = ", ".join(p.device for p in portas) or "nenhuma"
    raise SystemExit(f"Conversor nao encontrado. Portas vistas: {nomes}. "
                     f"Plugue o USB ou defina VFD_PORTA (ex.: COM5).")

def listar_portas():
    for p in list_ports.comports():
        print(f"{p.device:12s} {p.description}  serial={p.serial_number}")

def portas():
    """Lista de portas como dicionários (usada pela aplicação web).
    'conversor' = True para o PCM-KW-469 (nº de série) ou qualquer FTDI."""
    lista = []
    if simulado():
        lista.append({"porta": PORTA_SIMULADA, "descricao": "Tela simulada (VFD_SIMULADO=1)", "serial": "",
                      "ftdi": False, "conversor": True})
    for p in list_ports.comports():
        nosso = bool(p.serial_number and SERIAL_CONVERSOR in p.serial_number)
        lista.append({"porta": p.device, "descricao": p.description or "",
                      "serial": p.serial_number or "", "ftdi": p.vid == 0x0403,
                      "conversor": nosso})
    return lista

def porta_preferida():
    """Igual a achar_porta(), mas devolve None em vez de encerrar o programa."""
    try:
        return achar_porta()
    except SystemExit:
        return None
W, H = 256, 128           # pontos
COLS, LINHAS = 42, 16     # fonte padrão 6x8

# ----------------------------------------------------------------- comandos
INIT        = b"\x1b\x40"
LIMPAR      = b"\x0c"
HOME        = b"\x0b"
CRLF        = b"\r\n"
MODO_SOBRE  = b"\x1f\x01"          # sobrescreve (padrão)
MODO_ROLA   = b"\x1f\x02"          # rolagem vertical quando enche
DISPLAY_ON  = b"\x1f\x28\x61\x40\x01"
DISPLAY_OFF = b"\x1f\x28\x61\x40\x00"
CURSOR_OFF  = b"\x1f\x43\x00"
CURSOR_ON   = b"\x1f\x43\x01"

def cmd_brilho(n):            # n = 1..8  -> 1F 58 10..18 (0 % a 100 % em 8 passos)
    n = max(1, min(8, int(n)))
    return b"\x1f\x58" + bytes([0x10 + n])

def cmd_cursor(x, y):         # x em pontos (0..255), y em linhas de 8 pontos (0..15)
    return b"\x1f\x24" + bytes([x & 0xFF, x >> 8, y & 0xFF, y >> 8])

def cmd_fonte(tam):           # 1 = 6x8 · 2 = 8x16 · 4 = 16x32
    return b"\x1f\x28\x67\x01" + bytes([tam])

def cmd_inverter(ligado):     # texto invertido (fundo aceso)
    return b"\x1f\x72" + (b"\x01" if ligado else b"\x00")

# ----------------------------------------------------------------- classe
class VFD:
    def __init__(self, porta=None, baud=38400, iniciar=True, ao_enviar=None):
        """iniciar=False abre a porta sem mandar nada à tela.
        ao_enviar(n_bytes, segundos) é chamado depois de cada envio (log da aplicação)."""
        self.ao_enviar = ao_enviar
        self.porta = porta or achar_porta()
        self.ser = serial.Serial(self.porta, baud, bytesize=8, parity="N", stopbits=1,
                                 rtscts=False, dsrdtr=False, xonxoff=False, write_timeout=2)
        print(f"Tela em {self.porta} @ {baud} bps")
        if iniciar:
            self.iniciar()

    def __enter__(self): return self
    def __exit__(self, *_): self.fechar()
    def fechar(self):
        try: self.ser.close()
        except Exception: pass

    # --- envio bruto
    def raw(self, dados, pausa=0.0):
        """Envia bytes e espera saírem pela serial. Blocos de 128 B respeitam o buffer de 256 B."""
        t0 = time.time()
        for i in range(0, len(dados), 128):
            self.ser.write(dados[i:i+128])
            self.ser.flush()
            if len(dados) > 128: time.sleep(0.02)
        if pausa: time.sleep(pausa)
        if self.ao_enviar:
            self.ao_enviar(len(dados), time.time() - t0)

    # --- básicos
    def iniciar(self):
        self.raw(INIT, 0.3)
        self.raw(cmd_brilho(8), 0.05)
        self.raw(CURSOR_OFF)
    def limpar(self):          self.raw(LIMPAR, 0.05)
    def brilho(self, n):       self.raw(cmd_brilho(n), 0.02)
    def ligar(self):           self.raw(DISPLAY_ON, 0.02)
    def desligar(self):        self.raw(DISPLAY_OFF, 0.02)
    def fonte(self, tam):      self.raw(cmd_fonte(tam))
    def cursor(self, x, y):    self.raw(cmd_cursor(x, y))
    def rolagem(self, ligada): self.raw(MODO_ROLA if ligada else MODO_SOBRE)

    # --- texto
    @staticmethod
    def ascii(txt):
        """A tela só tem ASCII na tabela padrão: tira acentos (ç->c, ã->a)."""
        trocas = {"“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-", "…": "...", "º": "o", "ª": "a"}
        txt = "".join(trocas.get(c, c) for c in txt)
        txt = unicodedata.normalize("NFKD", txt)
        return "".join(c for c in txt if 32 <= ord(c) < 127 or c in "\r\n")

    def texto(self, txt, x=None, y=None):
        """Escreve texto. Opcionalmente posiciona o cursor em (x pontos, y linha de 8 px)."""
        if x is not None: self.cursor(x, y or 0)
        self.raw(self.ascii(txt).replace("\n", "\r\n").encode("ascii"))

    def linhas(self, *linhas):
        """Escreve várias linhas a partir do topo."""
        self.limpar()
        self.texto("\n".join(linhas))

    # --- imagens
    @staticmethod
    def _codificar(img):
        """PIL Image (qualquer modo) -> 4096 bytes no formato da tela.
        Colunas da esquerda p/ direita; 16 bytes por coluna de cima p/ baixo; bit7 = ponto de cima.
        Transpor a imagem faz cada coluna virar uma linha, e tobytes() do modo "1" empacota 8 pontos
        por byte com o primeiro ponto no bit 7: é exatamente o formato da tela, sem laço em Python."""
        from PIL import Image, ImageOps
        g = img.convert("L")
        if g.size != (W, H):                         # ajusta mantendo proporção, centraliza
            g = ImageOps.contain(g, (W, H))
            fundo = Image.new("L", (W, H), 0)
            fundo.paste(g, ((W - g.width) // 2, (H - g.height) // 2))
            g = fundo
        bw = g.point(lambda v: 255 if v > 127 else 0, "1")
        return bw.transpose(Image.Transpose.TRANSPOSE).tobytes()

    @staticmethod
    def pacote_bitmap(dados, x=0, yb=0, largura=W, altura_bytes=H // 8):
        """Comando 1F 28 66 11 para uma região: cursor em (x pontos, yb linha de 8 pontos), largura em
        pontos, altura em bytes. 'dados' = colunas da região, altura_bytes bytes por coluna.
        Com a tela inteira (padrão) sai o pacote validado na bancada: 00 01 10 00 01 + 4096 B."""
        assert len(dados) == largura * altura_bytes, "dados não batem com a região"
        return cmd_cursor(x, yb) + b"\x1f\x28\x66\x11" + bytes([largura & 0xFF, largura >> 8,
                                                                  altura_bytes & 0xFF, altura_bytes >> 8, 1]) + dados

    @staticmethod
    def regiao_diferente(antes, depois):
        """Caixa (x0, x1, yb0, yb1) que cobre todos os bytes que mudaram entre dois quadros de 4096 B,
        em colunas e linhas de 8 pontos. None se nada mudou."""
        n = H // 8
        xs = [x for x in range(W) if antes[x * n:(x + 1) * n] != depois[x * n:(x + 1) * n]]
        if not xs:
            return None
        x0, x1 = xs[0], xs[-1]
        ybs = [yb for yb in range(n) if any(antes[x * n + yb] != depois[x * n + yb] for x in xs)]
        return x0, x1, ybs[0], ybs[-1]

    def bits(self, dados, regiao=None):
        """Mostra 4096 bytes já no formato da tela. Com 'regiao' = (x0, x1, yb0, yb1), manda só essa
        caixa (1F 28 66 11 aceita largura e altura menores a partir do cursor). Devolve os bytes enviados."""
        n = H // 8
        if regiao is None or regiao == (0, W - 1, 0, n - 1):
            pacote = self.pacote_bitmap(dados)
        else:
            x0, x1, yb0, yb1 = regiao
            fatia = b"".join(dados[x * n + yb0:x * n + yb1 + 1] for x in range(x0, x1 + 1))
            pacote = self.pacote_bitmap(fatia, x0, yb0, x1 - x0 + 1, yb1 - yb0 + 1)
        self.raw(pacote)
        return len(pacote)

    def bitmap(self, img, inverter=False):
        """Mostra uma PIL Image na tela inteira."""
        from PIL import ImageOps
        if inverter: img = ImageOps.invert(img.convert("L"))
        self.bits(self._codificar(img))

    def imagem(self, caminho, inverter=False):
        """Mostra um arquivo PNG/JPG/BMP. Branco = ponto aceso. Use inverter=True p/ fundo branco."""
        from PIL import Image
        self.bitmap(Image.open(caminho), inverter)

    def enviar_bin(self, caminho):
        """Envia um .bin já pronto (ex.: logo_vfd.bin)."""
        self.raw(open(caminho, "rb").read())

    def desenhar(self):
        """Devolve (Image, ImageDraw) 256x128 em branco p/ você desenhar e depois chamar bitmap()."""
        from PIL import Image, ImageDraw
        im = Image.new("1", (W, H), 0)
        d = ImageDraw.Draw(im); d.fontmode = "1"
        return im, d

class VFDFalso(VFD):
    """Tela simulada: mesmos métodos, nenhuma serial. Cada envio dorme o tempo que levaria no fio
    (3840 B/s), para quem desenvolve sem o hardware sentir a cadência real. Liga com VFD_SIMULADO=1."""

    def __init__(self, porta=None, baud=38400, iniciar=True, ao_enviar=None):
        self.ao_enviar = ao_enviar
        self.porta = PORTA_SIMULADA
        self.ser = None
        print("Tela simulada (VFD_SIMULADO=1): nada sai pela serial.")
        if iniciar:
            self.iniciar()

    def fechar(self):
        pass

    def raw(self, dados, pausa=0.0):
        t0 = time.time()
        time.sleep(len(dados) / BYTES_POR_S + pausa)
        if self.ao_enviar:
            self.ao_enviar(len(dados), time.time() - t0)


def abrir(porta=None, **kw):
    """VFD na porta dada, ou VFDFalso quando a porta é a simulada."""
    cls = VFDFalso if (porta or achar_porta()) == PORTA_SIMULADA else VFD
    return cls(porta, **kw)


# ----------------------------------------------------------------- CLI
def _fonte_ttf(tam):
    from PIL import ImageFont
    for f in ("C:/Windows/Fonts/consolab.ttf", "C:/Windows/Fonts/consola.ttf",
              "/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"):
        if os.path.exists(f): return ImageFont.truetype(f, tam)
    return ImageFont.load_default()

def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__); return
    acao, args = argv[1], argv[2:]
    if acao == "portas":
        listar_portas(); return
    with abrir() as t:
        if acao == "texto":
            if args and args[0] == "-l": t.linhas(*args[1:])
            else: t.texto(" ".join(args))
        elif acao == "limpar":  t.limpar()
        elif acao == "brilho":  t.brilho(args[0] if args else 8)
        elif acao == "liga":    t.ligar()
        elif acao == "desliga": t.desligar()
        elif acao == "imagem":  t.imagem(args[0], inverter="-i" in args)
        elif acao == "bin":     t.enviar_bin(args[0])
        elif acao == "teste":
            t.linhas("Noritake GU256X128C-3900", "42 colunas x 16 linhas", "", "Teste OK: texto"); time.sleep(2)
            im, d = t.desenhar()
            for x in range(0, W, 16):
                for y in range(0, H, 16):
                    if (x // 16 + y // 16) % 2 == 0: d.rectangle((x, y, x + 15, y + 15), fill=1)
            t.bitmap(im); time.sleep(2)
            im, d = t.desenhar(); d.rectangle((0, 0, W - 1, H - 1), fill=1); t.bitmap(im); time.sleep(1)
            t.limpar(); t.texto("Teste completo.")
        elif acao == "hora":
            import datetime
            f_g, f_p = _fonte_ttf(56), _fonte_ttf(14)
            print("Relogio na tela. Ctrl+C para sair.")
            try:
                while True:
                    agora = datetime.datetime.now()
                    im, d = t.desenhar()
                    d.text((W // 2, 52), agora.strftime("%H:%M"), font=f_g, fill=1, anchor="mm")
                    d.text((W // 2, 108), agora.strftime("%A, %d/%m/%Y"), font=f_p, fill=1, anchor="mm")
                    t.bitmap(im); time.sleep(5)
            except KeyboardInterrupt:
                t.limpar()
        else:
            print(f"acao desconhecida: {acao}\n"); print(__doc__)

if __name__ == "__main__":
    main(sys.argv)
