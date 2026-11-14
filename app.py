#!/usr/bin/env python3
"""
app.py — VFD Studio: servidor local que controla a tela Noritake GU256X128C-3900.

Rodar:  python app.py      (abre http://127.0.0.1:8765 no navegador)

Regras de arquitetura:
- O servidor só escuta em 127.0.0.1 e recusa qualquer Host/Origin que não seja local.
- Este processo é o ÚNICO dono da porta serial: um objeto VFD por vez, protegido por um lock.
- Todo envio à serial roda num executor de 1 thread, com timeout, para o servidor nunca travar.
- Autonomia (museu): procura o conversor sozinho, mostra boas-vindas, liga o rodízio da cena padrão,
  reconecta se o USB sair. Frases que chegam pela API v1 interrompem o rodízio e, passado o tempo da
  cena, o rodízio volta sozinho. A tela nunca fica vazia por falta de quem mande.
"""
import asyncio
import base64
import collections
import concurrent.futures
import contextlib
import os
import threading
import time
import webbrowser
from pathlib import Path

import serial
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

import cenas
import presets
import vfd as driver

HOST, PORTA_HTTP = "127.0.0.1", 8765
PASTA = Path(__file__).resolve().parent
HOSTS_OK = {f"127.0.0.1:{PORTA_HTTP}", f"localhost:{PORTA_HTTP}"}
TIMEOUT_ENVIO = 10.0          # segundos; uma tela inteira leva ~1,1 s

# Textos de erro: o que aconteceu + o que fazer. Mesmo problema = mesma frase em todo lugar.
MSG_OCUPADA = ("Porta ocupada. Outro programa está usando o conversor (Arduino IDE, PuTTY, monitor "
               "serial ou outra janela do VFD Studio). Feche esse programa e clique em Conectar de novo.")
MSG_SUMIU = "Porta não encontrada. O USB pode ter saído. Plugue o conversor e clique em Atualizar."
MSG_TIMEOUT = ("A tela não recebeu os dados a tempo. Confira se a fonte de 5 V está ligada e se o USB "
               "está firme, depois tente de novo.")
MSG_SEM_CONEXAO = "Sem conexão. Escolha a porta e clique em Conectar."
MSG_SEM_CONVERSOR = "Nenhum conversor FTDI encontrado nas portas USB. Plugue o PCM-KW-469."


# ======================================================================= estado
class Estado:
    """Tudo que o servidor sabe sobre a tela. Acesso à serial só com self.lock."""

    def __init__(self):
        self.lock = threading.Lock()
        self.tela = None                    # objeto driver.VFD quando conectado
        self.porta = None
        self.brilho = 8                     # último nível enviado (1..8)
        self.log = collections.deque(maxlen=200)
        # Prévia: os mesmos 4096 bytes do formato da tela (colunas, bit7 = ponto de cima).
        self.previa = bytes(driver.W * driver.H // 8)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="serial")
        self.exibindo = "nada"              # nada | boas-vindas | rodizio | api | manual | teste
        self.parado_desde = None            # quando a imagem atual (não rodízio) entrou na tela
        self.ultima_api = None              # resumo da última frase recebida pela API

    @property
    def conectado(self):
        return self.tela is not None


estado = Estado()


class Exposicao:
    """Modo exposição: rodízio de frases com deslocamento de 1-2 pontos, para a tela não marcar."""

    def __init__(self):
        self.thread = None
        self.parar_ev = threading.Event()
        self.ativa = False
        self.frase, self.total = 0, 0
        self.pedido = None                  # último pedido, para o rodízio poder voltar sozinho

    def resumo(self):
        return {"ativa": self.ativa, "frase": self.frase, "total": self.total}


expo = Exposicao()


# ============================================================= WebSocket (hub)
class Hub:
    """Mantém as páginas abertas e distribui eventos (log, status, prévia).
    publicar() pode ser chamado de qualquer thread."""

    def __init__(self):
        self.clientes = set()
        self.loop = None

    async def _enviar_todos(self, msg):
        mortos = []
        for ws in list(self.clientes):
            try:
                await ws.send_json(msg)
            except Exception:
                mortos.append(ws)
        for ws in mortos:
            self.clientes.discard(ws)

    def publicar(self, msg):
        if self.loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._enviar_todos(msg), self.loop)
        except RuntimeError:
            pass                            # loop encerrando


hub = Hub()


def registrar(nivel, texto):
    """Acrescenta um evento ao log (máx. 200) e avisa as páginas."""
    item = {"t": time.strftime("%H:%M:%S"), "nivel": nivel, "msg": texto}
    estado.log.append(item)
    hub.publicar({"tipo": "log", "item": item})


