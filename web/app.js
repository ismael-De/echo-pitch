// Echo Pitch UI: vanilla JS, consumes the FastAPI SSE replay stream.
const $ = (id) => document.getElementById(id);
const I18N = {
  en: {audioOn:'Audio on', a11yOn:'Audio-first mode on: every line is read aloud. Keys: Space kick off, S score, A off.', prodOn:'Producer mode on: AI-written rewrites wait here for Approve / Reject. Verified template lines still go out live.', prodIdle:'Press Kick off. AI drafts will appear here for approval.', prodOff:'AI is off for this visitor right now (fair-use limit: 6 AI streams per hour), so only verified template lines are shown and there is nothing to approve.', prodNoAI:'This server runs without the AI writer (offline agents), so every line is a verified template and there is nothing to approve.', prodWait:'Waiting for the next AI rewrite of a key moment…', audio:"Audio", a11y:"Audio-first", approval:"Producer", audit:"Audit", verified:"verified", approve:"Approve", reject:"Reject", pending:"AI draft awaiting producer", evidence:"Evidence", tagline:"AI match storyteller", match:"Match", speed:"Speed", fan:"Fan", analyst:"Analyst", club:"Club",
       player:"Player", none:"None", start:"▶ Kick off", restart:"↻ Restart", possession:"Possession", shots:"Shots",
       ontarget:"On target", passes:"Pass %", momentum:"Momentum", commentary:"Live commentary",
       moments:"Key moments · why they matter", agents:"Agents", fulltime:"Full-time recap", close:"Close",
       potm:"Player of the match", controlled:"controlled", contested:"contested", chaotic:"chaotic",
       "fast and direct":"fast & direct", "slow build-up":"slow build-up", steady:"steady", goal:"GOAL!",
       xg:"xG", difficulty:"Pass difficulty", speedAlert:"km/h", attacks:"attacks"},
  ar: {audioOn:'الصوت يعمل', a11yOn:'الوضع الصوتي مفعّل: تُقرأ كل الأسطر بصوت عالٍ. المفاتيح: مسافة للبدء، S للنتيجة، A للإيقاف.', prodOn:'وضع المنتج مفعّل: صياغات الذكاء الاصطناعي تنتظر هنا الموافقة أو الرفض. الأسطر الموثّقة الجاهزة تُعرض مباشرة.', prodIdle:'اضغط بدء المباراة. ستظهر مسودات الذكاء الاصطناعي هنا للموافقة.', prodOff:'الذكاء الاصطناعي متوقف لهذا الزائر حالياً (حد الاستخدام: 6 بثوث في الساعة)، لذلك تُعرض أسطر القوالب الموثّقة فقط ولا يوجد ما يُوافَق عليه.', prodNoAI:'هذا الخادم يعمل دون كاتب الذكاء الاصطناعي، لذلك كل الأسطر قوالب موثّقة ولا يوجد ما يُوافَق عليه.', prodWait:'بانتظار الصياغة التالية من الذكاء الاصطناعي لأهم اللحظات…', audio:"الصوت", a11y:"وضع صوتي", approval:"المنتج", audit:"السجل", verified:"موثّق", approve:"موافقة", reject:"رفض", pending:"مسودة AI بانتظار المنتج", evidence:"الدليل", tagline:"راوي المباريات بالذكاء الاصطناعي", match:"المباراة", speed:"السرعة", fan:"مشجّع", analyst:"محلّل",
       club:"النادي", player:"اللاعب", none:"لا شيء", start:"▶ ابدأ", restart:"↻ إعادة", possession:"الاستحواذ",
       shots:"التسديدات", ontarget:"على المرمى", passes:"دقة التمرير", momentum:"الزخم", commentary:"التعليق المباشر",
       moments:"اللحظات الحاسمة · لماذا تهم", agents:"الوكلاء", fulltime:"ملخص المباراة", close:"إغلاق",
       potm:"أفضل لاعب", controlled:"منظّم", contested:"متكافئ", chaotic:"فوضوي", "fast and direct":"سريع ومباشر",
       "slow build-up":"بناء هادئ", steady:"متوازن", goal:"هدف!", xg:"xG", difficulty:"صعوبة التمريرة",
       speedAlert:"كم/س", attacks:"يهاجم"},
  es: {audio:"Audio", a11y:"Modo audio", approval:"Productor", audit:"Registro", verified:"verificado", approve:"Aprobar", reject:"Rechazar", pending:"Borrador IA pendiente", evidence:"Evidencia", tagline:"Narrador de partidos con IA", match:"Partido", speed:"Velocidad", fan:"Aficionado", analyst:"Analista",
       club:"Club", player:"Jugador", none:"Ninguno", start:"▶ Empezar", restart:"↻ Reiniciar", possession:"Posesión",
       shots:"Tiros", ontarget:"A puerta", passes:"% pases", momentum:"Impulso", commentary:"Comentario en directo",
       moments:"Momentos clave · por qué importan", agents:"Agentes", fulltime:"Resumen final", close:"Cerrar",
       potm:"Jugador del partido", controlled:"controlado", contested:"disputado", chaotic:"caótico",
       "fast and direct":"rápido y directo", "slow build-up":"elaboración lenta", steady:"estable", goal:"¡GOL!",
       xg:"xG", difficulty:"Dificultad del pase", speedAlert:"km/h", attacks:"ataca"},
  fr: {audio:"Audio", a11y:"Mode audio", approval:"Producteur", audit:"Journal", verified:"vérifié", approve:"Valider", reject:"Rejeter", pending:"Brouillon IA en attente", evidence:"Preuve", tagline:"Le conteur de matchs IA", match:"Match", speed:"Vitesse", fan:"Supporter", analyst:"Analyste",
       club:"Club", player:"Joueur", none:"Aucun", start:"▶ Coup d'envoi", restart:"↻ Rejouer", possession:"Possession",
       shots:"Tirs", ontarget:"Cadrés", passes:"% passes", momentum:"Dynamique", commentary:"Commentaire en direct",
       moments:"Moments clés · pourquoi ils comptent", agents:"Agents", fulltime:"Résumé du match", close:"Fermer",
       potm:"Homme du match", controlled:"maîtrisé", contested:"disputé", chaotic:"décousu",
       "fast and direct":"rapide et direct", "slow build-up":"construction lente", steady:"équilibré", goal:"BUT !",
       xg:"xG", difficulty:"Difficulté de passe", speedAlert:"km/h", attacks:"attaque"},
  pt: {audio:"Áudio", a11y:"Modo áudio", approval:"Produtor", audit:"Registro", verified:"verificado", approve:"Aprovar", reject:"Rejeitar", pending:"Rascunho IA aguardando", evidence:"Evidência", tagline:"Narrador de jogos com IA", match:"Jogo", speed:"Velocidade", fan:"Torcedor", analyst:"Analista",
       club:"Clube", player:"Jogador", none:"Nenhum", start:"▶ Começar", restart:"↻ Reiniciar", possession:"Posse",
       shots:"Finalizações", ontarget:"No alvo", passes:"% passes", momentum:"Momento", commentary:"Narração ao vivo",
       moments:"Lances decisivos · por que importam", agents:"Agentes", fulltime:"Resumo do jogo", close:"Fechar",
       potm:"Craque do jogo", controlled:"controlado", contested:"disputado", chaotic:"caótico",
       "fast and direct":"rápido e direto", "slow build-up":"construção lenta", steady:"estável", goal:"GOL!",
       xg:"xG", difficulty:"Dificuldade do passe", speedAlert:"km/h", attacks:"ataca"},
};
const qs = new URLSearchParams(location.search);
const S = {persona: qs.get("persona") || "fan", lang: qs.get("lang") || "en", club: qs.get("club") || "",
           player: qs.get("player") || "", match: qs.get("match"), speed: +(qs.get("speed") || 30),
           replay: null, es: null, meta: null, recent: [], momentum: [],
           audio: qs.get("audio") === "1", a11y: qs.get("a11y") === "1", approval: qs.get("approval") === "1", vstats: {checked: 0, rejected: 0}};
