# VFD Studio

**Desenvolvedor criativo:** Frado Monteiro · [frado.com.br](https://frado.com.br)

Aplicação local para controlar a tela VFD gráfica **Noritake Itron GU256X128C-3900** (256×128 pontos)
por um conversor USB-RS232. Roda em **Windows e macOS** com o mesmo código: um servidor Python sobe só
no seu computador e abre a página em `http://127.0.0.1:8765`.

Pensada para instalações que ficam ligadas sem ninguém por perto: a tela pode ser lida atrás de uma lente.

## O que faz

- Acha o conversor sozinho (FTDI, nº de série `A1AEZRMT`), conecta e inicializa a tela.
- **Texto desenhado como imagem:** acentos aparecem, 5 espessuras de letra, tamanho automático ou manual,
  frases prontas, prévia ponto a ponto antes de enviar, envio ao digitar.
- **Exposição:** rodízio de frases, deslocamento de 1–2 pontos a cada minuto e brilho de 1 a 8,
  para a tela (que já tem desgaste) marcar menos.
- **Logo:** botão que manda a assinatura frado para a tela.
- **Teste de pontos:** todos acesos, xadrez, xadrez invertido, todos apagados.
- **Cenas** salvas em `cenas.json`: letra, tamanho, espelhar, brilho, rodízio e modo das frases da API.
- **Autonomia:** ao ligar, acha o conversor sozinho, mostra boas-vindas na tela, liga o rodízio da cena
  padrão e reconecta se o USB sair. Frases que chegam pela API interrompem o rodízio; depois ele volta.
- **API local** para outro programa escrever na tela. **Manual completo para integrar: [docs/API.md](docs/API.md).**
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

### Abrir sozinho ao ligar o Mac

Duplo clique em `mac/instalar_inicio_automatico.command`. Ele registra o VFD Studio para abrir no login
e reabrir se fechar. Depois, uma vez só, ligue o **login automático** em Ajustes do Sistema › Usuários
e Grupos, senão após uma queda de luz o Mac para na tela de senha. Para desfazer:
`mac/remover_inicio_automatico.command`.

### Energia: a tela não pode ficar acesa sem o computador

A tela VFD **segura a última imagem para sempre** se continuar alimentada depois que o computador some
(USB puxado, queda de luz com a fonte do visor em outra tomada, Mac desligado à força). Nenhum programa
consegue apagar uma tela com a qual não fala mais, e imagem parada por horas é o que mais queima o
fósforo. O app já apaga a tela ao encerrar de forma normal; o resto é montagem:

1. **Fonte do visor junto com o Mac mini.** As duas na **mesma régua** (ou na mesma tomada inteligente).
   Caiu a luz, caem os dois; desligou o Mac pela régua, a tela apaga junto. Nunca deixe a fonte do visor
   numa tomada separada.
2. **Melhor ainda: alimentar a tela pela USB do próprio Mac mini** (ou de um hub ligado nele), com um
   cabo USB → 5 V no pino 6 do CN1. Aí a tela só tem energia enquanto o Mac está ligado, sem régua.
   Confirme antes a corrente da tela: a ficha da série indica 850 mA típicos para o modelo C; uma porta
   USB-C do Mac mini fornece até 1,5 A, uma USB-A 0,9 A. Se o pico passar disso, fique na régua.
   Isso muda só a **origem** dos 5 V; os fios de dados validados continuam iguais.
3. **Mac mini: ligar sozinho quando a energia voltar.** Ajustes do Sistema › Energia › "Iniciar
   automaticamente após falta de energia" (ou, no Terminal, `sudo pmset -a autorestart 1`). Junto com o
   login automático e o `instalar_inicio_automatico.command`, a sequência depois de uma queda de luz
   fica: energia volta → Mac liga → usuário entra → VFD Studio abre → conecta → limpa a tela → rodízio.
4. **Nunca deixe o Mac dormir:** Ajustes do Sistema › Energia › "Impedir repouso automático" (ou
   `sudo pmset -a sleep 0 disksleep 0`). Mac dormindo = USB sem comando = imagem parada.
5. **Antes de puxar o USB ou desligar a fonte** para manutenção: clique em **Desconectar** na página
   (a tela é apagada antes de a porta fechar) ou feche o app.

O log do app registra a hora em que a conexão caiu e voltou. Se a tela ficou parada por muitas horas,
deixe-a apagada por um tempo equivalente antes de voltar à exposição.

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
cenas.py            cenas e configuração em arquivo (cenas.json, config.json)
docs/               PESQUISA.md, ICD_tela_VFD.md, API.md, simulação da frase
mac/                instalar/remover início automático (LaunchAgent)
iniciar.bat / iniciar.command   lançadores Windows / macOS
vfd_monitor.py, vfd_claude.py   scripts originais de bancada; o app ainda não os usa (etapas E4/E5)
```

## Ainda não feito

Envio de imagem com pontilhado e logo (E3), painel ao vivo e relógio (E4), chat com o Claude (E5,
opcional e pago à parte), testes automáticos (E6), e o rodízio de pixels guiado por mapa de desgaste
(ver docs/PESQUISA.md, seção 6).

## Executável pronto (sem instalar Python)

Para quem não quer mexer com Python, há o app empacotado, com a logo frado no ícone:

- **Windows:** baixe `VFD-Studio-2.0-windows.zip` na página de
  [Releases](https://github.com/fradomnt/vfd-studio/releases), descompacte e dê duplo clique em
  **VFD Studio.exe**. O Windows SmartScreen pode avisar na primeira vez ("Mais informações › Executar
  assim mesmo"), porque o executável não tem assinatura digital.
- **macOS:** `VFD-Studio-2.0-mac.zip` nas Releases, descompacte, botão direito no **VFD Studio.app › Abrir**
  (só na primeira vez; o app não é assinado pela Apple). Se o Finder recusar: no Terminal,
  `xattr -cr "VFD Studio.app"`.

`cenas.json` e `config.json` ficam **ao lado** do executável (ou do .app): é lá que o app grava as cenas.

### Gerar você mesmo

Cada sistema gera o seu, não dá para gerar o do Mac no Windows nem o contrário:

- Windows: duplo clique em `windows/gerar_exe.bat` → `dist\VFD Studio\VFD Studio.exe` e o zip.
- macOS: duplo clique em `mac/gerar_app.command` → `dist/VFD Studio.app` e o zip.

Os dois usam `vfd_studio.spec` (PyInstaller, listado em `requirements-dev.txt`). Para publicar nas
Releases: `gh release upload v2.0 dist/VFD-Studio-2.0-mac.zip`.

## Créditos

- **Desenvolvimento criativo:** Frado Monteiro — [frado.com.br](https://frado.com.br)
- **Integração com o app que manda as frases:** Marlus Araujo
- Fonte Roboto Condensed (SIL Open Font License). Tela Noritake Itron GU256X128C-3900.

## Hardware (fixo)

Tela GU256X128C-3900, RS-232 real no conector CN1, SW1 com as 8 chaves em OFF (38400 bps, 8N1, sem
controle de fluxo), fonte externa 5 V ≥ 2 A. Conversor PremierCable PCM-KW-469 (FTDI FT232R).
Não mude fios, SW1, baud nem o formato do bitmap.
