"""
presets.py — texto desenhado como BITMAP (não como texto da tela) e padrões de teste de pontos.

Por que bitmap: o texto nativo da tela só tem ASCII (perde o "é") e só tem 3 tamanhos fixos.
Desenhando com uma fonte TTF e mandando como imagem, os acentos aparecem e a letra ocupa a tela
inteira — que é o que importa atrás da lente Fresnel da escultura.

Fonte embutida: Roboto Condensed (licença SIL Open Font License), em assets/fonts/.
"""
import functools
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from vfd import W, H

PASTA_FONTES = Path(__file__).resolve().parent / "assets" / "fonts"
PESOS = {"light": "Roboto_Condensed-Light.ttf",
         "regular": "Roboto_Condensed-Regular.ttf",
         "medium": "Roboto_Condensed-Medium.ttf",
         "bold": "Roboto_Condensed-Bold.ttf",
         "black": "Roboto_Condensed-Black.ttf"}
TAM_MIN, TAM_MAX = 8, 120
MAX_LINHAS_AUTO = 6
MARGEM, ENTRELINHA = 3, -3     # entrelinha negativa: a fonte já traz respiro em cima e embaixo

# Frases prontas: as quebras de linha fazem parte do desenho.
PRESETS = {
    "devaneios": {
        "nome": "Devaneios do Aparato",
        "texto": "Devaneios do Aparato:\nA realidade é apenas\numa sombra da verdade.",
        "peso": "medium",
    },
    "sombra": {
        "nome": "A realidade é apenas uma sombra",
        "texto": "A realidade é apenas\numa sombra da verdade.",
        "peso": "medium",
    },
    "titulo": {
        "nome": "Devaneios do Aparato (só o título)",
        "texto": "Devaneios\ndo Aparato",
        "peso": "bold",
    },
    "acentos": {
        "nome": "Teste de acentos e números",
        "texto": "ÁÉÍÓÚ áéíóú ÃÕ ãõ Çç\nABCDEFGHIJKLM abcdefghijklm\n0123456789 .,:;!?",
        "peso": "regular",
    },
}

PADROES = {
    "cheio": "todos os pontos acesos",
    "xadrez": "xadrez (ponto sim, ponto não)",
    "xadrez_inv": "xadrez invertido",
    "apagado": "todos os pontos apagados",
}


@functools.lru_cache(maxsize=512)
def fonte(peso, tamanho):
    caminho = PASTA_FONTES / PESOS.get(peso, PESOS["medium"])
    return ImageFont.truetype(str(caminho), tamanho)


_REGUA = ImageDraw.Draw(Image.new("1", (1, 1)))


def _medir(linhas, f):
    """Largura da linha mais larga, altura total do bloco e altura de uma linha, em pontos."""
    largura = max(_REGUA.textlength(l, font=f) for l in linhas)
    sobe, desce = f.getmetrics()
    altura_linha = sobe + desce
    total = altura_linha * len(linhas) + ENTRELINHA * (len(linhas) - 1)
    return largura, total, altura_linha


def _cabe(linhas, peso, tam):
    largura, altura, _ = _medir(linhas, fonte(peso, tam))
    return largura <= W - 2 * MARGEM and altura <= H - 2 * MARGEM


def maior_tamanho(linhas, peso):
    """Maior tamanho de letra em que as linhas cabem em 256x128 (busca binária). 0 = não cabe."""
    if not _cabe(linhas, peso, TAM_MIN):
        return 0
    baixo, alto = TAM_MIN, TAM_MAX
    while baixo < alto:
        meio = (baixo + alto + 1) // 2
        if _cabe(linhas, peso, meio):
            baixo = meio
        else:
            alto = meio - 1
    return baixo


def quebrar(texto, n):
    """Divide o texto em até n linhas de tamanho parecido, sem cortar palavras."""
    palavras = texto.split()
    if n <= 1 or len(palavras) <= 1:
        return [" ".join(palavras)]
    alvo = len(" ".join(palavras)) / n
    linhas, atual = [], ""
    for p in palavras:
        candidata = (atual + " " + p).strip()
        if atual and len(candidata) > alvo and len(linhas) < n - 1:
            if abs(len(candidata) - alvo) < abs(len(atual) - alvo):
                linhas.append(candidata); atual = ""
            else:
                linhas.append(atual); atual = p
        else:
            atual = candidata
    if atual:
        linhas.append(atual)
    return linhas


def arrumar_linhas(texto, peso="medium"):
    """Decide as linhas e o tamanho da letra.
    - Se o texto tem Enter, respeita as quebras de quem digitou.
    - Se é uma linha só, testa de 1 a 6 linhas e fica com a divisão que dá a MAIOR letra."""
    texto = texto.replace("\r", "").replace("\t", " ").strip("\n")
    if not texto.strip():
        return [], 0
    if "\n" in texto:
        linhas = [l.strip() for l in texto.split("\n")]
        return linhas, maior_tamanho([l or " " for l in linhas], peso)
    melhor = ([], 0)
    for n in range(1, MAX_LINHAS_AUTO + 1):
        linhas = quebrar(texto, n)
        tam = maior_tamanho(linhas, peso)
        if tam > melhor[1]:
            melhor = (linhas, tam)
    return melhor


def quebrar_por_largura(texto, f):
    """Quebra o texto em linhas que cabem na largura da tela com a fonte f (tamanho manual)."""
    saida = []
    for paragrafo in texto.replace("\r", "").split("\n"):
        atual = ""
        for p in paragrafo.split():
            candidata = (atual + " " + p).strip()
            if atual and _REGUA.textlength(candidata, font=f) > W - 2 * MARGEM:
                saida.append(atual); atual = p
            else:
                atual = candidata
        saida.append(atual)
    return saida