const t = (k) => (I18N[S.lang][k] ?? I18N.en[k] ?? k);

function applyLang() {
  document.documentElement.lang = S.lang;
  document.documentElement.dir = S.lang === "ar" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  if (S.replay) $("startBtn").textContent = t("restart");
  if (S.meta) { $("hintHome").textContent = `${S.meta.home.code} ${t("attacks")}`; $("hintAway").textContent = `${S.meta.away.code} ${t("attacks")}`; }
}
function seg(id, key) {
  const el = $(id);
  el.querySelectorAll("button").forEach((b) => {
    b.classList.toggle("on", b.dataset.v === S[key]);
    b.onclick = () => { S[key] = b.dataset.v; seg(id, key); if (key === "lang") applyLang(); reconnect(); };
  });
}
async function api(path, opts) { const r = await fetch(path, opts); if (!r.ok) throw new Error(await r.text()); return r.json(); }

async function loadMatches() {
  const ms = await api("/api/matches");
  $("matchSel").innerHTML = ms.map((m) => `<option value="${m.match_id}">${m.home} v ${m.away}</option>`).join("");
  if (S.match) $("matchSel").value = S.match;
  S.match = $("matchSel").value;
  await loadMeta();
}
async function loadMeta() {
  S.meta = await api(`/api/matches/${S.match}/meta`);
  const m = S.meta;
  $("homeName").textContent = m.home.name; $("awayName").textContent = m.away.name;
  $("clubSel").innerHTML = `<option value="">${t("none")}</option><option value="home">${m.home.name}</option><option value="away">${m.away.name}</option>`;
  $("clubSel").value = S.club;
  const grp = (side) => `<optgroup label="${m[side].name}">` + m[side].lineup.map((p) =>
    `<option value="${p.player_id}">${p.number}. ${p.name} (${p.position})</option>`).join("") + "</optgroup>";
  $("playerSel").innerHTML = `<option value="">${t("none")}</option>` + grp("home") + grp("away");
  $("playerSel").value = S.player;
  applyLang();
}
function resetView() {
  ["ticker", "cards", "dots", "trails", "overlays"].forEach((id) => ($(id).innerHTML = ""));
  $("homeScore").textContent = "0"; $("awayScore").textContent = "0"; $("clock").textContent = "0'";
  S.recent = []; $("recap").classList.add("hidden");
}
async function start(startMinute = +(qs.get("start") || 0)) {
  if (S.es) S.es.close();
  resetView();
  S.match = $("matchSel").value; S.speed = +$("speedSel").value;
  const r = await api("/api/replays", {method: "POST", headers: {"content-type": "application/json"},
    body: JSON.stringify({match_id: S.match, speed: S.speed, start_minute: startMinute})});
  S.replay = r.replay_id; S.llmOff = false; $("prodQueue").innerHTML = ""; prodPanel(); $("startBtn").textContent = t("restart");
  connect(false);
}
function reconnect(keepFeed) { if (S.replay) { if (S.es) S.es.close(); if (!keepFeed) ["ticker", "cards", "overlays"].forEach((id) => ($(id).innerHTML = "")); connect(true); } }
function connect(fromNow) {
  const p = new URLSearchParams({persona: S.persona, lang: S.lang, from_now: fromNow, approval: S.approval});
  $("auditLink").href = `/api/replays/${S.replay}/audit`;
  if (S.club) p.set("club", S.club); if (S.player) p.set("player", S.player);
  const es = new EventSource(`/api/replays/${S.replay}/stream?${p}`); S.es = es;
  const on = (name, fn) => es.addEventListener(name, (ev) => fn(JSON.parse(ev.data)));
  on("notice", (d) => { if (d.llm === "offline") S.llmOff = "limit"; prodPanel(); });
  on("meta", (d) => { if (d.llm_mode !== "foundry" && !S.llmOff) S.llmOff = "noai"; prodPanel(); const b = $("modeBadge"); b.textContent = d.llm_mode === "foundry" ? "Azure AI Foundry" : "offline agents"; b.classList.toggle("foundry", d.llm_mode === "foundry"); });
  on("match_event", drawEvent); on("commentary", addLine); on("moment_card", addCard);
  on("commentary_update", (u) => (u.pending ? pendingLine(u) : applyUpdate(u))); on("overlay", showOverlay);
  on("verifier", (v) => { S.vstats = v; vchip(); });
  on("stats", updateStats); on("agent_trace", trace); on("recap", showRecap);
  on("end", () => es.close());
}

