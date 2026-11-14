// VFD Studio — lógica da página (sem framework).
// Comandos vão por HTTP (fetch); estado ao vivo (status, log, prévia) chega pelo WebSocket /ws.
"use strict";

const W = 256, H = 128, ESCALA = 3;
const $ = (id) => document.getElementById(id);

const el = {
  porta: $("porta"), info: $("porta-info"), status: $("status"), erro: $("erro"),
  atualizar: $("atualizar"), conectar: $("conectar"), desconectar: $("desconectar"),
  iniciar: $("iniciar"), log: $("log"), logConta: $("log-conta"), previa: $("previa"),
  previaDica: $("previa-dica"), previaEstado: $("previa-estado"),
  preset: $("preset"), espH: $("esp-h"), espV: $("esp-v"),
  texto: $("texto"), textoInfo: $("texto-info"), peso: $("peso"),
  textoEnviar: $("texto-enviar"), aoVivo: $("ao-vivo"),
  tamAuto: $("tam-auto"), tam: $("tam"), tamValor: $("tam-valor"),
  brilho: $("brilho"), brilhoValor: $("brilho-valor"), expoInfo: $("expo-info"),
  expoLista: $("expo-lista"), expoVazia: $("expo-vazia"), expoAdd: $("expo-add"),
  expoSeg: $("expo-seg"), expoDesloc: $("expo-desloc"),
  expoIniciar: $("expo-iniciar"), expoParar: $("expo-parar"),
  testes: [...document.querySelectorAll("button.teste")],
};
const MSG_SERVIDOR_PARADO =
  "O VFD Studio foi fechado. Abra o iniciar.bat (ou iniciar.command no Mac) de novo. Esta página volta sozinha.";
let conectado = false;
let portasVistas = [];

// ------------------------------------------------------------------ HTTP
async function api(caminho, corpo) {
  const opcoes = corpo === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo),
  };
  let r;
  try { r = await fetch(caminho, opcoes); }
  catch { throw new Error(MSG_SERVIDOR_PARADO); }
  const dados = await r.json().catch(() => ({ ok: false, erro: `O servidor respondeu algo inesperado (HTTP ${r.status}). Veja o log.` }));
  if (!r.ok || dados.ok === false) throw new Error(dados.erro || `Erro ${r.status}`);
  return dados;
}

function mostrarErro(msg) {
  el.erro.textContent = msg || "";
  el.erro.hidden = !msg;
}

// Executa uma ação de botão: desabilita enquanto roda e mostra o erro, se houver.
async function acao(botao, fn) {
  mostrarErro("");
  botao.classList.add("ocupado");
  botao.disabled = true;
  try { await fn(); }
  catch (e) { mostrarErro(e.message); }
  finally { botao.classList.remove("ocupado"); botao.disabled = false; atualizarBotoes(); }
}

// ----------------------------------------------------------------- portas
async function carregarPortas() {
  const { portas, sugerida } = await api("/api/portas");
  portasVistas = portas;
  const atual = el.porta.value;
  el.porta.innerHTML = "";
  if (!portas.length) {
    el.porta.add(new Option("Nenhuma porta encontrada", ""));
  }
  for (const p of portas) {
    const marca = p.conversor ? "  ✓ conversor da tela" : (p.ftdi ? "  · FTDI" : "");
    el.porta.add(new Option(`${p.porta} — ${p.descricao}${marca}`, p.porta));
  }
  el.porta.value = conectado && atual ? atual : (sugerida || atual || (portas[0] && portas[0].porta) || "");
  mostrarInfoPorta();
  atualizarBotoes();
}

function mostrarInfoPorta() {
  const p = portasVistas.find((x) => x.porta === el.porta.value);
  if (!p) {
    el.info.textContent = "Nenhum conversor à vista. Plugue o USB e clique em Atualizar.";
  } else if (p.conversor) {
    el.info.textContent = `Conversor da tela (PCM-KW-469 · ${p.serial}).`;
  } else {
    el.info.textContent = `Esta não é a porta do conversor da tela (serial ${p.serial || "—"}). Confira a escolha.`;
  }
}

