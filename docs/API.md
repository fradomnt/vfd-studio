# Manual da API do VFD Studio — para integrar o Devaneios do Aparato (`aparatus`)

Este manual é para quem vai escrever na tela VFD controlada pelo VFD Studio a partir de
outro programa. Há dois caminhos:

- **Texto** (`POST /api/v1/texto`): o seu app manda a frase; o VFD Studio cuida de tudo o mais
  (letra, acentos, tamanho, brilho, páginas, desgaste da tela, e o que mostrar quando você não manda nada).
- **Quadro** (`POST /api/v1/quadro`, seção 3b): o seu app desenha o bitmap 256×128 e manda pronto; o
  VFD Studio cuida da serial, da reconexão, do brilho, do guarda-tela e do rodízio de fallback. É o
  caminho do `aparatus`, que datilografa a fala do agente e mantém o vidro sempre ocupado.

Não é preciso saber nada da tela, da porta serial ou do protocolo Noritake.

---

## 1. Em 60 segundos

O VFD Studio precisa estar aberto **no mesmo computador** (na instalação, ele abre sozinho ao ligar o Mac
mini e fica em segundo plano). Então:

```bash
curl -X POST http://127.0.0.1:8765/api/v1/texto \
  -H "Content-Type: application/json" \
  -d '{"texto": "A dúvida é o começo da sabedoria."}'
```

Resposta:

```json
{"ok": true, "cena": "museu", "modo": "palavra", "paginas": 1, "letra": 31, "palavras": 7, "segundos": 90}
```

E a frase aparece na tela, palavra por palavra. Pronto: isso é 90 % da integração.

---

## 2. Como testar sem a tela