def status_atual():
    return {"conectado": estado.conectado, "porta": estado.porta, "brilho": estado.brilho,
            "exposicao": expo.resumo(), "exibindo": estado.exibindo, "ultima_api": estado.ultima_api,
            "config": cenas.config()}


def publicar_status():
    hub.publicar({"tipo": "status", **status_atual()})


def publicar_previa():
    hub.publicar({"tipo": "previa", "bits": base64.b64encode(estado.previa).decode()})


def ao_enviar(n, segundos):
    """Gancho chamado pelo driver depois de cada envio."""
    registrar("tx", f"{n} B enviados em {segundos*1000:.0f} ms")


def mostrar(img, origem):
    """Manda uma imagem para a tela (na thread de quem chama, com lock) e atualiza a prévia."""
    com_tela(lambda t: t.bitmap(img))
    estado.previa = driver.VFD._codificar(img)
    estado.exibindo = origem
    # tela apagada não gasta; rodízio se cuida sozinho; o resto tem prazo (guarda-tela)
    estado.parado_desde = None if origem in ("rodizio", "nada") or not any(estado.previa) else time.time()
    publicar_previa()


# ============================================================ serial (thread)
def mensagem_erro(e):
    """Traduz erros do pyserial para mensagens claras na interface."""
    txt = str(e)
    baixo = txt.lower()
    if "acesso negado" in baixo or "access is denied" in baixo or "permissionerror" in baixo \
            or "resource busy" in baixo or "errno 16" in baixo:
        return MSG_OCUPADA
    if "filenotfounderror" in baixo or "could not open port" in baixo or "no such file" in baixo \
            or "o sistema não pode encontrar" in baixo:
        return MSG_SUMIU
    if isinstance(e, serial.SerialTimeoutException) or "timeout" in baixo:
        return MSG_TIMEOUT
    return f"Erro na serial: {txt}"


def _fechar_tela(motivo=None, apagar=False):
    """Fecha a porta e volta ao estado desconectado. Chamar com o lock já tomado ou sem tela em uso.
    apagar=True (desconexão pedida pelo usuário): limpa a tela antes, para não ficar imagem parada."""
    expo.parar_ev.set()                     # sem tela, a exposição para sozinha
    escrita.cancelar.set()
    if estado.tela is not None:
        if apagar:
            try:
                estado.tela.limpar()
                estado.tela.desligar()
            except Exception:
                pass                        # a porta pode já ter sumido
        estado.tela.fechar()
    estado.tela = None
    estado.exibindo = "nada"
    if motivo:
        registrar("erro", motivo)
    publicar_status()


def _abrir_porta(porta):
    """Abre a porta (sem mandar nada à tela). Chamar com o lock tomado. Levanta RuntimeError claro."""
    if estado.tela is not None:
        if estado.porta == porta:
            return
        estado.tela.fechar()
        estado.tela = None
    try:
        estado.tela = driver.VFD(porta, iniciar=False, ao_enviar=ao_enviar)
    except (serial.SerialException, OSError, ValueError) as e:
        raise RuntimeError(mensagem_erro(e)) from e
    estado.porta = porta


def com_tela(funcao):
    """Executa funcao(tela) com lock. Erro de E/S = conversor perdido."""
    with estado.lock:
        if estado.tela is None:
            raise RuntimeError(MSG_SEM_CONEXAO)
        try:
            return funcao(estado.tela)
        except (serial.SerialException, OSError) as e:
            porta = estado.porta
            _fechar_tela(f"Conexão com {porta} perdida. {mensagem_erro(e)}")
            raise RuntimeError(mensagem_erro(e)) from e


async def na_serial(funcao, *args):
    """Roda uma função bloqueante no executor da serial, com timeout."""
    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(estado.executor, funcao, *args)
    return await asyncio.wait_for(fut, timeout=TIMEOUT_ENVIO)


def resposta_erro(e, codigo=400):
    if isinstance(e, asyncio.TimeoutError):
        msg = MSG_TIMEOUT
    else:
        msg = str(e)
    registrar("erro", msg)
    return JSONResponse({"ok": False, "erro": msg}, status_code=codigo)


# =========================================================== cena em uso
def cena_atual():
    """(nome, cena) da cena padrão da configuração."""
    return cenas.obter(cenas.config()["cena_padrao"])


def imagens_do_rodizio(cena):
    imgs = []
    for f in cena["rodizio"]:
        img, _, _, _ = presets.desenhar_texto(f["texto"][:600], f.get("peso", cena["peso"]), f.get("tamanho", 0))
        imgs.append(presets.espelhar(img, cena["espelhar_h"], cena["espelhar_v"]))
    return imgs


