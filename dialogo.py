"""
dialogo.py — o fluxo da obra no vidro: a fala do agente em letra pequena e, na convergência, o destaque
embaixo, em letra maior, sem apagar a fala.

Quem manda é o aparatus (POST /api/v1/dialogo), e ele só diz a fala, o destaque e a cena. Letra, peso,
tamanho, modo de revelação e cadência vêm da cena (cenas.py, campos dialogo_* e destaque_*): quem opera
o vidro ajusta pela página, sem mexer no app que manda.

O layout é decidido UMA vez, com o texto completo, e a revelação só corta: quebrando o texto parcial, a
última palavra pularia de linha a cada caractere e o bloco inteiro tremeria. O destaque entra no layout
desde o começo, com zero revelado, para a fala já nascer no lugar certo e nada se deslocar quando ele
chegar. Quando a fala não cabe em cima do destaque, o vidro rola como um terminal: a janela termina na
linha em que a escrita está, não no fim do texto, que ainda nem foi escrito.
"""
from PIL import Image, ImageDraw

import presets
from vfd import W, H

MODOS = ("caractere", "palavra", "linha")
VAO = 4                          # pontos entre a fala e o destaque

_REGUA = ImageDraw.Draw(Image.new("1", (1, 1)))


def _linhas(texto, f):
    """Linhas que cabem na largura da tela, sem cortar palavra. Espaços repetidos viram um."""
    texto = " ".join((texto or "").split())
    return presets.quebrar_por_largura(texto, f) if texto else []


def _total(linhas):
    """Caracteres do bloco, contando a quebra de linha como o espaço que ela consumiu."""
    return sum(len(l) + 1 for l in linhas) - 1 if linhas else 0


def layout(fala, destaque, cena):
    """Decide fontes, linhas e alturas uma vez. Devolve um dict que desenhar() e passos() consomem."""
    f_fala = presets.fonte(cena["dialogo_peso"], cena["dialogo_tamanho"])
    f_dest = presets.fonte(cena["destaque_peso"], cena["destaque_tamanho"])
    alt_fala = sum(f_fala.getmetrics()) + presets.ENTRELINHA
    alt_dest = sum(f_dest.getmetrics()) + presets.ENTRELINHA
    linhas_dest = _linhas(destaque.upper(), f_dest) if destaque else []
    alto_dest = len(linhas_dest) * alt_dest + (VAO if linhas_dest else 0)
    util = H - 2 * presets.MARGEM
    # O destaque tem prioridade no espaço: é o instante da convergência. A fala fica com o resto.
    cabem = max((util - alto_dest) // alt_fala, 1)
    linhas_fala = _linhas(fala, f_fala)
    return {"fala": linhas_fala, "destaque": linhas_dest, "f_fala": f_fala, "f_dest": f_dest,
            "alt_fala": alt_fala, "alt_dest": alt_dest, "alto_dest": alto_dest, "cabem": cabem,
            "n_fala": _total(linhas_fala), "n_dest": _total(linhas_dest)}


def passos(lay, modo):
    """Os pontos da revelação em que o quadro muda, em ordem: lista de (revelado_fala, revelado_destaque).
    caractere: um por caractere; palavra: ao fim de cada palavra; linha: ao fim de cada linha. A fala
    inteira vem antes do destaque. A cadência é do laço de escrita: a posição (soma dos dois) dividida
    pelos caracteres por segundo da cena é o instante de cada passo."""
    if modo not in MODOS:
        raise ValueError(f"Modo de diálogo desconhecido: {modo}")

    def marcas(linhas):
        saida, base = [], 0
        for linha in linhas:
            if modo == "linha":
                saida.append(base + len(linha))
            elif modo == "palavra":
                pos = 0
                for palavra in linha.split(" "):
                    pos += len(palavra)
                    saida.append(base + pos)
                    pos += 1
            else:
                saida.extend(base + i for i in range(1, len(linha) + 1))
            base += len(linha) + 1
        return saida

    nf = lay["n_fala"]
    return [(m, 0) for m in marcas(lay["fala"])] + [(nf, m) for m in marcas(lay["destaque"])]


def _janela(linhas, revelado, cabem):
    """Recorta as linhas visíveis e o quanto delas já foi revelado. Cabendo tudo, devolve tudo: as linhas
    ainda em branco seguram a altura do bloco. Não cabendo, rola: a janela termina na linha corrente."""
    if len(linhas) <= cabem:
        return linhas, revelado
    consumido, fim = 0, 0
    for i, linha in enumerate(linhas):
        if revelado <= consumido:
            break
        fim = i
        consumido += len(linha) + 1
    inicio = max(0, fim - cabem + 1)
    pulados = sum(len(l) + 1 for l in linhas[:inicio])
    return linhas[inicio:inicio + cabem], revelado - pulados


def desenhar(lay, revelado_fala, revelado_destaque):
    """PIL Image 256x128 modo '1' com a fala cortada em revelado_fala e o destaque em revelado_destaque.
    O x de cada linha do destaque sai da linha COMPLETA, não do pedaço revelado: senão ela se recentraliza
    a cada caractere e treme. A fala é alinhada à esquerda, como se lê um fluxo."""
    img = Image.new("1", (W, H), 0)
    d = ImageDraw.Draw(img)
    d.fontmode = "1"                              # a tela só tem aceso e apagado
    linhas, rev = _janela(lay["fala"], revelado_fala, lay["cabem"])
    alto = len(linhas) * lay["alt_fala"] + lay["alto_dest"]
    y = presets.MARGEM + max(0, (H - 2 * presets.MARGEM - alto) // 2)
    for linha in linhas:
        if rev > 0:
            d.text((presets.MARGEM, y), linha[:rev], font=lay["f_fala"], fill=1, anchor="la")
        rev -= len(linha) + 1
        y += lay["alt_fala"]
    if lay["destaque"]:
        y += VAO
        rev = revelado_destaque
        for linha in lay["destaque"]:
            x = (W - _REGUA.textlength(linha, font=lay["f_dest"])) / 2
            if rev > 0:
                d.text((x, y), linha[:rev], font=lay["f_dest"], fill=1, anchor="la")
            rev -= len(linha) + 1
            y += lay["alt_dest"]
    return img