// ------------------------------------------------------------------ status
function aplicarStatus(s) {
  conectado = !!s.conectado;
  el.status.textContent = conectado ? `conectado · ${s.porta}` : "desconectado";
  el.status.className = "status " + (conectado ? "ligado" : "desligado");
  if (conectado && s.porta) el.porta.value = s.porta;
  if (s.brilho) { el.brilho.value = s.brilho; el.brilhoValor.textContent = `${s.brilho} de 8`; }
  if (s.exposicao) expo = s.exposicao;
  mostrarExpo();
  atualizarBotoes();
}

function atualizarBotoes() {
  el.conectar.disabled = conectado || !el.porta.value;
  el.desconectar.disabled = !conectado;
  el.iniciar.disabled = !conectado;
  el.textoEnviar.disabled = !conectado;
  for (const b of el.testes) b.disabled = !conectado;
  el.brilho.disabled = !conectado;
  el.expoIniciar.disabled = !conectado || expo.ativa || !rodizio.length;
  el.expoParar.disabled = !expo.ativa;
  el.porta.disabled = conectado;
}

// Rótulo da prévia: "simulação" = só na página; "último envio" = o que foi mandado à tela.
function marcarPrevia(simulacao) {
  el.previaEstado.textContent = simulacao ? "simulação · ainda não enviada" : "o último envio, ponto a ponto";
  el.previaEstado.classList.toggle("simulacao", simulacao);
}

// ------------------------------------------------------------------- texto
// O texto é desenhado no servidor como imagem. A prévia acompanha a digitação;
// para a tela vai só no botão, ou sozinho se "Enviar enquanto digito" estiver marcado.
let presetsVistos = [];
let relogioPrevia = null, relogioEnvio = null;
let enviando = false, envioPendente = false;

function pedidoTexto() {
  return { tipo: "texto", texto: el.texto.value, peso: el.peso.value,
           tamanho: el.tamAuto.checked ? 0 : Number(el.tam.value),
           espelhar_h: el.espH.checked, espelhar_v: el.espV.checked };
}

async function carregarPresets() {
  const { presets } = await api("/api/presets");
  presetsVistos = presets;
  el.preset.innerHTML = "";
  el.preset.add(new Option("Frases prontas…", ""));
  for (const p of presets) el.preset.add(new Option(p.nome, p.id));
}

function infoTexto(r) {
  el.textoInfo.textContent = r.linhas
    ? `letra ${r.letra} pt · ${r.linhas} linha${r.linhas > 1 ? "s" : ""}` +
      (r.coube === false ? " · passou da tela, diminua a letra" : "")
    : "digite e veja na prévia";
  el.textoInfo.classList.toggle("simulacao", r.coube === false);
  // No automático, o controle acompanha o tamanho escolhido: ao desmarcar, parte dele.
  if (el.tamAuto.checked && r.letra) el.tam.value = r.letra;
  el.tamValor.textContent = el.tamAuto.checked ? "maior que couber" : `${el.tam.value} pt`;
}

async function verTexto() {
  try {
    const r = await api("/api/desenho/previa", pedidoTexto());
    desenharPrevia(r.bits);
    marcarPrevia(true);
    infoTexto(r);
    mostrarErro("");
  } catch (e) { mostrarErro(e.message); }
}

// Envia o texto. Se chegar outro pedido durante um envio (~1 s), manda o mais novo ao terminar.
async function enviarTexto() {
  if (enviando) { envioPendente = true; return; }
  enviando = true;
  try {
    infoTexto(await api("/api/desenho/enviar", pedidoTexto()));
    mostrarErro("");
  } catch (e) { mostrarErro(e.message); }
  finally {
    enviando = false;
    if (envioPendente) { envioPendente = false; enviarTexto(); }
  }
}