1. Clone o repositório e abra o VFD Studio (`iniciar.command` no Mac, `iniciar.bat` no Windows, ou o
   executável das [Releases](https://github.com/fradomnt/vfd-studio/releases)).
2. Sem a tela ligada, a página em `http://127.0.0.1:8765` mostra "desconectado" e a API responde
   `503` (seção 6). **Para desenvolver sem a tela**, rode com a tela simulada:

   ```bash
   VFD_SIMULADO=1 VFD_SEM_NAVEGADOR=1 python app.py      # Mac/Linux (no Windows: set VFD_SIMULADO=1)
   ```

   O app conecta sozinho na "porta" `simulado`, a API responde `200` e tudo o que você mandar aparece
   na prévia ponto a ponto da página (`http://127.0.0.1:8765`). Nada sai pela serial. Cada envio dorme o
   tempo que levaria no fio (3840 B/s), então a cadência das respostas é a do vidro de verdade.
   `GET /api/v1/estado` devolve `"simulado": true` nesse modo.
3. Com a tela ligada, o cartão *Outro app escrevendo na tela* tem o botão **Testar agora**, que faz a
   mesma chamada que o seu app fará.

---

## 3. Referência

Base: `http://127.0.0.1:8765`. Só aceita chamadas do próprio computador. Sem chave, sem login.
Toda resposta é JSON com `"ok": true` ou `"ok": false` mais `"erro"` (texto em português, para log).

### `POST /api/v1/texto` — mostrar uma frase

Corpo JSON. Só `texto` é obrigatório.

| Campo | Tipo | O que faz | Se omitir |
|---|---|---|---|
| `texto` | string | a frase. Até 2000 caracteres. Acentos ok. `\n` força quebra de linha | obrigatório |
| `cena` | string | nome de uma cena salva no VFD Studio (seção 4) | cena padrão |
| `modo` | `"palavra"` \| `"inteira"` | aparece escrevendo, ou de uma vez | o da cena |
| `segundos` | inteiro 3–3600 | quanto tempo fica depois de pronta, antes de o rodízio voltar | o da cena |
| `peso` | `light` `regular` `medium` `bold` `black` | espessura da letra | o da cena |
| `tamanho` | inteiro 8–120, ou 0 | tamanho da letra em pontos; 0 = o maior que couber | o da cena |
| `origem` | string | nome do seu app, só para o log do VFD Studio | `"api"` |

Resposta `200`:

| Campo | Significado |
|---|---|
| `cena` | cena usada |
| `modo` | modo usado |
| `paginas` | em quantas telas o texto foi dividido |
| `letra` | tamanho da letra da primeira página, em pontos |
| `palavras` | total de palavras |
| `segundos` | quanto tempo a última página fica antes de o rodízio voltar |

A resposta volta **na hora**; a escrita acontece em seguida, em segundo plano.

### `POST /api/v1/dialogo` — a fala da obra e o destaque

O caminho do **Devaneios do Aparato**: o aparatus manda a fala do agente e, na convergência, o destaque;
o VFD Studio escreve a fala na letra do fluxo e o destaque embaixo, na letra maior, sem apagar a fala.
Letra, peso, tamanho, modo de revelação e cadência vêm da cena (seção 4): quem opera o vidro ajusta
pela página, e o app que manda não muda.

Corpo JSON. `fala` ou `destaque` precisa vir; os dois podem vir juntos.

| Campo | Tipo | O que faz | Se omitir |
|---|---|---|---|
| `fala` | string | o que o agente disse. Até 2000 caracteres; espaços repetidos viram um | vazio |
| `destaque` | string | a frase da convergência, escrita em maiúsculas embaixo da fala. Até 200 caracteres | vazio |
| `cena` | string | nome de uma cena salva (seção 4) | cena padrão |
| `origem` | string | nome do seu app, para o log e o estado | `"api"` |

Resposta `200`, **na hora**; a escrita acontece em seguida, em segundo plano:

```json
{"ok": true, "seq": 12, "cena": "museu", "modo": "palavra", "quadros": 31, "segundos_previstos": 6.4, "segundos": 180}
```

| Campo | Significado |
|---|---|
| `seq` | número desta fala. É com ele que você sabe, no estado, se ela terminou |
| `modo` | `caractere`, `palavra` ou `linha`: o que aparece de uma vez, pela cena |
| `quadros` | quantas vezes a tela vai mudar até a fala estar inteira |
| `segundos_previstos` | quanto a escrita leva no ritmo da cena, se a serial acompanhar |
| `segundos` | sem fala nova por esse tempo, o rodízio volta |

O que acontece:

1. **Chegou a fala:** o rodízio pausa, uma frase de `/texto` ou um diálogo anterior em andamento é
   cancelado (a mais recente é a que vale), o brilho da cena é aplicado.
2. **A fala aparece** no modo da cena, a até `dialogo_cps` caracteres por segundo. O ritmo é um teto:
   cada passo tem hora marcada, e se a serial atrasa o laço só deixa de dormir. Com `bitmap_parcial`
   desligado cada quadro custa ~1,1 s, então `caractere` vira na prática um quadro por segundo;
   `palavra` e `linha` cabem no fio de qualquer jeito.
3. **O destaque** entra depois da fala inteira, embaixo dela, centralizado, no mesmo ritmo. O lugar dele
   é reservado desde o início, então a fala não se desloca quando ele chega.
4. **Fala longa** rola como um terminal: a janela termina na linha que está sendo escrita.
5. **Terminou:** `GET /api/v1/estado` passa a trazer `"dialogo": {"seq": 12, "terminou": true, "fase": "fim"}`,
   e o mesmo objeto vai no `status` do WebSocket. Espere isso antes de mandar a próxima fala; se `seq`
   no estado já for maior que o seu, a sua foi atropelada por outra e não vai terminar. `fase` passa de
   `fala` a `destaque` no instante em que o destaque começa a aparecer: serve para outra tela do seu app
   mostrar a mesma frase no mesmo momento.
6. **Depois de `segundos`** sem fala nova, o rodízio da cena volta. Enquanto a fala está sendo escrita
   o guarda-tela não a interrompe.

O bloco inteiro anda 1 a 2 pontos a cada fala (o mesmo deslocamento do rodízio), para o texto da obra
não marcar sempre o mesmo lugar do fósforo.

**Python**

```python
import requests, time

VFD = "http://127.0.0.1:8765"

def dizer(fala, destaque="", teto=60):
    r = requests.post(f"{VFD}/api/v1/dialogo", json={"fala": fala, "destaque": destaque, "origem": "aparatus"},
                      timeout=5).json()
    if not r.get("ok"):
        return r                                  # 400 ou 503: registre e siga
    seq, fim = r["seq"], time.time() + teto
    while time.time() < fim:                      # espera a tela terminar, com teto
        d = requests.get(f"{VFD}/api/v1/estado", timeout=5).json()["dialogo"]
        if d["seq"] > seq or (d["seq"] == seq and d["terminou"]):
            break
        time.sleep(0.5)
    return r

dizer("A dúvida não é o contrário da certeza.", destaque="O que resta é o espelho")
```

### `GET /api/v1/estado` — como está a tela

```json
{"ok": true, "conectado": true, "porta": "/dev/cu.usbserial-A1AEZRMT", "exibindo": "rodizio",
 "cena_padrao": "museu", "cenas": ["museu"], "ultima": {"texto": "…", "hora": "14:32:10", "origem": "aparatus"},
 "tela": {"largura": 256, "altura": 128}}
```

`dialogo`: `{"seq": N, "terminou": bool, "fase": "fala" | "destaque" | "fim"}` da última fala de `/dialogo`.
`exibindo`: `boas-vindas`, `rodizio`, `api` (sua frase), `dialogo` (a fala da obra), `quadro` (seu bitmap), `manual`, `teste` ou
`nada` (apagada). `simulado` diz se é a tela simulada (seção 2). `bitmap_parcial` diz se o envio por
região está ligado (seção 3b).

### `POST /api/v1/quadro` — mostrar um bitmap pronto

Para o app que desenha a própria tela (fonte bitmap, datilografia, layout próprio). Corpo JSON:

| Campo | Tipo | O que faz | Se omitir |
|---|---|---|---|
| `png` | string | PNG **256×128** em base64 (prefixo `data:image/png;base64,` aceito). Qualquer modo; branco (>127) = ponto aceso. Até 2 MB | obrigatório |
| `origem` | string | nome do seu app, para o log e o estado | `"api"` |
| `cena` | string | de onde vêm o brilho e o tempo de volta, se não vierem abaixo | cena padrão |
| `segundos` | inteiro 3–3600 | sem quadro novo por esse tempo, o rodízio da cena volta | `api_segundos` da cena |
| `brilho` | inteiro 1–8 | brilho do visor enquanto os seus quadros estão na tela | o da cena |

Comportamento:

1. **O primeiro quadro pausa o rodízio** e cancela uma frase de texto em andamento. O brilho da cena
   (ou o do campo) é aplicado uma vez; quadros seguintes só mandam o bitmap.
2. **A resposta volta depois que o quadro saiu pela serial.** Assim o seu app sente a cadência real do
   vidro sem WebSocket: ~1,1 s para a tela inteira, bem menos com envio parcial (abaixo).
3. **Fila de tamanho 1, o mais recente vale.** Se chegam quadros mais rápido do que a serial escoa, os
   que ainda não começaram a sair são descartados. Mande à vontade (uma thread própria, sem travar o seu
   diálogo); o VFD Studio dita o ritmo. Quadro descartado responde `200` com `"exibido": false`.
4. **Envio parcial** (`bitmap_parcial` no `config.json`, ligado por quem opera o VFD Studio depois de
   validar no vidro): o VFD Studio compara o quadro com o anterior e manda só o retângulo que mudou
   (`1F 28 66 11` com largura e altura menores, a partir do cursor). Um caractere a mais na linha
   corrente leva ~20 ms; uma linha de 16 pontos inteira, ~0,15 s; rolagem da tela toda, ~1,1 s.
   Quadro igual ao anterior não manda nada. Desligado, todo quadro sai inteiro (~1,1 s). O seu app
   não precisa saber qual dos dois está valendo: mande sempre o quadro inteiro e leia `bytes` e `ms`
   na resposta.
5. **Passado `segundos` sem quadro novo**, o rodízio da cena volta (verificado a cada 3 s). O guarda-tela
   (`guarda_tela_segundos`, 120 s por padrão) também vale: quadro parado além disso volta ao rodízio.
   Para "segurar a última fala até a próxima", basta que a próxima chegue antes desses prazos.
6. **Uma frase de texto (`/api/v1/texto`) que chegar no meio** entra por cima; o quadro seguinte
   retoma. Vale sempre o que chegou por último, de qualquer caminho.

Resposta `200`:

| Campo | Significado |
|---|---|
| `exibido` | `true` saiu pela serial; `false` descartado por um quadro mais novo (`motivo` explica) |
| `seq` | número do quadro, crescente desde que o VFD Studio abriu |
| `bytes` | bytes enviados à tela (4111 = tela inteira; menos = envio parcial; 0 = quadro igual ao anterior) |
| `ms` | quanto tempo o envio levou |
| `segundos` | prazo de volta do rodízio a partir deste quadro |
| `cena` | cena usada para brilho e prazo |

Erros: `400` PNG inválido ou tamanho diferente de 256×128; `503` tela desconectada (seção 6).

```python
import base64, io, requests
from PIL import Image

def mostrar_quadro(img: Image.Image, segundos=180):
    buf = io.BytesIO(); img.convert("1").save(buf, "PNG")
    corpo = {"png": base64.b64encode(buf.getvalue()).decode(), "origem": "aparatus", "segundos": segundos}
    r = requests.post("http://127.0.0.1:8765/api/v1/quadro", json=corpo, timeout=10)
    return r.json()      # {"ok": true, "exibido": true, "seq": 12, "bytes": 4111, "ms": 1080, ...}
```

### `POST /api/v1/limpar` — apagar a tela

Para tudo (rodízio e frase) e apaga. Use com moderação: tela apagada é o estado "sem conteúdo".

### `POST /api/v1/rodizio` — voltar ao rodízio agora

Não espera o tempo da frase acabar.

---

## 4. O que a cena decide (e você não precisa)

Uma **cena** é um conjunto salvo no VFD Studio: espessura e tamanho da letra, espelhamento (para a
lente), **brilho do visor**, o rodízio de frases que fica quando ninguém manda nada, e como as frases
da API aparecem (modo, velocidade, tempo). Quem cria e ajusta cenas é quem opera o VFD Studio, pela página.

Você só precisa do **nome**. Mandar `"cena": "noite"` troca tudo isso de uma vez, inclusive o brilho.
Se não mandar, vale a cena padrão. A lista está em `GET /api/v1/estado` → `cenas`.

---

## 5. O que acontece na tela, em detalhe

1. **Chegou a frase:** o rodízio pausa. O brilho da cena é aplicado.
2. **Modo `palavra`:** as palavras aparecem uma a uma. Cada quadro leva ~1 s (é o limite da serial a
   38400 bps), então 8 palavras levam ~8 s para completar. **As letras não se mexem** enquanto aparecem:
   a posição final de cada linha é calculada antes. É o modo que "parece que está escrevendo".
3. **Modo `inteira`:** a frase aparece de uma vez, ~1 s depois da chamada.
4. **Texto longo** vira páginas, com letra nunca menor que 18 pontos. Cada página fica
   ~0,4 s por palavra (mínimo 3 s) e passa sozinha. Lida atrás de uma lente, até **~40 palavras**
   é confortável; acima disso, o leitor já não acompanha.
5. **Depois de `segundos`,** o rodízio da cena volta sozinho. A tela nunca fica vazia por falta de quem
   mande.
6. **Frase nova cancela a anterior,** mesmo no meio da escrita. A mais recente é a que vale. Se o seu app
   mandar duas frases em 5 s, a primeira some antes de alguém ler.

**Ritmo sugerido:** uma frase a cada 1 a 3 minutos. Se quiser que o leitor termine de ler, mande
`segundos` compatível com o tamanho (regra prática: 3 s + 0,5 s por palavra, mínimo 20 s).

---

## 6. Erros e o que fazer

| Código | Quando | O que o seu app deve fazer |
|---|---|---|
| `400` | texto vazio, longo demais, cena inexistente, campo inválido | corrigir; a mensagem em `erro` diz o quê |
| `503` | tela desconectada (USB fora, fonte desligada, app acabou de abrir) | **tentar de novo em 10–30 s**. O VFD Studio reconecta sozinho a cada 3 s; não precisa avisar ninguém |
| conexão recusada | VFD Studio não está aberto | esperar e tentar de novo; na instalação ele reabre sozinho |

Boa prática: trate `503` e conexão recusada como "tela indisponível agora", sem travar o seu app, e
registre no seu log. Ao ligar o Mac, o VFD Studio leva uns 5 s para conectar na tela.

Para `POST /api/v1/quadro`, use `timeout` de 10 s no cliente: a resposta espera o quadro sair pela
serial, e o VFD Studio desiste sozinho depois de 10 s (`MSG_TIMEOUT`, código `400`).

---

## 7. Exemplos completos

**Python**

```python
import requests

VFD = "http://127.0.0.1:8765"

def mostrar(frase, cena=None, segundos=None):
    corpo = {"texto": frase, "origem": "aparatus"}
    if cena: corpo["cena"] = cena
    if segundos: corpo["segundos"] = segundos
    try:
        r = requests.post(f"{VFD}/api/v1/texto", json=corpo, timeout=5)
        dados = r.json()
        if not dados.get("ok"):
            print("tela recusou:", dados.get("erro"))     # 400 ou 503
        return dados
    except requests.ConnectionError:
        print("VFD Studio não está aberto")              # tente de novo depois
        return None

mostrar("A dúvida é o começo da sabedoria.", segundos=40)
```

**JavaScript (Node 18+ ou navegador)**

```js
const VFD = "http://127.0.0.1:8765";

async function mostrar(frase, { cena, segundos } = {}) {
  const corpo = { texto: frase, origem: "aparatus", ...(cena && { cena }), ...(segundos && { segundos }) };
  try {
    const r = await fetch(`${VFD}/api/v1/texto`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo),
    });
    const dados = await r.json();
    if (!dados.ok) console.warn("tela recusou:", dados.erro);   // 400 ou 503
    return dados;
  } catch {
    console.warn("VFD Studio não está aberto");                 // tente de novo depois
    return null;
  }
}

mostrar("A dúvida é o começo da sabedoria.", { segundos: 40 });
```

**Terminal**

```bash
# frase inteira, 30 s, letra grossa
curl -s -X POST http://127.0.0.1:8765/api/v1/texto -H "Content-Type: application/json" \
  -d '{"texto": "Conhece-te a ti mesmo.", "modo": "inteira", "segundos": 30, "peso": "bold"}'

# estado da tela
curl -s http://127.0.0.1:8765/api/v1/estado
```

---

## 8. Avisos em tempo real (opcional)

`ws://127.0.0.1:8765/ws` manda JSON a cada mudança. Os que interessam ao seu app:

```json
{"tipo": "status", "conectado": true, "exibindo": "api", "ultima_api": {"texto": "…", "hora": "14:32:10"}}
{"tipo": "log", "item": {"t": "14:32:10", "nivel": "info", "msg": "API: frase exibida (1 página(s), letra 31 pt, modo palavra); rodízio volta em 90 s."}}
```

Serve para saber que a frase terminou de aparecer (`exibindo` passa a `"api"` com a sua frase em
`ultima_api`) ou que a tela caiu (`conectado: false`). Só leitura; comandos vão por HTTP.

---

## 9. Regras de convivência no Mac mini

- O VFD Studio usa a **porta 8765**. Não use essa porta no seu app.
- Rodando como `git subtree` dentro de outro repositório (ex.: `aparatus/vfd-studio/`), nada muda: o app
  acha `static/`, `assets/`, `cenas.json` e `config.json` ao lado do próprio código, e o `.venv` nasce
  dentro dessa pasta (ponha `vfd-studio/.venv/` e `vfd-studio/logs/` no `.gitignore` de fora).
  `cenas.json` e `config.json` são versionados aqui: ajustes feitos na máquina da instalação precisam
  ser commitados, ou o próximo `git subtree pull` conflita.
- Ele roda em segundo plano, sem janela; o seu app pode ficar em tela cheia por cima.
- Não é preciso iniciar nem fechar o VFD Studio: ele abre com o Mac e apaga a tela ao encerrar.
- Se quiser ver o que está acontecendo, abra `http://127.0.0.1:8765` num navegador: página, prévia da
  tela ponto a ponto e log dos últimos 200 eventos, inclusive as suas chamadas (com a `origem` que você
  mandar).

---

## 10. Recomendações e cuidados para o seu app

**Conteúdo das frases**
1. **Texto puro.** Sem markdown, asteriscos, listas, emojis ou símbolos: a fonte da tela não tem emoji
   nem alfabetos fora do latino, e eles viram quadradinhos. Acentos e cedilha funcionam.
2. **Curto.** Até ~40 palavras; o ideal é uma frase de 1 a 3 linhas.
3. **Peça isso à IA no prompt:** "responda em texto puro, em português, no máximo 30 palavras, sem
   markdown, sem emojis". É mais barato do que limpar depois.
4. **Varie as frases.** Texto fixo por horas marca a tela (foi assim que ela ficou com fantasmas).
   Variar é proteção física, não só estética.

**Ritmo**
5. Uma frase a cada 1 a 3 minutos. Rajada só cancela a anterior antes de alguém ler.
6. Para a frase ficar até a próxima, mande `segundos` alto (ex.: 180); senão o rodízio volta antes.

**Robustez**
7. **Nunca trave por causa da tela.** `503` ou conexão recusada = tentar de novo em 30 s, em segundo
   plano. O seu app não pode depender de o VFD Studio responder.
8. **Nunca trave por causa da IA.** Se a API de IA cair ou faltar internet, a tela volta ao rodízio
   sozinha; o seu app só não pode ficar numa tela de erro em cima do visitante.
9. **Abra sozinho ao ligar o Mac e volte sozinho se fechar** (item de login + relançar). Queda de luz numa
   instalação é certeza, não hipótese.
10. **Tela cheia de verdade:** sem cursor, sem barra, sem protetor de tela, sem diálogo de atualização.
11. **Log em arquivo** do que mandou e do que a API respondeu. É o primeiro lugar onde se olha quando
    algo estranha.

**Custo e segurança**
12. A API de IA é paga: limite de chamadas por hora e teto diário. Um loop travado gasta a conta numa noite.
13. Chave da IA fora do repositório e fora da tela: variável de ambiente ou arquivo ignorado pelo git.
14. Sem dado de visitante (câmera, microfone, texto do público) indo para a IA sem combinar antes.

**Convivência**
15. A porta 8765 é do VFD Studio. Nada seu pode escutar nela.
16. Mande `"origem"` com o nome do seu app em toda chamada: aparece no log e separa quem fez o quê.
17. Avise antes de mudar ritmo ou formato das frases: a cena da tela foi ajustada para um tipo de texto.

**Montagem**
18. Teste nesta ordem: botão **Testar agora** da página → seu app apontando para o Mac mini → uma noite
    inteira ligado antes de abrir ao público.

## 11. Checklist de integração

- [ ] Chamada `POST /api/v1/texto` com `texto` e `origem`, ou `POST /api/v1/quadro` com `png` e `origem`.
- [ ] Diálogo da obra: `POST /api/v1/dialogo` com `fala`/`destaque`, e espera por `dialogo.terminou` no estado, com teto.
- [ ] Quadros numa thread própria, com `timeout` de 10 s, aceitando `"exibido": false` sem reclamar.
- [ ] `503` e conexão recusada tratados como "tente depois", sem travar.
- [ ] Intervalo entre frases de pelo menos 1 minuto, ou `segundos` compatível com o tamanho.
- [ ] Frases de até ~40 palavras (ou aceitar que vire páginas).
- [ ] Nenhuma dependência da porta 8765 além desta API.
- [ ] Testado com `VFD_SIMULADO=1` (prévia da página), depois com o botão **Testar agora** e por fim no vidro.

Dúvidas e pedidos (fila em vez de cancelamento, outro comportamento ao terminar, mais eventos no
WebSocket): abra uma issue no repositório.

---

VFD Studio · desenvolvimento criativo: **Frado Monteiro** — [frado.com.br](https://frado.com.br)