// ---------------------------------------------------------------- pitch
const NS = "http://www.w3.org/2000/svg";
function svg(tag, attrs, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); parent.appendChild(e); return e; }
function drawEvent(e) {
  $("clock").textContent = clockOf(e);
  const g = svg("g", {}, $("dots"));
  if (e.end_x != null && (e.type === "pass" || e.type === "carry"))
    svg("line", {x1: e.x, y1: e.y, x2: e.end_x, y2: e.end_y, class: `trail ${e.team}`, "stroke-dasharray": e.type === "carry" ? "1 .7" : ""}, g);
  if (e.type === "shot") svg("line", {x1: e.x, y1: e.y, x2: e.end_x, y2: e.end_y, class: "shotline"}, g);
  const r = e.type === "shot" ? 1.3 : e.type === "goal" ? 1.8 : 0.85;
  svg("circle", {cx: e.x, cy: e.y, r, class: `ev ${e.team}`}, g);
  if (e.type === "goal") { svg("circle", {cx: e.x, cy: e.y, r: 2, class: "pulse"}, g); const s = document.querySelector(".score"); s.classList.remove("flash"); void s.offsetWidth; s.classList.add("flash");
    $(e.team === "home" ? "homeScore" : "awayScore").textContent = +$(e.team === "home" ? "homeScore" : "awayScore").textContent + 1; }
  const bx = e.end_x ?? e.x, by = e.end_y ?? e.y;
  let ball = document.querySelector("#pitch .ball"); if (!ball) ball = svg("circle", {r: 0.9, class: "ball"}, $("pitch"));
  ball.setAttribute("cx", bx); ball.setAttribute("cy", by);
  S.recent.push(g);
  while (S.recent.length > 28) S.recent.shift().remove();
  S.recent.forEach((n, i) => (n.style.opacity = (0.15 + (0.85 * (i + 1)) / S.recent.length).toFixed(2)));
}
function clockOf(e) { const m = e.minute; if (e.period === 1 && m >= 45) return `45+${m - 44}'`; if (e.period === 2 && m >= 90) return `90+${m - 89}'`; return `${m + 1}'`; }

