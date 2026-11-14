# API do VFD Studio (v1)

Para outro programa (por exemplo, o app de filosofias do Marlus) escrever na tela VFD.
O VFD Studio cuida da **forma**: letra, tamanho, acentos, páginas, brilho, desgaste da tela.
Quem chama a API cuida só do **conteúdo**.

## Onde

O VFD Studio precisa estar aberto no **mesmo computador** (hoje ele só aceita conexões locais).

```
http://127.0.0.1:8765
```

Sem chave, sem login. Respostas em JSON, sempre com `"ok": true` ou `"ok": false` + `"erro"`.

## Mandar uma frase

`POST /api/v1/texto`

```json
{ "texto": "A realidade é apenas uma sombra da verdade." }
```

Só `texto` é obrigatório. O resto vem da **cena padrão** configurada no VFD Studio. Campos opcionais:

| Campo | O que faz | Padrão |
|---|---|---|
| `cena` | nome de uma cena salva no VFD Studio | a cena padrão |
| `modo` | `"palavra"` (vai escrevendo, ~1 palavra/s) ou `"inteira"` | o da cena |
| `segundos` | quanto tempo a frase fica depois de pronta, antes de o rodízio voltar | o da cena (90) |
| `peso` | `light`, `regular`, `medium`, `bold`, `black` | o da cena |
| `tamanho` | tamanho da letra em pontos; `0` = o maior que couber | o da cena |
| `origem` | nome do seu app, só para o log | `"api"` |

Resposta (imediata; a escrita acontece em seguida):

```json
{ "ok": true, "cena": "museu", "modo": "palavra", "paginas": 1, "letra": 31, "palavras": 8, "segundos": 90 }
```

### O que acontece na tela

1. O rodízio de frases da cena é interrompido.
2. A frase aparece. No modo `palavra`, cada quadro leva ~1 s (limite físico da serial a 38400 bps),
   então uma frase de 8 palavras leva ~8 s para terminar de escrever. As letras **não se mexem**
   enquanto aparecem: a posição final é calculada antes.
3. Texto longo vira **páginas** (letra mínima de 18 pt). Cada página fica ~0,4 s por palavra, mínimo 3 s.
4. Depois de `segundos`, o rodízio da cena volta sozinho. A tela nunca fica vazia.
5. Uma frase nova **cancela** a anterior, mesmo no meio da escrita. A mais recente é a que vale.

Limites: 2000 caracteres por frase. Acentos funcionam (ç, ã, é…). Quebra de linha (`\n`) é respeitada
e desliga a paginação automática. Para a lente, uma tela confortável tem até ~40 palavras.

## Outras chamadas

| Chamada | Para quê |
|---|---|
| `GET /api/v1/estado` | tela conectada?, o que está exibindo (`boas-vindas`, `rodizio`, `api`, `manual`, `nada`), cena padrão, cenas disponíveis, última frase recebida |
| `POST /api/v1/limpar` | apaga a tela e para tudo (rodízio e frase) |
| `POST /api/v1/rodizio` | volta ao rodízio da cena padrão agora |

Erros: `400` para pedido inválido, `503` quando a tela não está conectada (o VFD Studio tenta
reconectar sozinho a cada 3 s; basta tentar de novo).

## Exemplos

**curl**

```bash
curl -s -X POST http://127.0.0.1:8765/api/v1/texto \
  -H "Content-Type: application/json" \
  -d '{"texto": "A dúvida é o começo da sabedoria.", "origem": "filosofias"}'
```

**Python**

```python
import requests
r = requests.post("http://127.0.0.1:8765/api/v1/texto",
                  json={"texto": "A dúvida é o começo da sabedoria.", "origem": "filosofias"}, timeout=5)
print(r.json())
```

**JavaScript (Node ou navegador)**

```js
const r = await fetch("http://127.0.0.1:8765/api/v1/texto", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ texto: "A dúvida é o começo da sabedoria.", origem: "filosofias" }),
});
console.log(await r.json());
```

**Ritmo sugerido:** uma frase a cada 1–3 minutos. Mandar mais rápido que isso só cancela a anterior
antes de alguém ler. Se o seu app ficar em silêncio, o rodízio da cena segura a tela.

## Avisos em tempo real (opcional)

`ws://127.0.0.1:8765/ws` manda JSON com `tipo` = `status`, `previa` ou `log` a cada mudança.
Serve para o seu app saber que a frase já foi exibida (`exibindo: "api"`) ou que a tela caiu.
