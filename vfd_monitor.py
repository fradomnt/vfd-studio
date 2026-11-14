#!/usr/bin/env python3
"""
vfd_monitor.py: painel ao vivo do computador na tela VFD GU256X128C-3900.
Sem custo: lê dados locais (CPU, memória, disco, rede, relógio). Windows/Mac/Linux.

Instalação (uma vez):  pip install pyserial pillow psutil
Uso:                   python vfd_monitor.py      (Ctrl+C para sair)
"""
import os, time, datetime, collections
import psutil
from PIL import Image, ImageDraw, ImageFont
from vfd import VFD, W, H          # usa a biblioteca vfd.py da mesma pasta

# ------------------------------------------------------------ fontes
def fonte(tam):
    for f in ("C:/Windows/Fonts/consola.ttf", "/System/Library/Fonts/Menlo.ttc",
              "/System/Library/Fonts/Monaco.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, tam)
    return ImageFont.load_default()

F_GRANDE, F_MEDIA, F_PEQ = fonte(24), fonte(11), fonte(10)

# ------------------------------------------------------------ leitura
def fmt_taxa(bps):
    if bps >= 1_000_000: return f"{bps/1_000_000:.1f}M"
    if bps >= 1_000:     return f"{bps/1_000:.0f}k"
    return f"{bps:.0f}"

historico = collections.deque([0.0]*W, maxlen=W)

def desenhar(cpu, mem, disco, rx, tx, agora):
    img = Image.new("1", (W, H), 0)
    d = ImageDraw.Draw(img); d.fontmode = "1"     # sem antisserrilhado
    # relógio + data
    d.text((2, 0), agora.strftime("%H:%M:%S"), font=F_GRANDE, fill=1)
    dias = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
    d.text((172, 2),  dias[agora.weekday()], font=F_MEDIA, fill=1)
    d.text((172, 15), agora.strftime("%d/%m/%y"), font=F_MEDIA, fill=1)
    d.line((0, 30, W-1, 30), fill=1)
    # barras
    def barra(y, rotulo, pct):
        d.text((2, y), rotulo, font=F_PEQ, fill=1)
        d.rectangle((40, y+2, 200, y+9), outline=1)
        d.rectangle((40, y+2, 40 + int(160*pct/100), y+9), fill=1)
        d.text((206, y), f"{pct:3.0f}%", font=F_PEQ, fill=1)
    barra(33, "CPU",   cpu)
    barra(45, "RAM",   mem)
    barra(57, "DISCO", disco)
    d.text((2, 69), f"REDE  down {fmt_taxa(rx)}B/s  up {fmt_taxa(tx)}B/s",
           font=F_PEQ, fill=1)
    # gráfico da CPU (últimas 256 leituras)
    topo, base = 84, 127
    d.rectangle((0, topo, W-1, base), outline=1)
    alt = base - topo - 2
    for x, v in enumerate(historico):
        h = int(alt * v / 100)
        if h: d.line((x, base-1, x, base-1-h), fill=1)
    return img

def main():
    tela = VFD()
    tela.limpar()
    psutil.cpu_percent(None)
    net0, t0 = psutil.net_io_counters(), time.time()
    print("Painel ativo na tela. Ctrl+C para sair.")
    try:
        while True:
            time.sleep(1)
            cpu = psutil.cpu_percent(None)
            mem = psutil.virtual_memory().percent
            disco = psutil.disk_usage(os.path.abspath(os.sep)).percent
            net1, t1 = psutil.net_io_counters(), time.time()
            dt = max(t1 - t0, 0.001)
            rx = (net1.bytes_recv - net0.bytes_recv) / dt
            tx = (net1.bytes_sent - net0.bytes_sent) / dt
            net0, t0 = net1, t1
            historico.append(cpu)
            tela.bitmap(desenhar(cpu, mem, disco, rx, tx, datetime.datetime.now()))
    except KeyboardInterrupt:
        tela.limpar(); tela.fechar()
        print("\nEncerrado.")

if __name__ == "__main__":
    main()
