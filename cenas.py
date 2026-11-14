"""
cenas.py — cenas salvas em arquivo (cenas.json) e configuração de autonomia (config.json).

Uma CENA guarda toda a aparência: espessura e tamanho da letra, espelhar, brilho, rodízio de frases,
tempo de cada frase, deslocamento, e como as frases vindas da API devem aparecer. Quem manda texto pela
API (o app do Marlus) só diz o nome da cena; a forma é decidida aqui, no VFD Studio.

Os arquivos ficam na pasta do app, para valer em qualquer navegador e sobreviver a reinício.
"""
import json
import threading
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQ_CENAS = PASTA / "cenas.json"
ARQ_CONFIG = PASTA / "config.json"
_lock = threading.Lock()

CENA_PADRAO = {
    "peso": "medium",
    "tamanho": 0,                  # 0 = automático
    "espelhar_h": False,
    "espelhar_v": False,
    "brilho": 6,
    "segundos": 120,               # tempo de cada frase do rodízio
    "deslocar": True,
    "rodizio": [
        {"texto": "Devaneios do Aparato:\nA realidade é apenas\numa sombra da verdade.",
         "peso": "medium", "tamanho": 0},
    ],
    # frases vindas da API
    "api_modo": "palavra",         # "palavra" (vai escrevendo) ou "inteira"
    "api_palavras_por_quadro": 1,  # no modo palavra; cada quadro leva ~1 s na tela
    "api_segundos": 90,            # quanto tempo a frase fica depois de pronta, antes de voltar ao rodízio
}

CONFIG_PADRAO = {
    "auto_conectar": True,         # ao ligar e sempre que a porta sumir, procura o conversor sozinho
    "auto_exposicao": True,        # depois de conectar, liga o rodízio da cena padrão
    "cena_padrao": "museu",
    "boas_vindas": True,           # mostra a mensagem abaixo na tela ao conectar
    "boas_vindas_texto": "Tekne Studio\nVFD pronto · {hora}\naguardando frases",
    "boas_vindas_segundos": 8,     # depois disso entra o rodízio da cena (se auto_exposicao)
}


def _ler(arq, padrao):
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return json.loads(json.dumps(padrao))
    except json.JSONDecodeError:
        # arquivo corrompido: guarda uma cópia e recomeça do padrão
        arq.rename(arq.with_suffix(".json.quebrado"))
        return json.loads(json.dumps(padrao))


def _gravar(arq, dados):
    tmp = arq.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(arq)                # troca atômica: nunca fica meio arquivo


def normalizar(cena):
    """Completa campos que faltam e limita valores."""
    c = {**CENA_PADRAO, **{k: v for k, v in cena.items() if k in CENA_PADRAO}}
    c["peso"] = c["peso"] if c["peso"] in ("light", "regular", "medium", "bold", "black") else "medium"
    c["tamanho"] = max(0, min(120, int(c["tamanho"] or 0)))
    c["brilho"] = max(1, min(8, int(c["brilho"])))
    c["segundos"] = max(5, min(3600, int(c["segundos"])))
    c["api_modo"] = c["api_modo"] if c["api_modo"] in ("palavra", "inteira") else "palavra"
    c["api_palavras_por_quadro"] = max(1, min(5, int(c["api_palavras_por_quadro"])))
    c["api_segundos"] = max(3, min(3600, int(c["api_segundos"])))
    c["rodizio"] = [{"texto": str(f.get("texto", ""))[:600], "peso": f.get("peso", c["peso"]),
                     "tamanho": int(f.get("tamanho", 0) or 0)}
                    for f in c.get("rodizio", []) if str(f.get("texto", "")).strip()][:30]
    return c


def todas():
    with _lock:
        dados = _ler(ARQ_CENAS, {"museu": CENA_PADRAO})
    return {nome: normalizar(c) for nome, c in dados.items()}


def obter(nome):
    """Cena pelo nome; se não existir, a padrão da configuração; se nem essa, a primeira."""
    lista = todas()
    if nome in lista:
        return nome, lista[nome]
    padrao = config()["cena_padrao"]
    if padrao in lista:
        return padrao, lista[padrao]
    if lista:
        primeiro = sorted(lista)[0]
        return primeiro, lista[primeiro]
    return "museu", normalizar(CENA_PADRAO)


def salvar(nome, cena):
    nome = nome.strip()[:40]
    if not nome:
        raise ValueError("Dê um nome à cena.")
    with _lock:
        dados = _ler(ARQ_CENAS, {"museu": CENA_PADRAO})
        dados[nome] = normalizar(cena)
        _gravar(ARQ_CENAS, dados)
    return nome


def apagar(nome):
    with _lock:
        dados = _ler(ARQ_CENAS, {"museu": CENA_PADRAO})
        if nome not in dados:
            raise ValueError(f"Cena \"{nome}\" não existe.")
        if len(dados) == 1:
            raise ValueError("Não dá para apagar a única cena.")
        del dados[nome]
        _gravar(ARQ_CENAS, dados)


def config():
    with _lock:
        return {**CONFIG_PADRAO, **_ler(ARQ_CONFIG, CONFIG_PADRAO)}


def salvar_config(novo):
    with _lock:
        atual = {**CONFIG_PADRAO, **_ler(ARQ_CONFIG, CONFIG_PADRAO)}
        atual.update({k: v for k, v in novo.items() if k in CONFIG_PADRAO})
        _gravar(ARQ_CONFIG, atual)
        return atual


def garantir_arquivos():
    """Cria cenas.json e config.json na primeira vez, para o usuário ver onde ficam."""
    with _lock:
        if not ARQ_CENAS.exists():
            _gravar(ARQ_CENAS, {"museu": CENA_PADRAO})
        if not ARQ_CONFIG.exists():
            _gravar(ARQ_CONFIG, CONFIG_PADRAO)
