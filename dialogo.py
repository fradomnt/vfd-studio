"""
dialogo.py — o fluxo da obra no vidro: a fala do agente em letra pequena e, na convergência, o destaque
sozinho, em letra grande.

Quem manda é o aparatus (POST /api/v1/dialogo), e ele só diz a fala, o destaque e a cena. Letra, peso,
tamanho, modo de revelação, cadência e a pausa entre fala e destaque vêm da cena (cenas.py, campos
dialogo_* e destaque_*): quem opera o vidro ajusta pela página, sem mexer no app que manda.

São duas telas, nunca uma: a fala ocupa o vidro inteiro; depois de uma pausa com ela parada, o vidro
limpa e o destaque entra sozinho, centralizado, na maior letra que couber (ou no tamanho da cena). A
frase conceitual não divide o vidro com a fala do agente.

O layout de cada tela é decidido UMA vez, com o texto completo, e a revelação só corta: quebrando o
texto parcial, a última palavra pularia de linha a cada caractere e o bloco inteiro tremeria. Quando a
fala não cabe, o vidro rola como um terminal: a janela termina na linha em que a escrita está, não no
fim do texto, que ainda nem foi escrito.
"""
from PIL import Image, ImageDraw

import presets
from vfd import W, H

MODOS = ("caractere", "palavra", "linha")

_REGUA = ImageDraw.Draw(Image.new("1", (1, 1)))


def _linhas(texto, f):
    """Linhas que cabem na largura da tela, sem cortar palavra. Espaços repetidos viram um."""
    texto = " ".join((texto or "").split())
    return presets.quebrar_por_largura(texto, f) if texto else []


def _total(linhas):
    """Caracteres do bloco, contando a quebra de linha como o espaço que ela consumiu."""
    return sum(len(l) + 1 for l in linhas) - 1 if linhas else 0


def layout(fala, destaque, cena):
    """Decide fontes, linhas e alturas das duas telas uma vez. Devolve um dict que desenhar() e passos()
    consomem. destaque_tamanho = 0 escolhe a maior letra em que o destaque cabe, como o /texto faz."""
    f_fala = presets.fonte(cena["dialogo_peso"], cena["dialogo_tamanho"])
    alt_fala = sum(f_fala.getmetrics()) + presets.ENTRELINHA
    util = H - 2 * presets.MARGEM
    linhas_fala = _linhas(fala, f_fala)
    cabem = max(util // alt_fala, 1)

    linhas_dest, f_dest, alt_dest = [], None, 0
    if destaque:
        texto = " ".join(destaque.upper().split())
        if cena["destaque_tamanho"]:
            f_dest = presets.fonte(cena["destaque_peso"], cena["destaque_tamanho"])
            linhas_dest = presets.quebrar_por_largura(texto, f_dest)
        else:
            linhas_dest, tam = presets.arrumar_linhas(texto, cena["destaque_peso"])
            if tam == 0:
                raise ValueError("O destaque não cabe na tela nem com a menor letra.")
            f_dest = presets.fonte(cena["destaque_peso"], tam)
        alt_dest = sum(f_dest.getmetrics()) + presets.ENTRELINHA
    return {"fala": linhas_fala, "destaque": linhas_dest, "f_fala": f_fala, "f_dest": f_dest,
            "alt_fala": alt_fala, "alt_dest": alt_dest, "cabem": cabem,
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
    """PIL Image 256x128 modo '1'. Com revelado_destaque > 0 é a tela do destaque, sozinho e centralizado;
    senão é a tela da fala, cortada em revelado_fala. O x de cada linha do destaque sai da linha COMPLETA,
    não do pedaço revelado: senão ela se recentraliza a cada caractere e treme. A fala é alinhada à
    esquerda, como se lê um fluxo."""
    img = Image.new("1", (W, H), 0)
    d = ImageDraw.Draw(img)
    d.fontmode = "1"                              # a tela só tem aceso e apagado
    if revelado_destaque > 0 and lay["destaque"]:
        rev = revelado_destaque
        alto = len(lay["destaque"]) * lay["alt_dest"] - presets.ENTRELINHA
        y = max(presets.MARGEM, (H - alto) // 2)
        for linha in lay["destaque"]:
            x = (W - _REGUA.textlength(linha, font=lay["f_dest"])) / 2
            if rev > 0:
                d.text((x, y), linha[:rev], font=lay["f_dest"], fill=1, anchor="la")
            rev -= len(linha) + 1
            y += lay["alt_dest"]
        return img
    linhas, rev = _janela(lay["fala"], revelado_fala, lay["cabem"])
    alto = len(linhas) * lay["alt_fala"] - presets.ENTRELINHA
    y = presets.MARGEM + max(0, (H - 2 * presets.MARGEM - alto) // 2)
    for linha in linhas:
        if rev > 0:
            d.text((presets.MARGEM, y), linha[:rev], font=lay["f_fala"], fill=1, anchor="la")
        rev -= len(linha) + 1
        y += lay["alt_fala"]
    return img
