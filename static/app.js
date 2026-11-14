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
  textoEnviar: $("texto-enviar"), aoVivo: $("ao-vivo"), logoEnviar: $("logo-enviar"),
  tamAuto: $("tam-auto"), tam: $("tam"), tamValor: $("tam-valor"),
  brilho: $("brilho"), brilhoValor: $("brilho-valor"), expoInfo: $("expo-info"),
  expoLista: $("expo-lista"), expoVazia: $("expo-vazia"), expoAdd: $("expo-add"),
  expoSeg: $("expo-seg"), expoDesloc: $("expo-desloc"),
  expoIniciar: $("expo-iniciar"), expoParar: $("expo-parar"),
  cenaSel: $("cena-sel"), cenaNome: $("cena-nome"), cenaSalvar: $("cena-salvar"), cenaAplicar: $("cena-aplicar"),
  cenaApagar: $("cena-apagar"), apiModo: $("api-modo"), apiPpq: $("api-ppq"), apiSeg: $("api-seg"),
  autoConectar: $("auto-conectar"), autoExpo: $("auto-expo"), autoBv: $("auto-bv"), bvTexto: $("bv-texto"),
  bvSeg: $("bv-seg"), autoSalvar: $("auto-salvar"), guarda: $("guarda"), guardaSeg: $("guarda-seg"), testeSeg: $("teste-seg"), exibindo: $("exibindo"), ultimaApi: $("ultima-api"),
  cenaInfo: $("cena-info"), apiExemplo: $("api-exemplo"), apiCopiar: $("api-copiar"), apiTestar: $("api-testar"),
  dlgPeso: $("dlg-peso"), dlgTam: $("dlg-tam"), dstPeso: $("dst-peso"), dstTam: $("dst-tam"), dlgModo: $("dlg-modo"),
  dlgCps: $("dlg-cps"), dlgSeg: $("dlg-seg"), dlgTestar: $("dlg-testar"),
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
  if (s.config) mostrarConfig(s.config);
  if (s.versao) $("versao").textContent = s.versao;
  if (s.exibindo) {
    const nomes = { nada: "nada", "boas-vindas": "boas-vindas", rodizio: "rodízio", api: "frase da API", quadro: "quadro de outro app", dialogo: "diálogo da obra", manual: "envio manual", teste: "teste de pontos" };
    el.exibindo.textContent = nomes[s.exibindo] || s.exibindo;
  }
  if (s.ultima_api) el.ultimaApi.textContent = `Última da API às ${s.ultima_api.hora}: “${s.ultima_api.texto}”`;
  mostrarExpo();
  atualizarBotoes();
}