// ---------------------------------------------------------------- feed
function evHtml(ev) {
  if (!ev || !ev.length) return "";
  return `<span class="ev-list">${t("evidence")}: ` + ev.map((x, i) => `<span class="fn"><sup>${i + 1}</sup><bdi>${esc(x.claim)}</bdi> ← <code>${esc(x.fact)}</code></span>`).join(" ") + "</span>";
}
function vbadge(d) {
  if (d.verified === undefined) return "";
  const tip = (d.evidence || []).map((x) => `${x.claim} ← ${x.fact} (${x.how})`).join("\n");
  return `<button class="vbadge ${d.verified ? "ok" : "bad"}" title="${esc(tip)}" aria-label="${t("verified")}: ${esc(tip)}">🛡 ${d.verified ? t("verified") : "!"} ${(d.evidence || []).length ? `<sup>${d.evidence.length}</sup>` : ""}</button>`;
}
function addLine(d) {
  const li = document.createElement("li");
  li.className = `${d.team || ""} ${d.important ? "big" : ""}`; li.dataset.id = d.id || "";
  li.innerHTML = `<span class="c">${d.clock}</span><span><span class="txt">${bidi(d.text)}</span><span class="src">${d.source}</span>${vbadge(d)}<div class="evd hidden">${evHtml(d.evidence)}</div></span>`;
  wireBadge(li);
  $("ticker").prepend(li);
  while ($("ticker").children.length > 40) $("ticker").lastChild.remove();
  S.vstats.checked += 1; vchip();
  if (S.a11y || S.audio) say(d.text, d.id);
}
function wireBadge(li) { const b = li.querySelector(".vbadge"); if (b) b.onclick = () => li.querySelector(".evd").classList.toggle("hidden"); }
function applyUpdate(u) {
  const li = document.querySelector(`#ticker li[data-id="${u.id}"]`); if (!li) return;
  const tx = li.querySelector(".txt"); tx.classList.add("swap");
  setTimeout(() => {
    tx.innerHTML = bidi(u.text); li.querySelector(".src").textContent = u.source; tx.classList.remove("swap"); li.classList.add("upgraded");
    const old = li.querySelector(".vbadge"); if (old) old.outerHTML = vbadge(u); li.querySelector(".evd").innerHTML = evHtml(u.evidence); wireBadge(li);
    S.vstats.checked += 1; vchip();
    if (S.audio || S.a11y) say(u.text, u.id, true);
  }, 220);
}
function pendingLine(u) { holdBox(u.id, u.clock || "", u.text, () => applyUpdate({...u, pending: false})); }
function prodPanel() {
  const n = $("notice"); n.classList.toggle("hidden", !S.approval); if (!S.approval) return;
  const held = $("prodQueue").children.length;
  $("prodMsg").textContent = S.llmOff === "limit" ? t("prodOff") : S.llmOff ? t("prodNoAI") : !S.replay ? `${t("prodOn")} ${t("prodIdle")}` : `${t("prodOn")}${held ? "" : " " + t("prodWait")}`;
}
function holdBox(ref, label, text, onApprove) {
  const box = document.createElement("div"); box.className = "pending"; box.dataset.ref = ref;
  box.innerHTML = `<div class="pl">🎬 ${t("pending")} · ${esc(label)}</div><div class="pt">${bidi(text)}</div>
    <button class="ap">✓ ${t("approve")}</button><button class="rj">✕ ${t("reject")}</button>`;
  const send = (decision) => fetch(`/api/replays/${S.replay}/decisions`, {method: "POST", headers: {"content-type": "application/json"},
    body: JSON.stringify({ref, decision, text})});
  box.querySelector(".ap").onclick = () => { send("approve"); box.remove(); onApprove(); prodPanel(); };
  box.querySelector(".rj").onclick = () => { send("reject"); box.remove(); prodPanel(); };
  $("prodQueue").prepend(box); prodPanel();
}
function vchip() { $("verChip").textContent = `🛡 ${S.vstats.checked}${S.vstats.rejected ? ` · ✕ ${S.vstats.rejected}` : ""}`; }