def aplicar_brilho(nivel):
    nivel = max(1, min(8, int(nivel)))
    com_tela(lambda t: t.brilho(nivel))
    estado.brilho = nivel
    publicar_status()


# ====================================================================== rodízio
# Caminho do deslocamento: no máximo 2 pontos para cada lado. Cabe na margem de 3 pontos do texto.
DESLOCAMENTOS = [(0, 0), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1),
                 (2, 0), (0, 2), (-2, 0), (0, -2)]
SEGUNDOS_DESLOCAR = 60


class FraseExpo(BaseModel):
    texto: str
    peso: str = "medium"
    tamanho: int = 0


class PedidoExposicao(BaseModel):
    frases: list[FraseExpo]
    segundos: int = 120            # tempo de cada frase na tela
    deslocar: bool = True
    espelhar_h: bool = False
    espelhar_v: bool = False


def parar_exposicao(motivo=None):
    """Para o rodízio, se estiver ligado, e espera a thread sair."""
    if not expo.ativa:
        return
    expo.parar_ev.set()
    if expo.thread and expo.thread is not threading.current_thread():
        expo.thread.join(timeout=5)
    if motivo:
        registrar("info", f"Exposição parada: {motivo}.")


def _laco_exposicao(pedido, imagens):
    """Thread do rodízio. imagens = uma PIL Image por frase, já desenhada e espelhada."""
    i, passo = 0, 0
    troca_em = time.time() + pedido.segundos
    try:
        while not expo.parar_ev.is_set():
            dx, dy = DESLOCAMENTOS[passo % len(DESLOCAMENTOS)] if pedido.deslocar else (0, 0)
            quadro = Image.new("1", (driver.W, driver.H), 0)
            quadro.paste(imagens[i], (dx, dy))
            mostrar(quadro, "rodizio")
            expo.frase = i + 1
            publicar_status()
            falta = max(0.5, troca_em - time.time())
            espera = min(falta, SEGUNDOS_DESLOCAR) if pedido.deslocar else falta
            if expo.parar_ev.wait(espera):
                break
            passo += 1
            if time.time() >= troca_em:
                i = (i + 1) % len(imagens)
                troca_em = time.time() + pedido.segundos
    except Exception as e:
        registrar("erro", f"Exposição interrompida. {e}")
    finally:
        expo.ativa = False
        expo.frase = 0
        publicar_status()


def comecar_exposicao(pedido, imagens, origem="pela página"):
    """Liga o rodízio (pode ser chamado de qualquer thread)."""
    parar_exposicao()
    expo.parar_ev.clear()
    expo.pedido = (pedido, imagens)
    expo.ativa, expo.frase, expo.total = True, 0, len(imagens)
    expo.thread = threading.Thread(target=_laco_exposicao, args=(pedido, imagens),
                                   daemon=True, name="exposicao")
    expo.thread.start()
    registrar("info", f"Exposição ligada {origem}: {len(imagens)} frase(s), {pedido.segundos} s cada"
                      f"{', com deslocamento' if pedido.deslocar else ''}.")


def exposicao_da_cena(nome, cena):
    """Monta o pedido de rodízio a partir de uma cena. None se a cena não tem frases."""
    if not cena["rodizio"]:
        return None, None
    pedido = PedidoExposicao(frases=[FraseExpo(**f) for f in cena["rodizio"]], segundos=cena["segundos"],
                             deslocar=cena["deslocar"], espelhar_h=cena["espelhar_h"],
                             espelhar_v=cena["espelhar_v"])
    return pedido, imagens_do_rodizio(cena)


def voltar_ao_rodizio(motivo):
    """Depois de uma frase da API ou das boas-vindas: religa o rodízio da cena padrão, se configurado."""
    cfg = cenas.config()
    if not estado.conectado or not cfg["auto_exposicao"]:
        return
    nome, cena = cena_atual()
    pedido, imagens = exposicao_da_cena(nome, cena)
    try:
        if estado.brilho != cena["brilho"]:
            aplicar_brilho(cena["brilho"])
    except Exception as e:
        registrar("erro", f"Não consegui aplicar o brilho da cena: {e}")
    if pedido is None:
        registrar("info", f"Cena \"{nome}\" não tem rodízio; a tela fica com o último conteúdo.")
        return
    comecar_exposicao(pedido, imagens, f"({motivo}, cena \"{nome}\")")


# ============================================================ escrita pela API
class Escrita:
    """Uma frase vinda da API por vez. Uma nova cancela a anterior (a mais recente é a que vale)."""

    def __init__(self):
        self.lock = threading.Lock()        # garante uma escrita por vez
        self.cancelar = threading.Event()
        self.thread = None
        self.volta = None                   # Timer que religa o rodízio


escrita = Escrita()


