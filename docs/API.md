# Manual da API do VFD Studio — para integrar o app de filosofias

Este manual é para quem vai escrever na tela VFD da escultura *Devaneios do Aparato* a partir de
outro programa. A ideia é simples: **o seu app manda o texto; o VFD Studio cuida de tudo o mais**
(letra, acentos, tamanho, brilho, páginas, desgaste da tela, e o que mostrar quando você não manda nada).

Não é preciso saber nada da tela, da porta serial ou do protocolo Noritake.

---

## 1. Em 60 segundos

O VFD Studio precisa estar aberto **no mesmo computador** (no museu, ele abre sozinho ao ligar o Mac
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

## 2. Como testar sem a escultura

1. Clone o repositório e abra o VFD Studio (`iniciar.command` no Mac, `iniciar.bat` no Windows, ou o
   executável das [Releases](https://github.com/fradomnt/vfd-studio/releases)).
2. Sem a tela ligada, a página em `http://127.0.0.1:8765` mostra "desconectado" e a API responde
   `503` (seção 6). **Para desenvolver sem a tela**, use a prévia da página: cole o texto no cartão
   *Texto* e veja como ficaria em 256×128 pontos. É exatamente o que a API desenha.
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

### `GET /api/v1/estado` — como está a tela

```json
{"ok": true, "conectado": true, "porta": "/dev/cu.usbserial-A1AEZRMT", "exibindo": "rodizio",
 "cena_padrao": "museu", "cenas": ["museu"], "ultima": {"texto": "…", "hora": "14:32:10", "origem": "filosofias"},
 "tela": {"largura": 256, "altura": 128}}
```

`exibindo`: `boas-vindas`, `rodizio`, `api` (sua frase), `manual`, `teste` ou `nada` (apagada).

### `POST /api/v1/limpar` — apagar a tela

Para tudo (rodízio e frase) e apaga. Use com moderação: tela apagada é o estado "sem conteúdo".

### `POST /api/v1/rodizio` — voltar ao rodízio agora

Não espera o tempo da frase acabar.

---

## 4. O que a cena decide (e você não precisa)

Uma **cena** é um conjunto salvo no VFD Studio: espessura e tamanho da letra, espelhamento (para a
lente), **brilho do visor**, o rodízio de frases que fica quando ninguém manda nada, e como as frases
da API aparecem (modo, velocidade, tempo). Quem cria e ajusta cenas é a equipe da escultura, pela página.

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
   ~0,4 s por palavra (mínimo 3 s) e passa sozinha. Para a lente da escultura, até **~40 palavras**
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
| conexão recusada | VFD Studio não está aberto | esperar e tentar de novo; no museu ele reabre sozinho |

Boa prática: trate `503` e conexão recusada como "tela indisponível agora", sem travar o seu app, e
registre no seu log. Ao ligar o Mac, o VFD Studio leva uns 5 s para conectar na tela.

---

## 7. Exemplos completos

**Python**

```python
import requests

VFD = "http://127.0.0.1:8765"

def mostrar(frase, cena=None, segundos=None):
    corpo = {"texto": frase, "origem": "filosofias"}
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
  const corpo = { texto: frase, origem: "filosofias", ...(cena && { cena }), ...(segundos && { segundos }) };
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
- Ele roda em segundo plano, sem janela; o seu app pode ficar em tela cheia por cima.
- Não é preciso iniciar nem fechar o VFD Studio: ele abre com o Mac e apaga a tela ao encerrar.
- Se quiser ver o que está acontecendo, abra `http://127.0.0.1:8765` num navegador: página, prévia da
  tela ponto a ponto e log dos últimos 200 eventos, inclusive as suas chamadas (com a `origem` que você
  mandar).

---

## 10. Checklist de integração

- [ ] Chamada `POST /api/v1/texto` com `texto` e `origem`.
- [ ] `503` e conexão recusada tratados como "tente depois", sem travar.
- [ ] Intervalo entre frases de pelo menos 1 minuto, ou `segundos` compatível com o tamanho.
- [ ] Frases de até ~40 palavras (ou aceitar que vire páginas).
- [ ] Nenhuma dependência da porta 8765 além desta API.
- [ ] Testado com o botão **Testar agora** da página e depois com o seu app.

Dúvidas e pedidos (fila em vez de cancelamento, outro comportamento ao terminar, mais eventos no
WebSocket): abra uma issue no repositório ou fale com a equipe da escultura.