def desenhar_texto(texto, peso="medium", tamanho=0):
    """Devolve (PIL Image 256x128 modo '1', tamanho da letra, nº de linhas, coube).
    tamanho=0: automático, a maior letra que cabe. tamanho>0: letra fixa; o que passar da tela
    é cortado e 'coube' volta False. Texto vazio = tela apagada."""
    img = Image.new("1", (W, H), 0)
    coube = True
    if not texto.strip():
        return img, 0, 0, True
    if tamanho:
        tam = max(TAM_MIN, min(TAM_MAX, int(tamanho)))
        linhas = quebrar_por_largura(texto.strip("\n"), fonte(peso, tam))
        coube = _cabe([l or " " for l in linhas], peso, tam)
    else:
        linhas, tam = arrumar_linhas(texto, peso)
        if tam == 0:
            raise ValueError("O texto não cabe na tela nem com a menor letra. Encurte o texto.")
    f = fonte(peso, tam)
    _, altura, altura_linha = _medir([l or " " for l in linhas], f)
    d = ImageDraw.Draw(img)
    d.fontmode = "1"                      # sem antisserrilhado: a tela só tem aceso/apagado
    y = (H - altura) // 2
    for linha in linhas:
        d.text((W // 2, y), linha, font=f, fill=1, anchor="ma")   # topo-centro
        y += altura_linha + ENTRELINHA
    return img, tam, len(linhas), coube


def desenhar_padrao(nome):
    """Padrões para conferir os pontos da tela."""
    if nome not in PADROES:
        raise ValueError(f"Padrão desconhecido: {nome}")
    if nome == "cheio":
        return Image.new("1", (W, H), 1)
    img = Image.new("1", (W, H), 0)
    if nome == "apagado":
        return img
    resto = 0 if nome == "xadrez" else 1
    px = img.load()
    for x in range(W):
        for y in range(H):
            if (x + y) % 2 == resto:
                px[x, y] = 1
    return img


def espelhar(img, horizontal=False, vertical=False):
    """Só para o caso de a montagem com a lente inverter a imagem."""
    if horizontal:
        img = ImageOps.mirror(img)
    if vertical:
        img = ImageOps.flip(img)
    return img


def lista():
    return [{"id": k, "nome": v["nome"], "texto": v["texto"], "peso": v.get("peso", "medium")}
            for k, v in PRESETS.items()]


# ================================================== escrita palavra a palavra e páginas
def layout_texto(texto, peso="medium", tamanho=0):
    """Decide linhas e tamanho UMA vez, para os quadros parciais não pularem.
    Devolve dict com linhas (lista de listas de palavras), fonte, y0, altura_linha, tam, coube."""
    texto = (texto or "").strip("\n")
    if not texto.strip():
        return None
    coube = True
    if tamanho:
        tam = max(TAM_MIN, min(TAM_MAX, int(tamanho)))
        linhas = quebrar_por_largura(texto, fonte(peso, tam))
        coube = _cabe([l or " " for l in linhas], peso, tam)
    else:
        linhas, tam = arrumar_linhas(texto, peso)
        if tam == 0:
            raise ValueError("O texto não cabe na tela nem com a menor letra. Encurte o texto.")
    f = fonte(peso, tam)
    _, altura, altura_linha = _medir([l or " " for l in linhas], f)
    return {"linhas": [l.split() for l in linhas], "fonte": f, "y0": (H - altura) // 2,
            "altura_linha": altura_linha, "tam": tam, "coube": coube,
            "palavras": sum(len(l.split()) for l in linhas)}


def desenhar_layout(lay, palavras_visiveis=None):
    """Desenha o layout mostrando só as primeiras N palavras (None = todas).
    Cada linha fica ancorada onde ficaria centralizada completa: o texto 'aparece' sem se mexer."""
    img = Image.new("1", (W, H), 0)
    if lay is None:
        return img
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    f, y = lay["fonte"], lay["y0"]
    restantes = lay["palavras"] if palavras_visiveis is None else max(0, palavras_visiveis)
    for palavras in lay["linhas"]:
        completa = " ".join(palavras)
        x0 = (W - _REGUA.textlength(completa, font=f)) / 2
        mostrar = palavras[:restantes]
        restantes -= len(mostrar)
        if mostrar:
            d.text((x0, y), " ".join(mostrar), font=f, fill=1, anchor="la")
        y += lay["altura_linha"] + ENTRELINHA
    return img


def paginar(texto, peso="medium", tamanho=0, tam_min=18):
    """Texto longo vira páginas que cabem com letra >= tam_min. Quebras manuais = 1 página só."""
    texto = (texto or "").strip()
    if not texto:
        return []
    if "\n" in texto or tamanho:
        return [texto]
    if maior_tamanho(quebrar(texto, 1), peso) >= tam_min or len(texto.split()) <= 2:
        # cabe inteiro (arrumar_linhas acha o melhor); testa rápido com a divisão automática
        if arrumar_linhas(texto, peso)[1] >= tam_min:
            return [texto]
    palavras = texto.split()
    paginas, i = [], 0
    while i < len(palavras):
        j = i + 1
        melhor = j
        # cresce a página enquanto couber com letra >= tam_min
        while j <= len(palavras):
            trecho = " ".join(palavras[i:j])
            if arrumar_linhas(trecho, peso)[1] >= tam_min:
                melhor = j
                j += 1
            else:
                break
        paginas.append(" ".join(palavras[i:melhor]))
        i = melhor
    return paginas
