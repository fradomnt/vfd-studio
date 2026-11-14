# ICD — Tela VFD Noritake GU256X128C-3900 no VFD Studio

| Campo | Valor |
|---|---|
| Documento | Interface Control Document (ICD) |
| Sistema | VFD Studio · tela GU256X128C-3900 (PCB PW-1032-101) |
| Revisão | 0.1 — 12/11/2026 |
| Fontes | bancada no Mac mini (12/10/2026), laptop Windows (12/11/2026), `vfd.py` |

> **Regra deste documento:** só entra aqui o que foi medido ou validado em bancada. O que vem de
> dedução ou ainda não foi testado está marcado como **[a confirmar]**. Nada é tirado de memória
> sobre a família de telas da Noritake.

---

## 1. Visão geral

A tela recebe comandos e imagens por **RS-232 real** pelo conector CN1. O computador fala USB, então
um conversor FTDI faz a ponte. A tela tem **fonte própria de 5 V**: o USB só leva dados.

```text
 ┌──────────────┐  USB 2.0   ┌─────────────────────┐  RS-232 ±V   ┌───────────────────────┐
 │  Computador  │──────────▶│ PCM-KW-469 (FT232R)  │────────────▶│ GU256X128C-3900 · CN1  │
 │  VFD Studio  │  COM4 /    │ serial A1AEZRMT     │ 38400 8N1    │ 256×128, 1 cor         │
 │  (app.py)    │  cu.usb…   └─────────────────────┘ sem fluxo    └───────────▲───────────┘
 └──────────────┘                                                           │ +5 V ≥ 2 A
                                                                    ┌───────┴───────┐
                                                                    │ Fonte externa │
                                                                    └───────────────┘
```

Fluxo de dados: **uma via só, PC → tela.** O app não lê nada que a tela devolva.

---

## 2. Lista de interfaces

| ID | Interface | Entre | Tipo | Estado |
|---|---|---|---|---|
| IF-1 | USB | computador ↔ conversor | USB full speed, VID `0403`, PID `6001` | validado nos dois computadores |
| IF-2 | Serial RS-232 | conversor → tela CN1 | 38400 bps, 8N1, sem controle de fluxo | validado nos dois computadores |
| IF-3 | Alimentação | fonte → tela CN1 pino 6 | 5 V, ≥ 2 A | validado |
| IF-4 | Configuração | DIP SW1 da tela | 8 chaves em OFF | validado (não mexer) |
| IF-5 | Protocolo | software → tela | comandos e bitmap, seção 5 | parcialmente validado |

---

## 3. Conector CN1 (tela)

| Pino CN1 | Sinal | Sentido | Fio | Liga em |
|---|---|---|---|---|
| 1 | RXD (entrada da tela) | entrada | preto | TXD do conversor |
| 2 | — | — | — | isolado |
| 3 | — | — | — | isolado |
| 4 | TXD (saída da tela) | saída | amarelo | RXD do conversor |
| 5 | — | — | — | isolado |
| 6 | +5 V | entrada | verde | fonte externa 5 V ≥ 2 A |
| **[a confirmar]** | GND | comum | azul | GND do conversor e da fonte |

**Cuidados**
- O +5 V entra no **mesmo conector** dos sinais RS-232. Se o cabo for refeito, confira o fio verde
  com multímetro antes de ligar a fonte.
- O GND precisa ser **comum** entre fonte, tela e conversor. Sem ele, a serial não funciona.
- Use só o lado RS-232 do conversor. O bloco TTL **não** deve ser usado.
- **Lacuna:** o número do pino de GND no CN1 não está anotado. Vale registrar na próxima vez que o
  cabo estiver aberto.

---

## 4. Conversor USB-RS232

| Item | Valor |
|---|---|
| Modelo | PremierCable PCM-KW-469 |
| Chip | FTDI FT232R (VID `0403`, PID `6001`) |
| Nº de série USB | `A1AEZRMT` |
| Windows | `COM4` neste laptop, "USB Serial Port (COM4)". O driver mostra o serial como `A1AEZRMTA` (com um "A" a mais, que indica a porta A do chip) |
| macOS | `/dev/cu.usbserial-A1AEZRMT` — usar sempre `cu.*`, nunca `tty.*` |
| Detecção no app | `vfd.achar_porta()`: 1º variável `VFD_PORTA`; 2º nº de série contém `A1AEZRMT`; 3º qualquer FTDI |

