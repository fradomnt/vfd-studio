# VFD Studio

Aplicação local para controlar a tela VFD gráfica **Noritake Itron GU256X128C-3900** (256×128 pontos)
por um conversor USB-RS232. Roda em **Windows e macOS** com o mesmo código: um servidor Python sobe só
no seu computador e abre a página em `http://127.0.0.1:8765`.

Feita para a escultura *Devaneios do Aparato*: a tela fica dentro da peça, atrás de uma lente Fresnel.

## O que faz

- Acha o conversor sozinho (FTDI, nº de série `A1AEZRMT`), conecta e inicializa a tela.
- **Texto desenhado como imagem:** acentos aparecem, 5 espessuras de letra, tamanho automático ou manual,
  frases prontas, prévia ponto a ponto antes de enviar, envio ao digitar.
- **Exposição:** rodízio de frases, deslocamento de 1–2 pontos a cada minuto e brilho de 1 a 8,
  para a tela (que já tem desgaste) marcar menos.
- **Logo:** botão que manda a assinatura frado para a tela.
- **Teste de pontos:** todos acesos, xadrez, xadrez invertido, todos apagados.
- Log dos envios ao vivo.

Pesquisa, decisões e próximos passos estão em [docs/PESQUISA.md](docs/PESQUISA.md).
Ligação elétrica e protocolo estão em [docs/ICD_tela_VFD.md](docs/ICD_tela_VFD.md).

## Instalar e rodar

### Windows

1. Instale o Python 3 em https://www.python.org/downloads/ marcando **"Add python.exe to PATH"**.
2. Plugue o conversor USB. O Windows instala o driver FTDI sozinho; a porta aparece como
   "USB Serial Port (COMx)" no Gerenciador de Dispositivos.
3. Dê duplo clique em **`iniciar.bat`**. Na primeira vez ele cria a pasta `.venv` e instala as
   dependências (precisa de internet); depois é instantâneo.
4. Fica aberta uma janela preta (o servidor) e o navegador abre a página. **Não feche a janela preta.**

### macOS (Mac mini atual, Apple Silicon, ou Intel)

1. Instale o Python 3 pelo instalador oficial em https://www.python.org/downloads/macos/
   (o `python3` que já vem no Mac é só um atalho das ferramentas da Apple; o lançador não depende dele).
2. Plugue o conversor USB. **Não precisa instalar driver:** o macOS já reconhece o chip FTDI FT232R e
   cria `/dev/cu.usbserial-A1AEZRMT`. Para conferir, no Terminal: `ls /dev/cu.usb*`.
   - No macOS Sequoia e mais novos, se a porta não aparecer, vá em **Ajustes do Sistema › Geral ›
     Itens de Início e Extensões** e permita a extensão de driver, depois replugue o USB.
   - Se algum dia foi instalado o driver VCP da FTDI, desative-o: ele briga com o da Apple.
3. Dê duplo clique em **`iniciar.command`**.
   - Se o Finder disser que o arquivo "não pode ser aberto": clique com o botão direito › **Abrir**.
     Isso acontece quando a pasta veio num ZIP baixado. Pelo `git clone` não acontece.
   - Se nada acontecer ao clicar, no Terminal: `chmod +x iniciar.command` e tente de novo.
4. Abre uma janela do Terminal (o servidor) e o navegador abre a página. **Não feche o Terminal.**

### Pela linha de comando (qualquer sistema)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Usar

1. **Conectar.** A porta do conversor já vem escolhida (marcada com ✓). Conectar só abre a porta.
2. **Inicializar tela** apaga a tela e põe o brilho em 100 %. Faça isso uma vez depois de ligar a fonte.
3. Escreva no cartão **Texto** e veja a prévia; **Enviar para a tela** (ou Ctrl+Enter) manda de verdade.
4. Para a peça ficar ligada: monte o rodízio no cartão **Exposição**, baixe o brilho e **Iniciar exposição**.

A fonte de 5 V da tela precisa estar ligada antes de enviar qualquer coisa. O app não controla a fonte.

## Se der problema

| Mensagem ou sintoma | O que fazer |
|---|---|
| **Porta ocupada** | Outro programa está com o conversor (Arduino IDE, PuTTY, monitor serial, outra janela do VFD Studio). Feche-o e clique em Conectar. |
| **Porta não encontrada** | O USB saiu. Replugue e clique em Atualizar. No Mac, confira `ls /dev/cu.usb*`. |
| Página diz **servidor parado** | A janela preta/Terminal foi fechada. Abra o `iniciar.bat` ou `iniciar.command` de novo. |
| Nada aparece na tela, sem erro | Fonte de 5 V desligada, ou a tela foi ligada depois do envio. Ligue a fonte e clique em Inicializar tela. |
| Imagem embaralhada | Procure no software, não nos fios: o formato do bitmap está em `vfd.py` (`_codificar`). |
| Com tudo aceso aparecem "fantasmas" de textos antigos | Desgaste do fósforo da tela, não é defeito do app. Veja docs/PESQUISA.md. |

Para forçar uma porta: variável de ambiente `VFD_PORTA` (ex.: `COM5` ou `/dev/cu.usbserial-A1AEZRMT`).

## Estrutura

```
app.py              servidor FastAPI: rotas, serial (único dono da porta), WebSocket, exposição
vfd.py              driver da tela (pyserial): comandos, texto, bitmap, detecção da porta
presets.py          texto desenhado como imagem (Roboto Condensed), frases prontas, padrões de teste
static/             index.html, app.js, style.css — a página, sem framework
assets/fonts/       Roboto Condensed (licença SIL OFL)
assets/logo_vfd.bin logo já no formato da tela (copiar do Mac mini; ainda não está no repositório)
docs/               PESQUISA.md, ICD_tela_VFD.md, simulação da frase
iniciar.bat / iniciar.command   lançadores Windows / macOS
vfd_monitor.py, vfd_claude.py   scripts originais de bancada; o app ainda não os usa (etapas E4/E5)
```

## Ainda não feito

Envio de imagem com pontilhado e logo (E3), painel ao vivo e relógio (E4), chat com o Claude (E5,
opcional e pago à parte), testes automáticos (E6), e o rodízio de pixels guiado por mapa de desgaste
(ver docs/PESQUISA.md, seção 6).

## Executável opcional (não gerado)

Quando tudo estiver estável, dá para empacotar com PyInstaller, em cada sistema separadamente:

```bash
pip install pyinstaller
pyinstaller --onefile --add-data "static:static" --add-data "assets:assets" app.py
```

No Windows use `;` em vez de `:` nos `--add-data`. Antivírus às vezes bloqueiam executáveis assim;
os lançadores `.bat`/`.command` continuam sendo o caminho mais simples.

## Hardware (fixo)

Tela GU256X128C-3900, RS-232 real no conector CN1, SW1 com as 8 chaves em OFF (38400 bps, 8N1, sem
controle de fluxo), fonte externa 5 V ≥ 2 A. Conversor PremierCable PCM-KW-469 (FTDI FT232R).
Não mude fios, SW1, baud nem o formato do bitmap.