def _escrever(texto, cena, nome_cena, modo, segundos, peso, tamanho, origem):
    """Thread: mostra o texto (inteiro ou palavra a palavra, em páginas) e agenda a volta do rodízio."""
    with escrita.lock:
        if escrita.cancelar.is_set():
            return
        try:
            parar_exposicao()
            if estado.brilho != cena["brilho"]:
                aplicar_brilho(cena["brilho"])
            paginas = presets.paginar(texto, peso, tamanho)
            por_quadro = cena["api_palavras_por_quadro"]
            for n_pag, pagina in enumerate(paginas, 1):
                lay = presets.layout_texto(pagina, peso, tamanho)
                total = lay["palavras"]
                if modo == "palavra":
                    vistas = 0
                    while vistas < total:
                        if escrita.cancelar.is_set():
                            return
                        vistas = min(total, vistas + por_quadro)
                        mostrar(presets.espelhar(presets.desenhar_layout(lay, vistas),
                                                 cena["espelhar_h"], cena["espelhar_v"]), "api")
                else:
                    mostrar(presets.espelhar(presets.desenhar_layout(lay), cena["espelhar_h"],
                                             cena["espelhar_v"]), "api")
                ultima = n_pag == len(paginas)
                # tempo de leitura da página: ~0,4 s por palavra, mínimo 3 s; a última fica 'segundos'
                espera = segundos if ultima else max(3.0, 1.5 + 0.4 * total)
                if ultima:
                    break
                if escrita.cancelar.wait(espera):
                    return
            estado.ultima_api = {"texto": texto[:120], "cena": nome_cena, "paginas": len(paginas),
                                 "letra": lay["tam"], "hora": time.strftime("%H:%M:%S"), "origem": origem}
            publicar_status()
            registrar("info", f"API: frase exibida ({len(paginas)} página(s), letra {lay['tam']} pt, "
                              f"modo {modo}); rodízio volta em {segundos} s.")
            escrita.volta = threading.Timer(segundos, voltar_ao_rodizio, args=("fim da frase da API",))
            escrita.volta.daemon = True
            escrita.volta.start()
        except Exception as e:
            registrar("erro", f"API: não consegui exibir a frase. {e}")


def exibir_pela_api(texto, nome_cena=None, modo=None, segundos=None, peso=None, tamanho=None, origem="api"):
    """Agenda a exibição de uma frase. Devolve o resumo do que vai acontecer."""
    if not estado.conectado:
        raise RuntimeError(MSG_SEM_CONEXAO)
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Texto vazio.")
    if len(texto) > 2000:
        raise ValueError("Texto longo demais (máximo de 2000 caracteres).")
    nome, cena = cenas.obter(nome_cena or cenas.config()["cena_padrao"])
    modo = modo if modo in ("palavra", "inteira") else cena["api_modo"]
    segundos = max(3, min(3600, int(segundos))) if segundos else cena["api_segundos"]
    peso = peso if peso in presets.PESOS else cena["peso"]
    tamanho = int(tamanho) if tamanho is not None else cena["tamanho"]
    paginas = presets.paginar(texto, peso, tamanho)
    lay = presets.layout_texto(paginas[0], peso, tamanho)

    # cancela a frase anterior e a volta agendada; a nova é a que vale
    escrita.cancelar.set()
    if escrita.volta:
        escrita.volta.cancel()
    if escrita.thread and escrita.thread.is_alive() and escrita.thread is not threading.current_thread():
        escrita.thread.join(timeout=5)
    escrita.cancelar.clear()
    escrita.thread = threading.Thread(target=_escrever, args=(texto, cena, nome, modo, segundos, peso,
                                                              tamanho, origem), daemon=True, name="escrita")
    escrita.thread.start()
    registrar("info", f"API ({origem}): \"{texto[:60]}{'…' if len(texto) > 60 else ''}\" → cena \"{nome}\", "
                      f"modo {modo}, {len(paginas)} página(s).")
    return {"ok": True, "cena": nome, "modo": modo, "paginas": len(paginas), "letra": lay["tam"],
            "palavras": sum(len(p.split()) for p in paginas), "segundos": segundos}


# ================================================================ autonomia
class Autonomia:
    def __init__(self):
        self.ultimo_erro = None             # para não repetir o mesmo aviso a cada 3 s
        self.tentativas = 0


auto = Autonomia()


def boas_vindas():
    cfg = cenas.config()
    if not cfg["boas_vindas"]:
        return
    texto = cfg["boas_vindas_texto"].replace("{hora}", time.strftime("%H:%M"))
    img, _, _, _ = presets.desenhar_texto(texto, "medium", 0)
    _, cena = cena_atual()
    mostrar(presets.espelhar(img, cena["espelhar_h"], cena["espelhar_v"]), "boas-vindas")