function atualizarBotoes() {
  el.conectar.disabled = conectado || !el.porta.value;
  el.desconectar.disabled = !conectado;
  el.iniciar.disabled = !conectado;
  el.textoEnviar.disabled = !conectado;
  el.logoEnviar.disabled = !conectado;
  el.apiTestar.disabled = !conectado;
  el.dlgTestar.disabled = !conectado;
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

// ---------------------------------------------------------------- cenas
let cenasVistas = {};
let configVista = {};

function mostrarConfig(cfg) {
  configVista = cfg;
  el.autoConectar.checked = !!cfg.auto_conectar;
  el.autoExpo.checked = !!cfg.auto_exposicao;
  el.autoBv.checked = !!cfg.boas_vindas;
  if (document.activeElement !== el.bvTexto) el.bvTexto.value = cfg.boas_vindas_texto || "";
  el.bvSeg.value = cfg.boas_vindas_segundos || 8;
  el.guarda.checked = cfg.guarda_tela !== false;
  el.guardaSeg.value = cfg.guarda_tela_segundos || 120;
  el.testeSeg.value = cfg.teste_segundos || 30;
  el.cenaInfo.textContent = `cena padrão: ${cfg.cena_padrao}`;
}

async function carregarCenas(selecionar) {
  const { cenas, config } = await api("/api/cenas");
  cenasVistas = cenas;
  mostrarConfig(config);
  el.cenaSel.innerHTML = "";
  for (const nome of Object.keys(cenas).sort()) {
    el.cenaSel.add(new Option(nome === config.cena_padrao ? `${nome} (padrão)` : nome, nome));
  }
  el.cenaSel.value = selecionar || config.cena_padrao || el.cenaSel.value;
  el.cenaNome.value = el.cenaSel.value;
  const c = cenas[el.cenaSel.value];
  if (c) { el.apiModo.value = c.api_modo; el.apiPpq.value = c.api_palavras_por_quadro; el.apiSeg.value = c.api_segundos; dialogoParaPagina(c); }
}

// Os campos do diálogo da obra, da cena para a página.
function dialogoParaPagina(c) {
  el.dlgPeso.value = c.dialogo_peso; el.dlgTam.value = c.dialogo_tamanho;
  el.dstPeso.value = c.destaque_peso; el.dstTam.value = c.destaque_tamanho;
  el.dlgModo.value = c.dialogo_modo; el.dlgCps.value = c.dialogo_cps; el.dlgSeg.value = c.dialogo_segundos;
}

// A cena é montada a partir do que está na página agora.
function montarCena() {
  const p = pedidoTexto();
  return {
    peso: p.peso, tamanho: p.tamanho, espelhar_h: p.espelhar_h, espelhar_v: p.espelhar_v,
    brilho: Number(el.brilho.value), segundos: Number(el.expoSeg.value) || 120, deslocar: el.expoDesloc.checked,
    rodizio: rodizio, api_modo: el.apiModo.value, api_palavras_por_quadro: Number(el.apiPpq.value) || 1,
    api_segundos: Number(el.apiSeg.value) || 90,
    dialogo_modo: el.dlgModo.value, dialogo_cps: Number(el.dlgCps.value) || 22,
    dialogo_peso: el.dlgPeso.value, dialogo_tamanho: Number(el.dlgTam.value) || 14,
    destaque_peso: el.dstPeso.value, destaque_tamanho: Number(el.dstTam.value) || 20,
    dialogo_segundos: Number(el.dlgSeg.value) || 180,
  };
}

// Carrega uma cena nos controles da página (sem mandar nada para a tela).
function cenaParaPagina(c) {
  el.peso.value = c.peso;
  el.tamAuto.checked = !c.tamanho; el.tam.disabled = el.tamAuto.checked;
  if (c.tamanho) el.tam.value = c.tamanho;
  el.espH.checked = c.espelhar_h; el.espV.checked = c.espelhar_v;
  el.brilho.value = c.brilho; el.brilhoValor.textContent = `${c.brilho} de 8`;
  el.expoSeg.value = c.segundos; el.expoDesloc.checked = c.deslocar;
  el.apiModo.value = c.api_modo; el.apiPpq.value = c.api_palavras_por_quadro; el.apiSeg.value = c.api_segundos;
  dialogoParaPagina(c);
  rodizio = c.rodizio.map((f) => ({ ...f }));
  salvarRodizio(); mostrarExpo(); textoMudou();
}

async function salvarCena() {
  const nome = el.cenaNome.value.trim();
  if (!nome) throw new Error("Dê um nome à cena.");
  const r = await api("/api/cenas", { nome, cena: montarCena() });
  await carregarCenas(r.nome);
}

async function aplicarCena() {
  const nome = el.cenaSel.value;
  if (!nome) return;
  cenaParaPagina(cenasVistas[nome]);
  await api(`/api/cenas/${encodeURIComponent(nome)}/aplicar`, {});
  await carregarCenas(nome);
}

async function apagarCena() {
  const nome = el.cenaSel.value;
  if (!nome || !confirm(`Apagar a cena “${nome}”?`)) return;
  const r = await fetch(`/api/cenas/${encodeURIComponent(nome)}`, { method: "DELETE" });
  const j = await r.json();
  if (!j.ok) throw new Error(j.erro);
  await carregarCenas();
}

function salvarAutomatico() {
  return api("/api/config", {
    auto_conectar: el.autoConectar.checked, auto_exposicao: el.autoExpo.checked, boas_vindas: el.autoBv.checked,
    boas_vindas_texto: el.bvTexto.value, boas_vindas_segundos: Number(el.bvSeg.value) || 8,
    guarda_tela: el.guarda.checked, guarda_tela_segundos: Number(el.guardaSeg.value) || 120,
    teste_segundos: Number(el.testeSeg.value) || 30,
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
el.logoEnviar.addEventListener("click", () => acao(el.logoEnviar, () => api("/api/desenho/enviar", { tipo: "logo" })));
// Ctrl+Enter (ou Cmd+Enter) no texto = Enviar para a tela
el.texto.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey) && conectado) { ev.preventDefault(); enviarTexto(); }
});
for (const b of el.testes) b.addEventListener("click", () => acao(b, () => enviarTeste(b)));
el.brilho.addEventListener("input", () => { el.brilhoValor.textContent = `${el.brilho.value} de 8`; el.cenaInfo.textContent = `brilho ${el.brilho.value} · não salvo na cena`; });
el.brilho.addEventListener("change", () => acao(el.brilho, () => api("/api/brilho", { nivel: Number(el.brilho.value) })));
el.expoAdd.addEventListener("click", () => acao(el.expoAdd, async () => adicionarAoRodizio()));
el.expoIniciar.addEventListener("click", () => acao(el.expoIniciar, iniciarExpo));
el.expoParar.addEventListener("click", () => acao(el.expoParar, () => api("/api/exposicao/parar", {})));
el.cenaSel.addEventListener("change", () => {
  el.cenaNome.value = el.cenaSel.value;
  const c = cenasVistas[el.cenaSel.value];
  if (c) cenaParaPagina(c);
});
el.cenaSalvar.addEventListener("click", () => acao(el.cenaSalvar, salvarCena));
el.cenaAplicar.addEventListener("click", () => acao(el.cenaAplicar, aplicarCena));
el.cenaApagar.addEventListener("click", () => acao(el.cenaApagar, apagarCena));
el.autoSalvar.addEventListener("click", () => acao(el.autoSalvar, salvarAutomatico));
const EXEMPLOS_API = {
  curl: ["curl -X POST http://127.0.0.1:8765/api/v1/texto \\",
         "  -H \"Content-Type: application/json\" \\",
         "  -d '{\"texto\": \"A dúvida é o começo da sabedoria.\", \"origem\": \"meu-app\"}'"].join("\n"),
  python: `import requests

r = requests.post("http://127.0.0.1:8765/api/v1/texto",
                  json={"texto": "A dúvida é o começo da sabedoria.", "origem": "meu-app"},
                  timeout=5)
print(r.json())   # {"ok": true, "cena": "museu", "modo": "palavra", ...}`,
  js: `const r = await fetch("http://127.0.0.1:8765/api/v1/texto", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ texto: "A dúvida é o começo da sabedoria.", origem: "meu-app" }),
});
console.log(await r.json()); // { ok: true, cena: "museu", modo: "palavra", ... }`,
};
const elLing = $("api-ling");
function mostrarExemploApi() { el.apiExemplo.textContent = EXEMPLOS_API[elLing.value]; }
elLing.addEventListener("change", mostrarExemploApi);
function modoMudou() { document.querySelector(".so-palavra").hidden = el.apiModo.value !== "palavra"; }
el.apiModo.addEventListener("change", modoMudou); modoMudou();
mostrarExemploApi();
for (const b of document.querySelectorAll("button.copiar")) {
  b.addEventListener("click", () => acao(b, async () => {
    await navigator.clipboard.writeText($(b.dataset.alvo).textContent);
    const antes = b.textContent; b.textContent = "Copiado"; setTimeout(() => { b.textContent = antes; }, 1500);
  }));
}
el.apiCopiar.addEventListener("click", () => acao(el.apiCopiar, async () => {
  await navigator.clipboard.writeText(el.apiExemplo.textContent);
  el.apiCopiar.textContent = "Copiado"; setTimeout(() => { el.apiCopiar.textContent = "Copiar exemplo"; }, 1500);
}));
el.dlgTestar.addEventListener("click", () => acao(el.dlgTestar, () => api("/api/v1/dialogo", {
  fala: "A dúvida não é o contrário da certeza; é o que a certeza esconde quando se olha de perto demais.",
  destaque: "O que resta é o espelho", origem: "página",
})));
el.apiTestar.addEventListener("click", () => acao(el.apiTestar, () => api("/api/v1/texto", {
  texto: "A dúvida é o começo da sabedoria.", origem: "teste da página", segundos: 20,
})));
carregarCenas().then(() => { const c = cenasVistas[el.cenaSel.value]; if (c) cenaParaPagina(c); })
  .catch((e) => mostrarErro(e.message));
mostrarExpo();

carregarPortas().catch((e) => mostrarErro(e.message));
carregarPresets().catch((e) => mostrarErro(e.message));
abrirWebSocket();
