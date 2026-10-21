// Echo Pitch UI: vanilla JS, consumes the FastAPI SSE replay stream.
const $ = (id) => document.getElementById(id);
const I18N = {
  en: {tagline:"AI match storyteller", match:"Match", speed:"Speed", fan:"Fan", analyst:"Analyst", club:"Club",
       player:"Player", none:"None", start:"▶ Kick off", restart:"↻ Restart", possession:"Possession", shots:"Shots",
       ontarget:"On target", passes:"Pass %", momentum:"Momentum", commentary:"Live commentary",
       moments:"Key moments · why they matter", agents:"Agents", fulltime:"Full-time recap", close:"Close",
       potm:"Player of the match", controlled:"controlled", contested:"contested", chaotic:"chaotic",
       "fast and direct":"fast & direct", "slow build-up":"slow build-up", steady:"steady", goal:"GOAL!",
       xg:"xG", difficulty:"Pass difficulty", speedAlert:"km/h", attacks:"attacks"},
  ar: {tagline:"راوي المباريات بالذكاء الاصطناعي", match:"المباراة", speed:"السرعة", fan:"مشجّع", analyst:"محلّل",
       club:"النادي", player:"اللاعب", none:"لا شيء", start:"▶ ابدأ", restart:"↻ إعادة", possession:"الاستحواذ",
       shots:"التسديدات", ontarget:"على المرمى", passes:"دقة التمرير", momentum:"الزخم", commentary:"التعليق المباشر",
       moments:"اللحظات الحاسمة · لماذا تهم", agents:"الوكلاء", fulltime:"ملخص المباراة", close:"إغلاق",
       potm:"أفضل لاعب", controlled:"منظّم", contested:"متكافئ", chaotic:"فوضوي", "fast and direct":"سريع ومباشر",
       "slow build-up":"بناء هادئ", steady:"متوازن", goal:"هدف!", xg:"xG", difficulty:"صعوبة التمريرة",
       speedAlert:"كم/س", attacks:"يهاجم"},
};
const qs = new URLSearchParams(location.search);
const S = {persona: qs.get("persona") || "fan", lang: qs.get("lang") || "en", club: qs.get("club") || "",
           player: qs.get("player") || "", match: qs.get("match"), speed: +(qs.get("speed") || 30),
           replay: null, es: null, meta: null, recent: [], momentum: []};
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
  S.replay = r.replay_id; $("startBtn").textContent = t("restart");
  connect(false);
}
function reconnect() { if (S.replay) { if (S.es) S.es.close(); ["ticker", "cards", "overlays"].forEach((id) => ($(id).innerHTML = "")); connect(true); } }
function connect(fromNow) {
  const p = new URLSearchParams({persona: S.persona, lang: S.lang, from_now: fromNow});
  if (S.club) p.set("club", S.club); if (S.player) p.set("player", S.player);
  const es = new EventSource(`/api/replays/${S.replay}/stream?${p}`); S.es = es;
  const on = (name, fn) => es.addEventListener(name, (ev) => fn(JSON.parse(ev.data)));
  on("meta", (d) => { const b = $("modeBadge"); b.textContent = d.llm_mode === "foundry" ? "Azure AI Foundry" : "offline agents"; b.classList.toggle("foundry", d.llm_mode === "foundry"); });
  on("match_event", drawEvent); on("commentary", addLine); on("moment_card", addCard);
  on("commentary_update", (u) => { const li = document.querySelector(`#ticker li[data-id="${u.id}"] .txt`); if (li) { li.textContent = u.text; li.nextSibling.textContent = u.source; } }); on("overlay", showOverlay);
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
function addLine(d) {
  const li = document.createElement("li");
  li.className = `${d.team || ""} ${d.important ? "big" : ""}`; li.dataset.id = d.id || "";
  li.innerHTML = `<span class="c">${d.clock}</span><span><span class="txt">${esc(d.text)}</span><span class="src">${d.source}</span></span>`;
  $("ticker").prepend(li);
  while ($("ticker").children.length > 40) $("ticker").lastChild.remove();
}
function addCard(c) {
  const old = document.querySelector(`#cards .card[data-id="${c.moment_id}"]`);
  const div = old || document.createElement("div");
  div.className = `card ${c.team || ""}`; div.dataset.id = c.moment_id;
  const name = c.team ? S.meta[c.team].code : "";
  div.innerHTML = `<div class="h"><span class="k">${esc(c.title)} · ${name}</span><span class="cl">${c.clock}</span></div>
    <div><b>${esc(c.player || "")}</b></div><p>${esc(c.why)}</p><div class="imp"><i style="width:${Math.round((c.importance || 0) * 100)}%"></i></div>`;
  if (!old) $("cards").prepend(div);
}
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
  $("trace").textContent = `${r.clock || ""} ${r.agent}.${r.task} → ${r.status}${r.attempts > 1 ? ` (${r.attempts} attempts)` : ""} · ${r.source || ""} · ${r.latency_ms ?? ""}ms`;
}
function showRecap(r) {
  $("recapScore").textContent = `${S.meta.home.name} ${r.score.home} – ${r.score.away} ${S.meta.away.name}`;
  $("recapText").textContent = r.text;
  $("recapMoments").innerHTML = r.moments.map((m) => `<span>${m.clock} ${esc(m.title)} ${esc(m.player || "")}</span>`).join("")
    + (r.player_of_match ? `<span>★ ${t("potm")}: ${esc(r.player_of_match.player)}</span>` : "");
  $("recap").classList.remove("hidden");
}

// ---------------------------------------------------------------- wiring
$("matchSel").onchange = async () => { S.match = $("matchSel").value; S.player = ""; S.club = ""; await loadMeta(); };
$("speedSel").value = String(S.speed);
$("speedSel").onchange = () => { if (S.replay) { const m = parseInt($("clock").textContent) || 0; start(Math.max(0, m - 1)); } };
$("clubSel").onchange = () => { S.club = $("clubSel").value; reconnect(); };
$("playerSel").onchange = () => { S.player = $("playerSel").value; reconnect(); };
$("startBtn").onclick = () => start(0);
$("recapClose").onclick = () => $("recap").classList.add("hidden");
(() => { const g = document.querySelector(".stripes"); for (let i = 0; i < 105; i += 15) svg("rect", {x: i, y: 0, width: 7.5, height: 68}, g); })();
seg("personaSeg", "persona"); seg("langSeg", "lang");
loadMatches().then(() => { if (qs.get("autoplay")) start(); });