def iniciar_e_apagar_duas_vezes(tela):
    """Ao iniciar: 1B 40 e dois 0C seguidos, rápido. Garante tela limpa mesmo que o primeiro
    comando chegue com a tela ainda acordando."""
    tela.iniciar()
    tela.limpar()
    time.sleep(0.15)
    tela.limpar()
    estado.previa = bytes(len(estado.previa))
    estado.exibindo = "nada"
    estado.parado_desde = None
    publicar_previa()


def apagar_ao_sair():
    """Ao encerrar o app: apaga a tela e desliga o display, para não ficar imagem parada queimando."""
    with estado.lock:
        if estado.tela is None:
            return
        try:
            estado.tela.limpar()
            estado.tela.desligar()
            print("Tela apagada ao sair.")
        except Exception as e:
            print(f"Não consegui apagar a tela ao sair: {e}")
        finally:
            estado.tela.fechar()
            estado.tela = None


def conectar_sozinho():
    """Procura o conversor, conecta, inicializa, aplica o brilho da cena e mostra as boas-vindas.
    Roda na thread da autonomia. Devolve True se conectou."""
    porta = driver.porta_preferida()
    if not porta:
        if auto.ultimo_erro != MSG_SEM_CONVERSOR:
            registrar("erro", MSG_SEM_CONVERSOR + " Vou tentar de novo a cada 3 s.")
            auto.ultimo_erro = MSG_SEM_CONVERSOR
        return False
    try:
        with estado.lock:
            _abrir_porta(porta)
    except RuntimeError as e:
        if auto.ultimo_erro != str(e):
            registrar("erro", f"Conexão automática em {porta} falhou. {e} Vou tentar de novo a cada 3 s.")
            auto.ultimo_erro = str(e)
        return False
    auto.ultimo_erro = None
    registrar("info", f"Conectado sozinho em {porta} @ 38400 8N1.")
    publicar_status()
    try:
        com_tela(iniciar_e_apagar_duas_vezes)
        nome, cena = cena_atual()
        aplicar_brilho(cena["brilho"])
        boas_vindas()
        cfg = cenas.config()
        registrar("info", f"Tela inicializada; brilho {cena['brilho']} de 8 (cena \"{nome}\").")
        if cfg["auto_exposicao"]:
            t = threading.Timer(cfg["boas_vindas_segundos"] if cfg["boas_vindas"] else 0.5,
                                voltar_ao_rodizio, args=("início automático",))
            t.daemon = True
            t.start()
    except Exception as e:
        registrar("erro", f"Conectei, mas a tela não respondeu bem: {e}")
    return True


def guarda_tela(cfg):
    """Imagem parada há tempo demais: volta ao rodízio ou apaga. Protege o fósforo da tela."""
    if not cfg["guarda_tela"] or not estado.conectado or estado.parado_desde is None:
        return
    if escrita.thread and escrita.thread.is_alive() and estado.exibindo == "api":
        return                                  # frase da API ainda sendo escrita (quadros mudando)
    limite = cfg["teste_segundos"] if estado.exibindo == "teste" else cfg["guarda_tela_segundos"]
    if time.time() - estado.parado_desde < limite:
        return
    motivo = f"guarda-tela: \"{estado.exibindo}\" parado há {int(time.time() - estado.parado_desde)} s"
    if escrita.volta:
        escrita.volta.cancel()
    nome, cena = cena_atual()
    if cfg["auto_exposicao"] and cena["rodizio"]:
        voltar_ao_rodizio(motivo)
    else:
        mostrar(Image.new("1", (driver.W, driver.H), 0), "nada")
        registrar("info", f"Tela apagada ({motivo}).")


def laco_autonomia():
    """A cada 3 s: se configurado e desconectado, tenta conectar. Se conectado, vigia se a porta sumiu."""
    time.sleep(1.5)
    while True:
        try:
            cfg = cenas.config()
            if estado.conectado:
                porta = estado.porta
                existentes = {p["porta"] for p in driver.portas()}
                if porta and porta not in existentes:
                    with estado.lock:
                        if estado.conectado and estado.porta == porta:
                            _fechar_tela(f"Conversor desconectado: a {porta} sumiu. "
                                         + ("Vou reconectar sozinho quando voltar." if cfg["auto_conectar"]
                                            else "Plugue o USB e clique em Conectar."))
            elif cfg["auto_conectar"]:
                conectar_sozinho()
            guarda_tela(cfg)
        except Exception as e:
            registrar("erro", f"Vigia: {e}")
        time.sleep(3)