function textoMudou() {
  clearTimeout(relogioPrevia); clearTimeout(relogioEnvio);
  relogioPrevia = setTimeout(verTexto, 200);
  if (el.aoVivo.checked && conectado) relogioEnvio = setTimeout(enviarTexto, 900);
}

// ---------------------------------------------------------------- exposição
// O rodízio fica guardado neste navegador (localStorage); o servidor só recebe ao iniciar.
let expo = { ativa: false, frase: 0, total: 0 };
let rodizio = [];
try { rodizio = JSON.parse(localStorage.getItem("vfd-rodizio") || "[]"); } catch { rodizio = []; }

function salvarRodizio() {
  try { localStorage.setItem("vfd-rodizio", JSON.stringify(rodizio)); } catch { /* sem armazenamento */ }
}

function mostrarExpo() {
  el.expoInfo.textContent = expo.ativa ? `ligada · frase ${expo.frase || 1} de ${expo.total}` : "parada";
  el.expoInfo.classList.toggle("ativa", expo.ativa);
  el.expoLista.innerHTML = "";
  rodizio.forEach((f, i) => {
    const li = document.createElement("li");
    if (expo.ativa && expo.frase === i + 1) li.className = "atual";
    const frase = document.createElement("span");
    frase.className = "frase"; frase.textContent = f.texto.replace(/\n/g, " / ");
    const meta = document.createElement("span");
    meta.className = "meta"; meta.textContent = f.tamanho ? `${f.tamanho} pt` : "auto";
    const tirar = document.createElement("button");
    tirar.className = "secundario"; tirar.textContent = "Tirar";
    tirar.addEventListener("click", () => { rodizio.splice(i, 1); salvarRodizio(); mostrarExpo(); atualizarBotoes(); });
    li.append(frase, meta, tirar);
    el.expoLista.append(li);
  });
  el.expoVazia.hidden = rodizio.length > 0;
}

function adicionarAoRodizio() {
  const p = pedidoTexto();
  if (!p.texto.trim()) throw new Error("Escreva um texto antes de adicionar ao rodízio.");
  rodizio.push({ texto: p.texto, peso: p.peso, tamanho: p.tamanho });
  salvarRodizio();
  mostrarExpo();
}

function iniciarExpo() {
  return api("/api/exposicao/iniciar", {
    frases: rodizio, segundos: Number(el.expoSeg.value) || 120, deslocar: el.expoDesloc.checked,
    espelhar_h: el.espH.checked, espelhar_v: el.espV.checked,
  });
}

// ------------------------------------------------------------ teste de pontos
async function enviarTeste(botao) {
  await api("/api/desenho/enviar", { tipo: "teste", padrao: botao.dataset.padrao });
}

// --------------------------------------------------------------------- log
function adicionarLog(item) {
  const li = document.createElement("li");
  const hora = document.createElement("span");
  hora.className = "hora"; hora.textContent = item.t;
  const msg = document.createElement("span");
  msg.className = item.nivel === "erro" ? "erro-log" : item.nivel;
  msg.textContent = item.msg;
  li.append(hora, msg);
  el.log.append(li);
  while (el.log.children.length > 200) el.log.firstChild.remove();
  el.log.scrollTop = el.log.scrollHeight;
  el.logConta.textContent = `${el.log.children.length} / 200`;
}

// ------------------------------------------------------------------ prévia
// Recebe os 4096 bytes no formato da tela (256 colunas × 16 bytes, bit 7 = ponto de cima)
// e desenha exatamente esses bits no canvas ampliado 3×.
const ctx = el.previa.getContext("2d");
function desenharPrevia(b64) {
  const bits = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  el.previaDica.hidden = bits.some((b) => b !== 0);
  const css = getComputedStyle(document.documentElement);
  ctx.fillStyle = css.getPropertyValue("--vfd-fundo").trim();
  ctx.fillRect(0, 0, W * ESCALA, H * ESCALA);
  const aceso = css.getPropertyValue("--vfd-ponto").trim();
  const apagado = css.getPropertyValue("--vfd-apagado").trim();
  for (let x = 0; x < W; x++) {
    for (let yb = 0; yb < H / 8; yb++) {
      const byte = bits[x * 16 + yb];
      for (let i = 0; i < 8; i++) {
        ctx.fillStyle = (byte & (0x80 >> i)) ? aceso : apagado;
        ctx.fillRect(x * ESCALA, (yb * 8 + i) * ESCALA, ESCALA - 1, ESCALA - 1);
      }
    }
  }
}