// ---------------------------------------------------------------- speech (Azure AI Speech, browser fallback)
const VOICE_LANG = {en: "en-GB", ar: "ar-SA", es: "es-ES", fr: "fr-FR", pt: "pt-BR"};
const SQ = {queue: [], busy: false, audio: new Audio(), spoken: new Set(), engine: null};
function say(text, id, isUpdate) {
  if (id && SQ.spoken.has(id) && !isUpdate) return;
  if (isUpdate) { const q = SQ.queue.find((x) => x.id === id); if (q) { q.text = text; q.req = ttsFetch(q); return; } if (SQ.spoken.has(id)) return; }
  if (SQ.queue.length > 3) SQ.queue.splice(0, SQ.queue.length - 3); // keep up with the live match
  const it = {text, id, lang: S.lang}; it.req = ttsFetch(it); SQ.queue.push(it); pump();
}
function ttsFetch(it) {  // fetched as soon as queued, so the next line is ready when the current one ends
  it.sent = it.text;
  return fetch("/api/tts", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({text: it.text.slice(0, 400), lang: it.lang, voice: qs.get("voice") || undefined})});
}
async function pump() {
  if (SQ.busy || SQ.priority || !SQ.queue.length) return;
  SQ.busy = true; const it = SQ.queue.shift(); if (it.id) SQ.spoken.add(it.id); const gen = SQ.gen;
  $("srLive").textContent = it.text;
  try {
    const r = await (it.req && it.sent === it.text ? it.req : ttsFetch(it));
    if (!r.ok) throw new Error(r.status);
    if (gen !== SQ.gen) throw new Error("stopped");  // a toggle interrupted us while the clip was downloading
    SQ.engine = "azure";
    await playBlob(await r.blob());
  } catch (e) {
    SQ.engine = "browser";
    if (e.message !== "stopped" && window.speechSynthesis) await new Promise((res) => { SQ.stop = res; const u = new SpeechSynthesisUtterance(it.text); u.lang = VOICE_LANG[it.lang]; u.onend = res; u.onerror = res; speechSynthesis.speak(u); setTimeout(res, 20000); });
  }
  SQ.stop = null; SQ.busy = false; pump();
}
// Play one mp3. Always settles: on end, on error, when stopped by a toggle, or after a safety timeout,
// so the queue can never hang (before, pausing mid-line left the queue busy forever = permanent silence).
function playBlob(blob) {
  return new Promise((res, rej) => {
    const done = (err) => { clearTimeout(tm); SQ.audio.onended = SQ.audio.onerror = null; SQ.stop = null; err ? rej(err) : res(); };
    const tm = setTimeout(() => done(), 30000);
    SQ.stop = () => done(new Error("stopped"));
    SQ.audio.onended = () => done(); SQ.audio.onerror = () => done(new Error("media"));
    SQ.audio.src = URL.createObjectURL(blob);
    SQ.audio.play().catch((e) => done(e));
  });
}
function stopSpeech() {
  SQ.gen = (SQ.gen || 0) + 1; SQ.queue = []; SQ.priority = false; try { SQ.audio.pause(); } catch (e) { /* ignore */ }
  try { window.speechSynthesis?.cancel(); } catch (e) { /* ignore */ }
  if (SQ.stop) SQ.stop();
}
// Speak right now (button feedback): interrupt whatever is playing and jump the queue.
// The confirmation clip is pre-fetched per language, so it starts inside the click itself.
const CONF = {};
function prefetchConfirm() {
  ["audioOn", "a11yOn"].forEach((k) => { const key = S.lang + k; if (CONF[key]) return;
    CONF[key] = {text: t(k), blob: null}; fetch("/api/tts", {method: "POST", headers: {"content-type": "application/json"},
      body: JSON.stringify({text: t(k), lang: S.lang, voice: qs.get("voice") || undefined})}).then((r) => (r.ok ? r.blob() : null)).then((b) => { CONF[key].blob = b; }).catch(() => {}); });
}
function sayNow(k) {
  stopSpeech(); SQ.unlocked = true;
  const c = CONF[S.lang + k], text = t(k);
  $("srLive").textContent = text;
  if (c && c.blob) { SQ.priority = true; const g = SQ.gen; playBlob(c.blob).catch((e) => e.message !== "stopped" && browserSay(text)).finally(() => { if (g === SQ.gen) { SQ.priority = false; pump(); } }); return; }
  unlockAudio(true); browserSay(text);
}
function browserSay(text) { try { if (!window.speechSynthesis) return; const u = new SpeechSynthesisUtterance(text); u.lang = VOICE_LANG[S.lang]; speechSynthesis.speak(u); } catch (e) { /* ignore */ } }
// Browsers only allow sound after a user gesture: unlock the shared <audio> element (and speechSynthesis)
// inside the click on 🔊 / ♿ / Kick off, so later commentary can play without another tap.
const SILENT = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=";
function unlockAudio(force) {
  if (SQ.unlocked && !force) return; SQ.unlocked = true;
  try { SQ.audio.muted = false; SQ.audio.src = SILENT; const pr = SQ.audio.play(); if (pr) pr.catch(() => { SQ.unlocked = false; }); } catch (e) { SQ.unlocked = false; }
  try { if (window.speechSynthesis) speechSynthesis.speak(new SpeechSynthesisUtterance(" ")); } catch (e) { /* ignore */ }
}
function setTog(id, on) { $(id).classList.toggle("on", on); $(id).setAttribute("aria-pressed", on); }
function a11yMode(on) { S.a11y = on; document.body.classList.toggle("a11y", on); setTog("a11yBtn", on); $("ticker").setAttribute("aria-live", on ? "polite" : "off");
  $("a11yBanner").textContent = t("a11yOn"); $("a11yBanner").classList.toggle("hidden", !on);
  if (on) sayNow("a11yOn"); else if (!S.audio) stopSpeech(); }