# ===================================================================== app
@contextlib.asynccontextmanager
async def ciclo_de_vida(_app):
    """Início: guarda o loop para o hub e liga a autonomia. Fim: fecha a porta serial."""
    hub.loop = asyncio.get_running_loop()
    cenas.garantir_arquivos()
    threading.Thread(target=laco_autonomia, daemon=True, name="autonomia").start()
    cfg = cenas.config()
    registrar("info", "VFD Studio iniciado." + (" Procurando o conversor…" if cfg["auto_conectar"] else ""))
    yield
    escrita.cancelar.set()
    expo.parar_ev.set()
    if expo.thread and expo.thread.is_alive():
        expo.thread.join(timeout=3)
    if escrita.thread and escrita.thread.is_alive():
        escrita.thread.join(timeout=3)
    apagar_ao_sair()


app = FastAPI(title="VFD Studio", docs_url=None, redoc_url=None, openapi_url=None,
              lifespan=ciclo_de_vida)


@app.middleware("http")
async def so_local(request: Request, chamada):
    """Recusa clientes que não sejam desta máquina e Host estranho (proteção contra DNS rebinding)."""
    cliente = request.client.host if request.client else ""
    if cliente not in ("127.0.0.1", "::1") or request.headers.get("host", "") not in HOSTS_OK:
        return JSONResponse({"ok": False, "erro": "Acesso recusado: o VFD Studio só aceita conexões deste computador."}, status_code=403)
    return await chamada(request)


# ----------------------------------------------------------------- rotas
class PedidoConectar(BaseModel):
    porta: str


@app.get("/")
def pagina():
    return FileResponse(PASTA / "static" / "index.html")


@app.get("/api/portas")
def listar_portas():
    lista = driver.portas()
    sugerida = next((p["porta"] for p in lista if p["conversor"]), None) \
        or next((p["porta"] for p in lista if p["ftdi"]), None)
    return {"portas": lista, "sugerida": sugerida}


@app.get("/api/estado")
def ler_estado():
    return {**status_atual(), "log": list(estado.log),
            "previa": base64.b64encode(estado.previa).decode()}


@app.post("/api/conectar")
async def conectar(pedido: PedidoConectar):
    def abrir():
        with estado.lock:
            _abrir_porta(pedido.porta)
    try:
        await na_serial(abrir)
    except Exception as e:
        publicar_status()
        return resposta_erro(e)
    auto.ultimo_erro = None
    registrar("info", f"Conectado em {pedido.porta} @ 38400 8N1.")
    publicar_status()
    return {"ok": True, **status_atual()}


@app.post("/api/desconectar")
async def desconectar():
    def fechar():
        parar_exposicao()
        with estado.lock:
            _fechar_tela(apagar=True)
    try:
        await na_serial(fechar)
    except Exception as e:
        return resposta_erro(e)
    # desconectar à mão desliga a conexão automática, senão ela reconecta em 3 s
    cenas.salvar_config({"auto_conectar": False})
    estado.previa = bytes(len(estado.previa))
    publicar_previa()
    registrar("info", "Tela apagada e desconectada. A conexão automática foi desligada; religue no cartão Automático.")
    publicar_status()
    return {"ok": True, **status_atual()}


@app.post("/api/iniciar")
async def inicializar():
    """1B 40 + brilho 100 % + cursor apagado (driver.VFD.iniciar), e limpa a prévia."""
    parar_exposicao("a tela foi inicializada")
    escrita.cancelar.set()
    try:
        await na_serial(com_tela, iniciar_e_apagar_duas_vezes)
    except Exception as e:
        return resposta_erro(e)
    estado.brilho = 8
    publicar_status()
    registrar("info", "Tela inicializada (1B 40) e apagada duas vezes; brilho 100 %.")
    return {"ok": True}


class PedidoDesenho(BaseModel):
    """Um desenho de tela inteira: texto digitado na hora, logo ou padrão de teste de pontos."""
    tipo: str = "texto"            # "texto", "logo" ou "teste"
    texto: str = ""
    peso: str = "medium"           # light | regular | medium | bold | black
    tamanho: int = 0               # 0 = automático (maior letra que cabe); senão, pontos
    padrao: str = "cheio"          # cheio | xadrez | xadrez_inv | apagado
    espelhar_h: bool = False
    espelhar_v: bool = False