Tirar e recolocar o USB **manteve a COM4** neste laptop (12/11/2026). Mesmo que o número da COM mude,
o app encontra a porta pelo número de série.

---

## 5. Protocolo (IF-5)

### 5.1 Comandos validados

| Função | Bytes (hex) | Espera depois | Observação |
|---|---|---|---|
| Inicializar | `1B 40` | 300 ms | apaga a tela e volta ao padrão |
| Limpar | `0C` | 50 ms | |
| Nova linha | `0D 0A` | — | |
| Brilho | `1F 58 n` | 20–50 ms | ver 5.3 |
| Cursor | `1F 24 xL xH yL yH` | — | x em pontos 0–255; y em linhas de 8 pontos 0–15 |
| Display aceso | `1F 28 61 40 01` | 20 ms | não apaga o conteúdo |
| Display apagado | `1F 28 61 40 00` | 20 ms | não apaga o conteúdo |
| Tamanho da letra | `1F 28 67 01 m` | — | m = 1, 2 ou 4 (5.4) |
| Rolagem vertical | `1F 02` | — | quando a tela enche, o texto sobe |
| Escrever por cima | `1F 01` | — | padrão |
| Bitmap tela inteira | `1F 28 66 11` + `00 01` + `10 00` + `01` + 4096 B | — | ver 5.2 |

### 5.2 Formato do bitmap (fixo — não mudar)

Cabeçalho depois de `1F 28 66 11`:

| Bytes | Significado |
|---|---|
| `00 01` | largura = 256 pontos (xL, xH) |
| `10 00` | altura = 16 bytes = 128 pontos (yL, yH) |
| `01` | valor fixo usado e validado |

Dados (4096 bytes):
- 256 colunas, **da esquerda para a direita**;
- 16 bytes por coluna, **de cima para baixo**;
- **bit 7 = ponto de cima** do grupo de 8; `1` = aceso.

Pontos para os testes automáticos:

| Ponto (x, y) | Índice do byte | Valor |
|---|---|---|
| (0, 0) | 0 | `0x80` |
| (5, 127) | 5 × 16 + 15 = 95 | `0x01` |
| (255, 127) | 255 × 16 + 15 = 4095 | `0x01` |

O pacote completo enviado por `VFD.bitmap()` tem **4111 bytes**: 6 do cursor (0,0), mais 9 de
comando e cabeçalho, mais 4096 de dados.

### 5.3 Brilho — ponto a esclarecer

- O prompt diz `n = 0x10..0x18` e "8 níveis". De `0x10` a `0x18` são **9 valores**.
- O `vfd.py` envia `0x10 + n` com n entre 1 e 8, ou seja, **`0x11..0x18`**: são 8 níveis, e `0x18` = 100 %.
- **Decisão para o app:** o controle vai de 1 a 8 (`0x11..0x18`). O valor **`0x10` nunca é enviado**
  **[a confirmar]**: ele pode ser "0 %", que deixaria a tela escura sem estar desligada, e isso confunde.

### 5.4 Letras e grade de texto

| m | Letra | Colunas × linhas | Origem |
|---|---|---|---|
| 1 | 6×8 | 42 × 16 | validado |
| 2 | 8×16 | 32 × 8 | conta 256/8 e 128/16 **[a confirmar]** |
| 4 | 16×32 | 16 × 4 | conta 256/16 e 128/32 **[a confirmar]** |

Na 6×8: 42 × 6 = 252 pontos, então sobram 4 pontos à direita.
Texto: só ASCII de 0x20 a 0x7E. Os acentos são removidos (`ç`→`c`, `ã`→`a`) por `VFD.ascii()`.

### 5.5 No código, mas fora do protocolo validado