function addCard(c) {
  if (c.pending) { holdBox(c.moment_id, `${c.title} ${c.player || ""}`, c.why, () => addCard({...c, pending: false})); return; }
  if (!c.update && (S.a11y || S.audio)) say(`${c.title}. ${c.player || ""}. ${c.why}`, c.moment_id);
  const old = document.querySelector(`#cards .card[data-id="${c.moment_id}"]`);
  const div = old || document.createElement("div");
  div.className = `card ${c.team || ""}`; div.dataset.id = c.moment_id;
  const name = c.team ? S.meta[c.team].code : "";
  div.innerHTML = `<div class="h"><span class="k">${esc(c.title)} · ${name}</span><span class="cl">${c.clock}</span></div>
    <div><b>${esc(c.player || "")}</b> ${vbadge(c)}</div><p>${esc(c.why)}</p><div class="evd hidden">${evHtml(c.evidence)}</div><div class="imp"><i style="width:${Math.round((c.importance || 0) * 100)}%"></i></div>`;
  wireBadge(div);
  if (!old) $("cards").prepend(div);
}
function bidi(s) { return esc(s).replace(/[A-Za-z0-9][A-Za-z0-9 .'\-]*[A-Za-z0-9]|[A-Za-z]/g, (m) => `<bdi>${m}</bdi>`); }
function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c])); }