def _desenhar(pedido):
    """Devolve (imagem, bits no formato da tela, descrição para o log, info para a página)."""
    if pedido.tipo == "teste":
        img = presets.desenhar_padrao(pedido.padrao)
        descricao = f"Teste de pontos: {presets.PADROES[pedido.padrao]}."
        info = {"origem": "teste"}
    elif pedido.tipo == "logo":
        img = Image.open(PASTA / "assets" / "logo_vfd_256x128.png").convert("1")
        descricao = "Logo frado enviada."
        info = {}
    elif pedido.tipo == "texto":
        if len(pedido.texto) > 600:
            raise ValueError("Texto longo demais para a tela (máximo de 600 caracteres).")
        img, tam, n, coube = presets.desenhar_texto(pedido.texto, pedido.peso, pedido.tamanho)
        descricao = f"Texto enviado (letra {tam} pt, {n} linha{'s' if n != 1 else ''})." if n \
            else "Texto vazio: tela apagada."
        info = {"letra": tam, "linhas": n, "coube": coube}
    else:
        raise ValueError(f"Tipo de desenho desconhecido: {pedido.tipo}")
    img = presets.espelhar(img, pedido.espelhar_h, pedido.espelhar_v)
    return img, driver.VFD._codificar(img), descricao, info


@app.get("/api/presets")
def listar_presets():
    return {"presets": presets.lista()}


@app.post("/api/desenho/previa")
def previa_desenho(pedido: PedidoDesenho):
    """Só desenha: devolve os bits para a página. Não manda nada para a tela."""
    try:
        _, dados, _, info = _desenhar(pedido)
    except Exception as e:
        return JSONResponse({"ok": False, "erro": str(e)}, status_code=400)
    return {"ok": True, "bits": base64.b64encode(dados).decode(), **info}


@app.post("/api/desenho/enviar")
async def enviar_desenho(pedido: PedidoDesenho):
    parar_exposicao("houve um envio manual")
    escrita.cancelar.set()
    if escrita.volta:
        escrita.volta.cancel()
    try:
        img, dados, descricao, info = _desenhar(pedido)
        await na_serial(mostrar, img, info.pop("origem", "manual"))
    except Exception as e:
        return resposta_erro(e)
    registrar("info", descricao)
    return {"ok": True, **info}


# ------------------------------------------------------------------ brilho
class PedidoBrilho(BaseModel):
    nivel: int


@app.post("/api/brilho")
async def ajustar_brilho(pedido: PedidoBrilho):
    """Brilho 1..8 (1F 58 11..18). Não interrompe a exposição."""
    try:
        await na_serial(aplicar_brilho, pedido.nivel)
    except Exception as e:
        return resposta_erro(e)
    registrar("info", f"Brilho {estado.brilho} de 8.")
    return {"ok": True, "brilho": estado.brilho}


# --------------------------------------------------------------- exposição
@app.post("/api/exposicao/iniciar")
async def iniciar_exposicao(pedido: PedidoExposicao):
    try:
        if not estado.conectado:
            raise RuntimeError(MSG_SEM_CONEXAO)
        frases = [f for f in pedido.frases if f.texto.strip()]
        if not frases:
            raise ValueError("Ponha pelo menos uma frase no rodízio.")
        if len(frases) > 30:
            raise ValueError("O rodízio aceita até 30 frases.")
        pedido.segundos = max(5, min(3600, pedido.segundos))
        imagens = []
        for f in frases:
            img, _, _, _ = presets.desenhar_texto(f.texto[:600], f.peso, f.tamanho)
            imagens.append(presets.espelhar(img, pedido.espelhar_h, pedido.espelhar_v))
    except Exception as e:
        return resposta_erro(e)
    escrita.cancelar.set()
    if escrita.volta:
        escrita.volta.cancel()
    comecar_exposicao(pedido, imagens)
    return {"ok": True}


@app.post("/api/exposicao/parar")
def rota_parar_exposicao():
    parar_exposicao("pelo botão")
    publicar_status()
    return {"ok": True}


# ------------------------------------------------------------- cenas e config
class PedidoCena(BaseModel):
    nome: str
    cena: dict


@app.get("/api/cenas")
def listar_cenas():
    return {"cenas": cenas.todas(), "config": cenas.config()}


@app.post("/api/cenas")
def salvar_cena(pedido: PedidoCena):
    try:
        nome = cenas.salvar(pedido.nome, pedido.cena)
    except Exception as e:
        return JSONResponse({"ok": False, "erro": str(e)}, status_code=400)
    registrar("info", f"Cena \"{nome}\" salva em cenas.json.")
    return {"ok": True, "nome": nome, "cenas": cenas.todas()}


@app.delete("/api/cenas/{nome}")
def apagar_cena(nome: str):
    try:
        cenas.apagar(nome)
    except Exception as e:
        return JSONResponse({"ok": False, "erro": str(e)}, status_code=400)
    registrar("info", f"Cena \"{nome}\" apagada.")
    return {"ok": True, "cenas": cenas.todas()}


@app.post("/api/config")
def salvar_config(novo: dict):
    cfg = cenas.salvar_config(novo)
    registrar("info", "Configuração salva em config.json.")
    publicar_status()
    return {"ok": True, "config": cfg}