| Função | Bytes | Estado |
|---|---|---|
| Cursor apagado / visível | `1F 43 00` / `1F 43 01` | enviado pelo `iniciar()`, sem efeito visível confirmado **[a confirmar]** |
| Texto invertido | `1F 72 00/01` | nunca testado **[a confirmar]** |

### 5.6 Proibido

**Nunca enviar** `1C 7C 4D D0 4D 4F 44 45 49 4E`: essa sequência põe a tela em modo de regravação de memória.
Sugestão para a E6: o driver recusar qualquer envio que contenha essa sequência.

---

## 6. Tempos e vazão

A 38400 bps com 8N1, cada byte usa 10 bits, ou seja, **260 µs por byte** (3840 B/s).

| Envio | Bytes | Tempo no fio | Blocos de 128 B | Pausas de 20 ms | **Total estimado** |
|---|---|---|---|---|---|
| Comando curto | 1–6 | < 2 ms | 1 | 0 | ~ espera do comando |
| Texto de 42 × 16 | ~700 | ~0,18 s | 6 | 0,12 s | **~0,3 s** |
| Tela inteira (bitmap) | 4111 | 1,07 s | 33 | 0,66 s | **1,07 s medido** |

**Medição real (laptop Windows, 12/11/2026, preset "Devaneios"):** 4111 B em **1074 ms**.
- Eu tinha estimado ~1,7 s somando as pausas ao tempo no fio. Estava errado: no Windows, o driver
  FTDI guarda os dados num buffer, as pausas de 20 ms correm **ao mesmo tempo** que a transmissão
  e o total fica igual ao tempo no fio. O "~1,1 s" do prompt está certo.
- Para o **painel ao vivo (E4)**, atualizar a cada 2 s deixa ~0,9 s livres. **2 s funciona.**
- Consequência: as pausas não seguram o ritmo, e os dados chegam à tela em fluxo contínuo. Se a
  imagem sair embaralhada no Windows, e só no Windows, a causa provável é essa.
- Não reduzir a pausa de 20 ms sem medir: o buffer de recepção da tela é de 256 B e o bloco de
  128 B é metade dele.

---

## 7. Como o app usa a interface

| Regra | Onde |
|---|---|
| Um único dono da porta (um `VFD` aberto por vez, com `threading.Lock`) | `app.py` → `Estado` / `com_tela()` |
| Conectar **abre a porta sem enviar nada**. Inicializar manda `1B 40` | `/api/conectar`, `/api/iniciar` |
| Envio numa thread separada, com timeout de 10 s, e `write_timeout` de 2 s no pyserial | `na_serial()`, `vfd.VFD` |
| A cada 2 s, confere se a porta sumiu (USB desplugado) e volta para desconectado | `vigia()` |
| A prévia mostra os mesmos 4096 bytes da seção 5.2, ampliados 3× | `static/app.js` → `desenharPrevia()` |

---

## 8. Situação da validação

| Item | Mac mini 12/10/2026 | Laptop Win 12/11/2026 |
|---|---|---|
| Porta detectada pelo nº de série | ✓ | ✓ COM4 |
| Texto (`vfd.py texto`) | ✓ | ✓ "Ola" |
| Bitmap e logo | ✓ | pendente (E3; falta copiar o `logo_vfd.bin`) |
| Inicializar pelo app (E1) | — | **pendente: teste do usuário** |
| Brilho, display, letras pelo app (E2) | — | pendente |
| Tempo real de uma tela inteira | — | ✓ 1074 ms |
| Bitmap pelo app (preset Devaneios) | — | enviado; **imagem a confirmar pelo usuário** |

## 9. Pendências

1. Número do pino de GND no CN1.
2. O que `1F 58 10` faz (brilho 0 % ou inválido).
3. Se `1F 43` e `1F 72` têm efeito (seção 5.5).
4. Grade de 32 × 8 e 16 × 4 nas letras grandes.
5. ~~Tempo real do bitmap~~: medido, 1074 ms (seção 6).
6. Se a tela manda algo pelo pino 4 (TXD). Hoje o app não lê nada.