// ---------------------------------------------------------------- overlays (timed, machine-readable cards)
function showOverlay(o) {
  const div = document.createElement("div");
  div.className = `ov ${o.anchor}`; div.dataset.kind = o.kind;
  const p = o.payload;
  if (o.kind === "goal_banner") div.textContent = `${t("goal")} ${p.player} · ${p.score.home}-${p.score.away}`;
  else if (o.kind === "shot_xg") div.innerHTML = `${esc(p.player)}<br><b>${p.xg.toFixed(2)} xG</b> · ${Math.round(p.speed_kmh)} ${t("speedAlert")}`;
  else if (o.kind === "pass_difficulty") div.innerHTML = `${esc(p.player)}<br>${t("difficulty")} <b>${p.difficulty}</b>/100 · ${p.length_m}m`;
  else if (o.kind === "stat_bar") div.innerHTML = `<div class="t">${t("possession")} ${p.possession.home}% – ${p.possession.away}% · xG ${p.xg.home} – ${p.xg.away} · ${t("shots")} ${p.shots.home} – ${p.shots.away}</div>`;
  else if (o.kind === "moment_card") div.innerHTML = `<div class="t">${esc(p.title)}</div>${esc(p.text)}`;
  else if (o.kind === "player_tag" || o.kind === "speed_alert") {
    const pt = o.kind === "player_tag" ? p : p; div.className = "ov pitch";
    div.textContent = o.kind === "speed_alert" ? `⚡ ${p.player} ${Math.round(p.speed_kmh)} ${t("speedAlert")}` : `★ ${p.player}`;
    const last = S.recent[S.recent.length - 1]?.querySelector("circle");
    const x = p.x ?? (last ? +last.getAttribute("cx") : 52), y = p.y ?? (last ? +last.getAttribute("cy") : 34);
    div.style.left = `${((x + 2) / 109) * 100}%`; div.style.top = `${((y + 2) / 72) * 100}%`;
  } else return;
  if (o.anchor !== "pitch") document.querySelectorAll(`#overlays .ov.${o.anchor}`).forEach((n) => n.remove());
  $("overlays").appendChild(div);
  const ms = Math.max(2500, (o.duration_s / S.speed) * 1000 * 4);
  setTimeout(() => div.remove(), Math.min(ms, 9000));
}