@app.post("/api/cenas/{nome}/aplicar")
async def aplicar_cena(nome: str):
    """Vira a cena padrão, aplica o brilho e (se auto_exposicao) liga o rodízio dela."""
    if nome not in cenas.todas():
        return JSONResponse({"ok": False, "erro": f"Cena \"{nome}\" não existe."}, status_code=400)
    cenas.salvar_config({"cena_padrao": nome})
    _, cena = cenas.obter(nome)
    if estado.conectado:
        try:
            await na_serial(aplicar_brilho, cena["brilho"])
        except Exception as e:
            return resposta_erro(e)
        escrita.cancelar.set()
        if escrita.volta:
            escrita.volta.cancel()
        voltar_ao_rodizio(f"cena \"{nome}\" aplicada")
    registrar("info", f"Cena padrão agora é \"{nome}\".")
    publicar_status()
    return {"ok": True}


# ------------------------------------------------------------------ API v1
class PedidoTextoV1(BaseModel):
    """O que o app do Marlus manda. Só 'texto' é obrigatório; o resto vem da cena."""
    texto: str
    cena: str | None = None
    modo: str | None = None        # "palavra" ou "inteira"
    segundos: int | None = None    # quanto tempo fica antes do rodízio voltar
    peso: str | None = None
    tamanho: int | None = None
    origem: str = "api"            # nome do app que mandou, só para o log


@app.post("/api/v1/texto")
def api_v1_texto(pedido: PedidoTextoV1):
    try:
        return exibir_pela_api(pedido.texto, pedido.cena, pedido.modo, pedido.segundos, pedido.peso,
                               pedido.tamanho, pedido.origem[:30])
    except Exception as e:
        return resposta_erro(e, 503 if str(e) == MSG_SEM_CONEXAO else 400)


@app.get("/api/v1/estado")
def api_v1_estado():
    nome, cena = cena_atual()
    return {"ok": True, "conectado": estado.conectado, "porta": estado.porta, "exibindo": estado.exibindo,
            "cena_padrao": nome, "cenas": sorted(cenas.todas()), "ultima": estado.ultima_api,
            "tela": {"largura": driver.W, "altura": driver.H}}


@app.post("/api/v1/limpar")
async def api_v1_limpar():
    """Apaga a tela e para tudo (rodízio e frase em exibição)."""
    parar_exposicao("API pediu para limpar")
    escrita.cancelar.set()
    if escrita.volta:
        escrita.volta.cancel()
    try:
        await na_serial(mostrar, Image.new("1", (driver.W, driver.H), 0), "api")
    except Exception as e:
        return resposta_erro(e, 503)
    return {"ok": True}


@app.post("/api/v1/rodizio")
def api_v1_rodizio():
    """Volta ao rodízio da cena padrão agora."""
    escrita.cancelar.set()
    if escrita.volta:
        escrita.volta.cancel()
    try:
        voltar_ao_rodizio("API pediu o rodízio")
    except Exception as e:
        return resposta_erro(e, 503)
    return {"ok": True, "exposicao": expo.resumo()}


# --------------------------------------------------------------- WebSocket
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    origem = websocket.headers.get("origin", "")
    if websocket.headers.get("host", "") not in HOSTS_OK or \
            (origem and origem not in {f"http://{h}" for h in HOSTS_OK}):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    hub.clientes.add(websocket)
    try:
        await websocket.send_json({"tipo": "inicial", **status_atual(), "log": list(estado.log),
                                   "previa": base64.b64encode(estado.previa).decode()})
        while True:
            await websocket.receive_text()   # só mantém a conexão; comandos vão por HTTP
    except WebSocketDisconnect:
        pass
    finally:
        hub.clientes.discard(websocket)


app.mount("/static", StaticFiles(directory=PASTA / "static"), name="static")


# ====================================================================== main
def main():
    import atexit
    import signal
    import uvicorn
    atexit.register(apagar_ao_sair)
    # SIGTERM (launchctl, kill) → uvicorn encerra com graça e o ciclo_de_vida apaga a tela;
    # SIGHUP (janela do Terminal fechada no Mac) não é tratado pelo uvicorn: apagamos e saímos.
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, lambda *_: (apagar_ao_sair(), os._exit(0)))
    url = f"http://{HOST}:{PORTA_HTTP}"
    print(f"VFD Studio em {url}  (Ctrl+C para sair)")
    if not os.environ.get("VFD_SEM_NAVEGADOR"):      # no início automático do Mac não há quem veja
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=HOST, port=PORTA_HTTP, log_level="warning")


if __name__ == "__main__":
    main()
