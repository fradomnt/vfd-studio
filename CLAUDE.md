# VFD Studio — instruções para o Claude Code neste repositório

Leia antes de mexer: `README.md`, `docs/PESQUISA.md` (seção 10 = decisões e pendências), `docs/API.md`.
Protocolo e ligação da tela: `docs/ICD_tela_VFD.md`. Não invente comandos da tela: só os do ICD.

## O que é
Servidor local (FastAPI, `app.py`) + página única (`static/`) que controla a tela VFD Noritake
GU256X128C-3900 por USB-RS232. Texto vai como bitmap (fontes em `assets/fonts`). Cenas e configuração
em `cenas.json` / `config.json` (ao lado do código ou do executável, ver `caminhos.py`). Outro app
manda frases por `POST /api/v1/texto`. Roda em Windows e macOS; empacotado por `vfd_studio.spec`.

## Regras do projeto
- **Commits como `fradomnt <22111329+fradomnt@users.noreply.github.com>`** (autor e committer),
  mensagem em português, trailer `Co-Authored-By: fradomnt <22111329+fradomnt@users.noreply.github.com>`.
  Nunca o e-mail da Liberdade Solar aqui.
- **Créditos e textos públicos falam só do app.** Nada sobre obra, escultura, museu ou terceiros.
  Crédito único: "Desenvolvimento criativo: Frado Monteiro — frado.com.br".
- **Você não enxerga a tela.** Nunca afirme que algo apareceu nela sem o usuário confirmar.
- **Proteger o fósforo:** a tela tem desgaste. Texto claro em fundo apagado; nunca propor fundos acesos
  nem deixar "acender todos" por muito tempo; manter guarda-tela, rodízio, brilho baixo e apagar ao sair.
- **Energia:** a tela segura a última imagem se ficar alimentada sem o computador. Fonte do visor junto
  com o Mac (README, seção "Energia").
- **Não mudar fios, SW1, baud nem o formato do bitmap.** Problema na imagem = procurar no software.
- **Usuário quer praticidade:** entregar funcionando, sem pedir medições de bancada. `fradola` =
  executar direto, commit e push imediatos. `PARA!` = parar tudo.
- **Deploy (commit, push, release, clone) por subagente Haiku** com brief completo; o modelo principal
  pensa, desenha e escreve código.
- Visual da página: minimalista estilo HERE Wallet (fundo quase branco, borda preta 2 px, sombra dura,
  texto preto); cor só em detalhes pequenos; nada baixado da internet.
- Dependências novas só com autorização; listar em `requirements.txt`.

## Verificar antes de dizer que está pronto
- `python -m py_compile app.py cenas.py presets.py caminhos.py vfd.py` e `node --check static/app.js`.
- Testes com tela falsa (classe com `bitmap/brilho/iniciar/limpar/desligar/fechar`) para rotas e autonomia.
- Conferir a página no navegador em largura larga e estreita.

## Pendências conhecidas (nov/2026)
Teste real no Mac mini e geração do `.app` (só no Mac); linguagem do app do Marlus; horário de
funcionamento; log em arquivo; vigia de travamento; botão "Testar autonomia"; `atualizar.command`;
aviso remoto; rodízio de pixels por mapa de desgaste; fila vs. cancelamento de frases; `logo_vfd.bin`.