// ---------------------------------------------------------------- stats + momentum
function updateStats(s) {
  $("homeScore").textContent = s.score.home; $("awayScore").textContent = s.score.away;
  if (s.events_processed) $("clock").textContent = s.clock;
  const ph = s.possession_pct.home, pa = s.possession_pct.away;
  $("posH").textContent = `${ph}%`; $("posA").textContent = `${pa}%`; $("posBar").style.width = `${ph}%`;
  $("xgH").textContent = s.xg.home.toFixed(2); $("xgA").textContent = s.xg.away.toFixed(2);
  $("shH").textContent = s.shots.home; $("shA").textContent = s.shots.away;
  $("sotH").textContent = s.shots_on_target.home; $("sotA").textContent = s.shots_on_target.away;
  $("pcH").textContent = `${Math.round(s.passing.home.completion_pct)}%`; $("pcA").textContent = `${Math.round(s.passing.away.completion_pct)}%`;
  if (s.phase) { $("phaseChip").textContent = t(s.phase); $("phaseChip").className = `chip ${s.phase}`; }
  if (s.rhythm) $("rhythmChip").textContent = t(s.rhythm);
  $("momNow").textContent = s.momentum_now > 0.15 ? `▲ ${S.meta.home.code}` : s.momentum_now < -0.15 ? `▲ ${S.meta.away.code}` : "=";
  drawMomentum(s.momentum || []);
}
function drawMomentum(series) {
  // x uses the monotonic timeline index `t` (first-half stoppage never overlaps the second half)
  const tMax = Math.max(98, ...series.map((r) => r.t ?? r.minute)), W = 400, H = 80, mid = H / 2, X = (m) => (m / tMax) * W;
  const ht = series.find((r) => r.period === 2);
  let ph = `M0,${mid}`, pa = `M0,${mid}`;
  series.forEach((r) => { const x = X(r.t ?? r.minute), y = r.momentum * (mid - 4); ph += ` L${x},${mid - Math.max(y, 0)}`; pa += ` L${x},${mid - Math.min(y, 0)}`; });
  const end = series.length ? X(series[series.length - 1].t ?? series[series.length - 1].minute) : 0;
  $("momH").setAttribute("d", ph + ` L${end},${mid} Z`); $("momA").setAttribute("d", pa + ` L${end},${mid} Z`);
  const hx = X(ht ? ht.t : 46); $("htLine").setAttribute("x1", hx); $("htLine").setAttribute("x2", hx);
}
function trace(r) {
  const el = $(`ag-${r.agent}`);
  if (el) { el.className = `agent ${r.status} active`; setTimeout(() => el.classList.remove("active"), 600); }
  if (r.agent === "verifier" && r.status !== "ok") { S.vstats.rejected += r.status === "rejected" ? 1 : 0; vchip(); }
  $("trace").textContent = `${r.clock || ""} ${r.agent}.${r.task} → ${r.status}${r.attempts > 1 ? ` (${r.attempts} attempts)` : ""} · ${r.source || ""} · ${r.latency_ms ?? ""}ms`;
}
function showRecap(r) {
  $("recapScore").textContent = `${S.meta.home.name} ${r.score.home} – ${r.score.away} ${S.meta.away.name}`;
  $("recapText").textContent = r.text;
  $("recapMoments").innerHTML = r.moments.map((m) => `<span>${m.clock} ${esc(m.title)} ${esc(m.player || "")}</span>`).join("")
    + (r.player_of_match ? `<span>★ ${t("potm")}: ${esc(r.player_of_match.player)}</span>` : "");
  if (r.verifier) $("recapMoments").innerHTML += `<span>🛡 Verifier: ${r.verifier.checked} checked · ${r.verifier.rejected} rejected · ${r.verifier.fallbacks} kept template</span>`;
  $("recap").classList.remove("hidden");
  if (S.audio || S.a11y) say(r.text, "recap");
}

// ---------------------------------------------------------------- wiring
$("matchSel").onchange = async () => { S.match = $("matchSel").value; S.player = ""; S.club = ""; await loadMeta(); };
$("speedSel").value = String(S.speed);
$("speedSel").onchange = () => { if (S.replay) { const m = parseInt($("clock").textContent) || 0; start(Math.max(0, m - 1)); } };
$("clubSel").onchange = () => { S.club = $("clubSel").value; reconnect(); };
$("playerSel").onchange = () => { S.player = $("playerSel").value; reconnect(); };
$("startBtn").onclick = () => { if (S.audio || S.a11y) unlockAudio(); start(0); };
$("recapClose").onclick = () => $("recap").classList.add("hidden");
(() => { const g = document.querySelector(".stripes"); for (let i = 0; i < 105; i += 15) svg("rect", {x: i, y: 0, width: 7.5, height: 68}, g); })();
seg("personaSeg", "persona");
if (!I18N[S.lang]) S.lang = "en";
$("langSel").value = S.lang;
$("langSel").onchange = (e) => { S.lang = e.target.value; applyLang(); prefetchConfirm(); prodPanel(); reconnect(); };
$("audioBtn").onclick = () => { S.audio = !S.audio; setTog("audioBtn", S.audio); if (S.audio) sayNow("audioOn"); else if (!S.a11y) stopSpeech(); };
$("a11yBtn").onclick = () => a11yMode(!S.a11y);
$("approvalBtn").onclick = () => { S.approval = !S.approval; setTog("approvalBtn", S.approval); prodPanel(); reconnect(true); };
setTog("audioBtn", S.audio); setTog("approvalBtn", S.approval); if (S.a11y) a11yMode(true);
document.addEventListener("keydown", (e) => { if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
  if (e.key === "a" || e.key === "A") a11yMode(!S.a11y);
  if (e.key === " " && S.a11y) { e.preventDefault(); start(0); }
  if ((e.key === "s" || e.key === "S") && S.a11y) { const st = `${$("clock").textContent}. ${$("homeName").textContent} ${$("homeScore").textContent}, ${$("awayName").textContent} ${$("awayScore").textContent}.`; say(st); } });
prefetchConfirm(); prodPanel();
loadMatches().then(() => { if (qs.get("autoplay")) start(); });
