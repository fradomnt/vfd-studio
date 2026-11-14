# Pesquisa — tela VFD da escultura "Devaneios do Aparato"

Registro de 12/11/2026. Reúne o que foi testado, pesquisado e decidido, para retomar depois.
Documentos irmãos: [ICD_tela_VFD.md](ICD_tela_VFD.md) (ligação e protocolo) e
[simulacao_devaneios.png](simulacao_devaneios.png) (simulação da frase).

---

## 1. A obra

- Escultura de cabeça clássica com a tela VFD dentro e uma **lente Fresnel** na frente, para ampliar.
- Frase-chave: **"Devaneios do Aparato: A realidade é apenas uma sombra da verdade."**
- Tela: Noritake Itron GU256X128C-3900, 256×128 pontos, uma cor só (azul-esverdeada), 8 níveis de brilho.

## 2. O que está confirmado na tela física (laptop Windows, COM4)

| Item | Resultado |
|---|---|
| Conversor detectado pelo nº de série | ✓ COM4, serial `A1AEZRMTA` |
| Texto pelo `vfd.py` | ✓ "Ola" |
| Frase como imagem, com o "é" | ✓ foto do usuário: certa, sem embaralhar |
| Tempo de uma tela inteira | ✓ 4111 B em 1074 ms |
| Brilho e rodízio do modo exposição | ✓ confirmado pelo usuário |
| Todos os pontos acesos | ✓ acendeu; revelou o desgaste (seção 4) |

## 3. Decisões de desenho

- **Texto vai como imagem, não como texto da tela.** O texto nativo só tem ASCII (perde acentos) e
  3 tamanhos. Como imagem, usa-se Roboto Condensed (5 espessuras, em `assets/fonts/`), com acentos e
  no maior tamanho que couber.
- **Texto claro em fundo apagado.** Esconde quase todo o desgaste da tela.
- **Espelhar H/V** existe por precaução: lente usada como lupa (tela perto da lente) não inverte a
  imagem; com a tela longe da lente, pode inverter.
- **Painel a cada 2 s funciona** (a estimativa de 1,7 s por tela estava errada; o medido é 1,07 s).

## 4. O "histórico" que aparece com tudo aceso

**O que se vê:** com todos os pontos acesos, aparecem fantasmas mais escuros de conteúdos antigos:
a frase "uma sombra da verdade.", uma linha tipo eletrocardiograma, grades e barras.

**O que é:** desgaste do fósforo (burn-in). Não é memória, nem fonte, nem cabo.
- Cada ponto é um grão de fósforo que brilha ao ser atingido por elétrons e **perde eficiência com o uso**.
- Pontos que ficaram muito tempo acesos brilham menos que os vizinhos. Com tudo aceso, a diferença
  desenha o que já ficou parado na tela.
- A Noritake descreve isso na ficha do GU128X64-800B (mesma tecnologia): um padrão fixo aceso por
  "várias horas" reduz a eficiência do fósforo e causa brilho desigual. Recomenda **variar o padrão**.
- Quanto mais brilho e mais tempo, mais rápido o desgaste. **Não tem conserto.**

**Como distinguir de outros defeitos**

| Causa | Sintoma |
|---|---|
| Fonte fraca | a tela inteira escurece ou pisca, piora com muitos pontos acesos, ou reinicia |
| Cabo de dados ruim | texto trocado, imagem embaralhada ou deslocada |
| Desgaste do fósforo | fantasmas com a forma de conteúdos antigos, sempre no mesmo lugar |

A ficha da série indica 5 V / 850 mA para o modelo C; a fonte usada é de 2 A ou mais.

## 5. O que o app já faz contra o desgaste

- Rodízio de frases (troca a cada N segundos).
- Deslocamento de 1–2 pontos a cada minuto (13 posições).
- Brilho de 1 a 8 ajustável durante a exposição.

**Limite atual:** deslocar 2 pontos só suaviza a borda do fantasma; o miolo do traço (uns 3 pontos)
continua gastando os mesmos pontos.

## 6. Plano para espalhar o desgaste (aprovado em ideia, ainda NÃO implementado)

1. **Mapa de desgaste:** somar, ponto a ponto, as horas acesas (ponderadas pelo brilho), salvar em
   arquivo e mostrar na página. É uma conta, não uma medida, e começa do zero.
2. **Passeio largo guiado pelo mapa:** desenhar o texto a ~85 % do máximo para ganhar ~15 pontos de
   folga nos lados e ~10 em cima/embaixo; a cada minuto, escolher a posição que cai nos pontos menos
   gastos. Custo: letra ~15 % menor.
