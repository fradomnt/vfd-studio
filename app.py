#!/usr/bin/env python3
"""
app.py — VFD Studio: servidor local que controla a tela Noritake GU256X128C-3900.

Rodar:  python app.py      (abre http://127.0.0.1:8765 no navegador)

Regras de arquitetura:
- O servidor só escuta em 127.0.0.1 e recusa qualquer Host/Origin que não seja local.
- Este processo é o ÚNICO dono da porta serial: um objeto VFD por vez, protegido por um lock.
- Todo envio à serial roda num executor de 1 thread, com timeout, para o servidor nunca travar.
"""
import asyncio
import base64
import collections
import concurrent.futures
import contextlib
import threading
import time
import webbrowser
from pathlib import Path

import serial
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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
            "exposicao": expo.resumo()}


def publicar_status():
    hub.publicar({"tipo": "status", **status_atual()})


def publicar_previa():
    hub.publicar({"tipo": "previa", "bits": base64.b64encode(estado.previa).decode()})


def ao_enviar(n, segundos):
    """Gancho chamado pelo driver depois de cada envio."""
    registrar("tx", f"{n} B enviados em {segundos*1000:.0f} ms")


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


def _fechar_tela(motivo=None):
    """Fecha a porta e volta ao estado desconectado. Chamar com o lock já tomado ou sem tela em uso."""
    expo.parar_ev.set()                     # sem tela, a exposição para sozinha
    if estado.tela is not None:
        estado.tela.fechar()
    estado.tela = None
    if motivo:
        registrar("erro", motivo)
    publicar_status()


def com_tela(funcao):
    """Executa funcao(tela) na thread da serial, com lock. Erro de E/S = conversor perdido."""
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


# ======================================================== vigia do conversor
def vigia():
    """A cada 2 s confere se a porta conectada ainda existe (conversor desplugado)."""
    while True:
        time.sleep(2)
        porta = estado.porta
        if not estado.conectado or not porta:
            continue
        try:
            existentes = {p["porta"] for p in driver.portas()}
        except Exception:
            continue
        if porta not in existentes:
            with estado.lock:
                if estado.conectado and estado.porta == porta:
                    _fechar_tela(f"Conversor desconectado: a {porta} sumiu. "
                                 f"Plugue o USB e clique em Conectar.")


# ===================================================================== app
@contextlib.asynccontextmanager
async def ciclo_de_vida(_app):
    """Início: guarda o loop para o hub e liga o vigia. Fim: fecha a porta serial."""
    hub.loop = asyncio.get_running_loop()
    threading.Thread(target=vigia, daemon=True, name="vigia").start()
    registrar("info", "VFD Studio iniciado.")
    yield
    with estado.lock:
        if estado.tela is not None:
            estado.tela.fechar()
            estado.tela = None


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
            if estado.tela is not None:
                if estado.porta == pedido.porta:
                    return
                estado.tela.fechar()
                estado.tela = None
            try:
                # Abre sem inicializar: o botão "Inicializar tela" faz isso.
                estado.tela = driver.VFD(pedido.porta, iniciar=False, ao_enviar=ao_enviar)
            except (serial.SerialException, OSError, ValueError) as e:
                raise RuntimeError(mensagem_erro(e)) from e
            estado.porta = pedido.porta
    try:
        await na_serial(abrir)
    except Exception as e:
        publicar_status()
        return resposta_erro(e)
    registrar("info", f"Conectado em {pedido.porta} @ 38400 8N1.")
    publicar_status()
    return {"ok": True, **status_atual()}


@app.post("/api/desconectar")
async def desconectar():
    def fechar():
        with estado.lock:
            _fechar_tela()
    try:
        await na_serial(fechar)
    except Exception as e:
        return resposta_erro(e)
    registrar("info", "Desconectado.")
    return {"ok": True, **status_atual()}


@app.post("/api/iniciar")
async def inicializar():
    """1B 40 + brilho 100 % + cursor apagado (driver.VFD.iniciar), e limpa a prévia."""
    parar_exposicao("a tela foi inicializada")
    try:
        await na_serial(com_tela, lambda t: t.iniciar())
    except Exception as e:
        return resposta_erro(e)
    estado.previa = bytes(len(estado.previa))
    estado.brilho = 8
    publicar_previa()
    publicar_status()
    registrar("info", "Tela inicializada (1B 40): apagada, brilho 100 %.")
    return {"ok": True}


class PedidoDesenho(BaseModel):
    """Um desenho de tela inteira: texto digitado na hora ou padrão de teste de pontos."""
    tipo: str = "texto"            # "texto" ou "teste"
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
        info = {}
    elif pedido.tipo == "logo":
        from PIL import Image
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
    try:
        img, dados, descricao, info = _desenhar(pedido)
        await na_serial(com_tela, lambda t: t.bitmap(img))
    except Exception as e:
        return resposta_erro(e)
    estado.previa = dados
    publicar_previa()
    registrar("info", descricao)
    return {"ok": True, **info}


# ------------------------------------------------------------------ brilho
class PedidoBrilho(BaseModel):
    nivel: int


@app.post("/api/brilho")
async def ajustar_brilho(pedido: PedidoBrilho):
    """Brilho 1..8 (1F 58 11..18). Não interrompe a exposição."""
    nivel = max(1, min(8, pedido.nivel))
    try:
        await na_serial(com_tela, lambda t: t.brilho(nivel))
    except Exception as e:
        return resposta_erro(e)
    estado.brilho = nivel
    registrar("info", f"Brilho {nivel} de 8.")
    publicar_status()
    return {"ok": True, "brilho": nivel}


# --------------------------------------------------------------- exposição
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
    from PIL import Image
    i, passo = 0, 0
    troca_em = time.time() + pedido.segundos
    try:
        while not expo.parar_ev.is_set():
            dx, dy = DESLOCAMENTOS[passo % len(DESLOCAMENTOS)] if pedido.deslocar else (0, 0)
            quadro = Image.new("1", (driver.W, driver.H), 0)
            quadro.paste(imagens[i], (dx, dy))
            com_tela(lambda t: t.bitmap(quadro))
            estado.previa = driver.VFD._codificar(quadro)
            expo.frase = i + 1
            publicar_previa()
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
    parar_exposicao()
    expo.parar_ev.clear()
    expo.ativa, expo.frase, expo.total = True, 0, len(imagens)
    expo.thread = threading.Thread(target=_laco_exposicao, args=(pedido, imagens),
                                   daemon=True, name="exposicao")
    expo.thread.start()
    registrar("info", f"Exposição ligada: {len(imagens)} frase(s), {pedido.segundos} s cada"
                      f"{', com deslocamento' if pedido.deslocar else ''}.")
    return {"ok": True}


@app.post("/api/exposicao/parar")
def rota_parar_exposicao():
    parar_exposicao("pelo botão")
    publicar_status()
    return {"ok": True}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    origem = websocket.headers.get("origin", "")
    if websocket.headers.get("host", "") not in HOSTS_OK or \
            origem not in {f"http://{h}" for h in HOSTS_OK}:
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
    import uvicorn
    url = f"http://{HOST}:{PORTA_HTTP}"
    print(f"VFD Studio em {url}  (Ctrl+C para sair)")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=HOST, port=PORTA_HTTP, log_level="warning")


if __name__ == "__main__":
    main()