// --------------------------------------------------------------- WebSocket
function abrirWebSocket() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.tipo === "inicial") {
      if (el.erro.textContent === MSG_SERVIDOR_PARADO) mostrarErro("");
      el.log.innerHTML = "";
      m.log.forEach(adicionarLog);
      aplicarStatus(m);
      desenharPrevia(m.previa);
    } else if (m.tipo === "log") {
      adicionarLog(m.item);
    } else if (m.tipo === "status") {
      aplicarStatus(m);
      if (!m.conectado) carregarPortas().catch(() => {});
    } else if (m.tipo === "previa") {
      desenharPrevia(m.bits);
      marcarPrevia(false);
    }
  };
  ws.onclose = () => {
    el.status.textContent = "servidor parado";
    el.status.className = "status desligado";
    conectado = false;
    atualizarBotoes();
    mostrarErro(MSG_SERVIDOR_PARADO);
    setTimeout(abrirWebSocket, 2000);   // tenta reconectar
  };
}

// ----------------------------------------------------------------- eventos
el.porta.addEventListener("change", () => { mostrarInfoPorta(); atualizarBotoes(); });
el.atualizar.addEventListener("click", () => acao(el.atualizar, carregarPortas));
el.conectar.addEventListener("click", () => acao(el.conectar, async () => {
  aplicarStatus(await api("/api/conectar", { porta: el.porta.value }));
}));
el.desconectar.addEventListener("click", () => acao(el.desconectar, async () => {
  aplicarStatus(await api("/api/desconectar", {}));
}));
el.iniciar.addEventListener("click", () => acao(el.iniciar, () => api("/api/iniciar", {})));

el.texto.addEventListener("input", textoMudou);
el.peso.addEventListener("change", textoMudou);
el.tam.addEventListener("input", textoMudou);
el.tamAuto.addEventListener("change", () => { el.tam.disabled = el.tamAuto.checked; textoMudou(); });
el.espH.addEventListener("change", textoMudou);
el.espV.addEventListener("change", textoMudou);
el.preset.addEventListener("change", () => {
  const p = presetsVistos.find((x) => x.id === el.preset.value);
  if (!p) return;
  el.texto.value = p.texto;
  el.peso.value = p.peso;
  el.tamAuto.checked = true; el.tam.disabled = true;
  el.preset.value = "";          // volta para "Frases prontas…": o texto agora é editável
  textoMudou();
});
el.textoEnviar.addEventListener("click", () => acao(el.textoEnviar, enviarTexto));
// Ctrl+Enter (ou Cmd+Enter) no texto = Enviar para a tela
el.texto.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey) && conectado) { ev.preventDefault(); enviarTexto(); }
});
for (const b of el.testes) b.addEventListener("click", () => acao(b, () => enviarTeste(b)));
el.brilho.addEventListener("input", () => { el.brilhoValor.textContent = `${el.brilho.value} de 8`; });
el.brilho.addEventListener("change", () => acao(el.brilho, () => api("/api/brilho", { nivel: Number(el.brilho.value) })));
el.expoAdd.addEventListener("click", () => acao(el.expoAdd, async () => adicionarAoRodizio()));
el.expoIniciar.addEventListener("click", () => acao(el.expoIniciar, iniciarExpo));
el.expoParar.addEventListener("click", () => acao(el.expoParar, () => api("/api/exposicao/parar", {})));
mostrarExpo();

carregarPortas().catch((e) => mostrarErro(e.message));
carregarPresets().catch((e) => mostrarErro(e.message));
abrirWebSocket();