3. **Variar o desenho da mesma frase** (espessura, quebra de linhas). Opcional: mexe na estética.
4. **Pausas no escuro** entre frases: 20 % do tempo apagado = 20 % menos desgaste.
5. **Compensação** (acender os pontos menos gastos fora do horário): desligada por padrão. Iguala a
   tela, mas gasta vida útil; ganho pequeno para texto em fundo apagado.

Recomendação: fazer 1, 2 e 4; deixar 3 como opção.

## 7. Outras melhorias levantadas

- **Funcionar sozinho:** conectar e retomar a exposição ao ligar; reconectar se o USB sair; guardar
  rodízio e brilho em arquivo do app (hoje o rodízio fica no navegador).
- **Horário de descanso** e limite de tempo para "Acender todos"; lembrar o brilho escolhido.
- **Tipografia:** alinhamento, posição vertical, entrelinha; fonte de pontos para texto pequeno;
  transição entre frases usando os 8 níveis de brilho.
- **Hardware:** computador pequeno (ex.: Raspberry Pi) na base, em vez de laptop. Não testado.
- **Acabamento:** testes pytest, README, recusar no driver a sequência proibida
  (`1C 7C 4D D0 4D 4F 44 45 49 4E`), remover `vfd_monitor.py` e `vfd_claude.py` que o app não usa.
- **Do prompt original ainda faltam:** envio de imagem com pontilhado e logo (E3), painel ao vivo e
  relógio (E4), chat com o Claude (E5, opcional), testes e README (E6).

## 8. Onde comprar outra tela (pesquisa de 12/11/2026)

O modelo **GU256X128C-3900 (sem "B") saiu de linha**; o substituto direto é o **GU256X128C-3900B**.
Não foi testado se o 3900B aceita exatamente os mesmos comandos do app.

| Onde | Situação | Preço |
|---|---|---|
| Mercado Livre | **nenhum anúncio deste modelo** nos resultados de busca; o site bloqueou a consulta direta com CAPTCHA | — |
| Mercado Livre | existe outro VFD Itron, bem menor (PW-898-101, 112×16 pontos): não serve | — |
| AliExpress | anúncio do GU256X128C-3900 | US$ 223 |
| eBay | 3900B usado | US$ 185 a 268 |
| DigiKey | 3900B sem estoque, prazo de 17 semanas | US$ 440–475 |
| Mouser | 3900B; estoque divergente entre fontes (48 ou zero) | ~US$ 470 |
| Farnell | 3900B sem estoque | 377 € |

Cuidados: conferir estoque na página do vendedor; frete e imposto de importação entram por cima;
tela usada pode vir com o mesmo desgaste — pedir foto com todos os pontos acesos. Anúncios do
AliExpress às vezes trazem só o vidro, sem a placa: confirmar antes.

## 9. Fontes

- Ficha Noritake GU128X64-800B: https://www.mouser.com/catalog/specsheets/Noritake-9-05-2019-s-gu128x64-800b_e03.pdf
- Como as telas VFD falham: https://joes-tech-blog.blogspot.com/2020/06/vacuum-fluorescent-displays-how-they.html
- TME, burn-in em VFD: https://www.tme.com/us/en-us/news/library-articles/faq/page/79464/does-screen-burn-in-only-affect-oled-displays-or-does-it-also-affect-displays-using-other-technologies/
- Noritake, série GU-3000: https://www.noritake-elec.com/products/vfd-display-module/dot-matrix-graphic-display/gu-3000-series
- DigiKey 3900 (obsoleto): https://www.digikey.com/en/products/detail/noritake-company-inc/GU256X128C-3900/770194
- DigiKey 3900B: https://www.digikey.com/en/products/detail/GU256X128C-3900B/GU256X128C-3900B-ND/2639043
- Octopart: https://octopart.com/gu256x128c-3900b-noritake-20008256
- Farnell: https://pt.farnell.com/noritake-itron/gu256x128c-3900b/vfd-module-256x128/dp/1495430
- eBay: https://www.ebay.com/itm/127553507615 e https://www.ebay.com/itm/285515298007
- AliExpress: https://www.aliexpress.com/item/4000599297465.html
- Mercado Livre, outro VFD Itron: https://produto.mercadolivre.com.br/MLB-2641685353-display-pw-898-101-visor-vfd-grafico-serial-112-x-16-itron-_JM

## 10. Como abrir o app

Duplo clique em `vfd-studio/iniciar.bat` → Conectar → cartões Texto, Teste de pontos e Exposição.
Página: http://127.0.0.1:8765 (a janela preta do servidor precisa ficar aberta).
