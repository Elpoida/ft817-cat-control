"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const MODES = ["LSB", "USB", "CW", "CWR", "AM", "FM", "DIG", "PKT"];
const BANDS = [
  { id: "160", lo: 1810e3, hi: 2000e3, def: 1843000, mode: "LSB" },
  { id: "80", lo: 3500e3, hi: 3800e3, def: 3700000, mode: "LSB" },
  { id: "60", lo: 5351.5e3, hi: 5366.5e3, def: 5354000, mode: "USB" },
  { id: "40", lo: 7000e3, hi: 7200e3, def: 7100000, mode: "LSB" },
  { id: "30", lo: 10100e3, hi: 10150e3, def: 10120000, mode: "CW" },
  { id: "20", lo: 14000e3, hi: 14350e3, def: 14200000, mode: "USB" },
  { id: "17", lo: 18068e3, hi: 18168e3, def: 18130000, mode: "USB" },
  { id: "15", lo: 21000e3, hi: 21450e3, def: 21250000, mode: "USB" },
  { id: "12", lo: 24890e3, hi: 24990e3, def: 24950000, mode: "USB" },
  { id: "10", lo: 28000e3, hi: 29700e3, def: 28500000, mode: "USB" },
  { id: "6", lo: 50000e3, hi: 52000e3, def: 50150000, mode: "USB" },
  { id: "2", lo: 144000e3, hi: 146000e3, def: 145500000, mode: "FM" },
  { id: "70", lo: 430000e3, hi: 440000e3, def: 433500000, mode: "FM" },
];
const STEPS = [10, 50, 100, 500, 1000, 2500, 5000, 6250, 10000, 12500, 25000, 100000];
const STEP_DEFAULT = { ssb: 10, cw: 10, am: 1000, fm: 12500 };
const RX_RANGES = [[100e3, 56e6], [76e6, 154e6], [420e6, 470e6]];

let INFO = null;
let S = { connected: false, ee: {}, written: {}, cfg: {}, stats: {}, cw: {} };
let MEMORIES = [];
let CWCFG = null;
let CURRENT_LANG = localStorage.getItem("ft817.lang") || "en";
let step = 10;
let stepGroup = null;
let pttHeld = false;
let pttLatchOn = false;
let pttBeat = null;
let tuneHeld = false;
let tuneBeat = null;
let swrBeat = null;
let lastTraceN = 0;
let traceTimer = null;
let cwLastJob = -1;
let audioCtx = null;
let audioNodes = [];
let entryOpen = false;
let scopeTimer = null;

const inRx = hz => RX_RANGES.some(([a, b]) => hz >= a && hz <= b);
const bandOf = hz => BANDS.find(b => hz >= b.lo && hz <= b.hi);
const modeGroup = m => ({ LSB: "ssb", USB: "ssb", DIG: "ssb", CW: "cw", CWR: "cw", AM: "am" })[m] || "fm";
const fmtMHz = hz => {
  const s = String(Math.round((hz || 0) / 10)).padStart(6, "0");
  return `${s.slice(0, -5)}.${s.slice(-5, -2)}.${s.slice(-2)}`;
};
const fmtShort = hz => (hz / 1e6).toFixed(6).replace(/0+$/, "").replace(/\.$/, "") + " MHz";
const sLabel = n => (n <= 9 ? `S${n}` : `S9+${(n - 9) * 10}`);
const modeName = () => (S.mode === "FM" && S.narrow ? "FM-N" : (S.mode || "---"));

async function api(path, body) {
  const opt = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  const response = await fetch(path, opt);
  let data;
  try { data = await response.json(); } catch { throw new Error(`HTTP ${response.status}`); }
  if (!data.ok) throw new Error(data.error || "error");
  return data;
}

let lastToast = "";
function toast(message, kind = "") {
  if (!message || (message === lastToast && Date.now() - lastToast < 900)) return;
  lastToast = message;
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = message;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), kind === "err" ? 6000 : 3200);
  while ($("#toasts").children.length > 4) $("#toasts").firstChild.remove();
}

function cmd(op, args = {}) {
  return api("/api/cmd", { op, ...args }).catch(err => { toast(err.message, "err"); throw err; });
}

function latestSender(fn) {
  let pending = null, busy = false;
  const send = async value => {
    pending = value;
    if (busy) return;
    busy = true;
    while (pending !== null) {
      const current = pending;
      pending = null;
      try { await fn(current); } catch { /* reported */ }
    }
    busy = false;
  };
  send.idle = () => !busy;
  return send;
}

function setText(el, text) { if (el && el.textContent !== text) el.textContent = text; }
function toggle(el, cls, on) { if (el) el.classList.toggle(cls, !!on); }

function fillToneValues() {
  const toneVal = $("#toneVal");
  const mode = $("#toneMode").value;
  const current = toneVal.value;
  toneVal.innerHTML = "";
  if (mode === "DCS") {
    for (const code of INFO.dcs) toneVal.add(new Option(`DCS ${String(code).padStart(3, "0")}`, `D${code}`));
  } else {
    for (const tone of INFO.ctcss) toneVal.add(new Option(tone.toFixed(1), String(tone)));
  }
  if ([...toneVal.options].some(option => option.value === current)) toneVal.value = current;
}

function initSelects() {
  fillToneValues();
  const modeRow = $("#modeRow");
  modeRow.innerHTML = "";
  for (const mode of MODES) {
    const button = document.createElement("button");
    button.className = "btn";
    button.textContent = mode;
    button.dataset.mode = mode;
    button.onclick = () => cmd("mode", { mode }).catch(() => {});
    modeRow.append(button);
  }
  const bandGrid = $("#bandGrid");
  bandGrid.innerHTML = "";
  for (const band of BANDS) {
    const button = document.createElement("button");
    button.className = "btn";
    button.textContent = band.id === "70" ? "70cm" : band.id === "2" ? "2m" : band.id === "6" ? "6m" : `${band.id}m`;
    button.dataset.band = band.id;
    button.onclick = () => gotoBand(band);
    bandGrid.append(button);
  }
  $("#scopeSpan").value = "25";
  $("#swrSpan").value = "25";
}

function gotoBand(band) {
  if (band.id === "60" && S.model !== "818") { toast("60 m: FT-818 only"); return; }
  if (Math.abs((S.freq || 0) - band.def) < 5000) {
    cmd("mode", { mode: band.mode }).catch(() => {});
  } else {
    setFreq(band.def, band.mode);
  }
}

const setFreqLatest = latestSender(async hz => {
  if (!inRx(hz)) { toast(t("invalidFreq"), "err"); return; }
  await cmd("freq", { hz, seq: Date.now() });
});

function setFreq(hz, mode) {
  if (!S.connected) { toast(t("connectFirst"), "err"); return; }
  hz = Math.round(hz / 10) * 10;
  S.freq = hz;
  renderFreq();
  setFreqLatest(hz);
  if (mode) cmd("mode", { mode }).catch(() => {});
}

function renderFreq() {
  const text = fmtMHz(S.freq || 0);
  const [mhz, khz, hz] = text.split(".");
  $("#freq").innerHTML = `${mhz}<span class="dim">.</span>${khz}<span class="dim">.</span>${hz}`;
  $("#stepText").textContent = step >= 1000 ? `${step / 1000} kHz` : `${step} Hz`;
  $("#knobStep").textContent = step >= 1000 ? `${step / 1000} kHz` : `${step} Hz`;
}

function setStep(value) {
  step = value;
  renderFreq();
}

function renderTop() {
  const pill = $("#connPill");
  toggle(pill, "on", S.connected);
  setText($("#connText"), S.connected ? (S.description || t("connected")) : t("disconnected"));
  setText($("#modelBadge"), S.model ? `${S.model === "818" ? "FT-818ND" : "FT-817ND"}${S.model_sure ? "" : " ?"}` : "--");
}

function renderDisplay() {
  const mode = modeName();
  setText($("#lcdMode"), mode);
  setText($("#lcdBand"), S.band ? `${S.band} m` : "");
  setText($("#lcdTag"), memoryAt(S.freq, S.mode)?.name || "");
  const icons = {
    vfoa: S.ee?.vfo === "A", vfob: S.ee?.vfo === "B", split: !!S.written?.split,
    clar: !!S.written?.clar_on, lock: !!S.written?.lock, ipo: S.ee?.ipo === "ON",
    att: S.ee?.att === "ON", nb: S.ee?.nb === "ON", agc: S.ee?.agc && S.ee.agc !== "AUTO",
    ant: S.ee?.ant === "REAR", tone: (S.written?.tone_mode || "OFF") !== "OFF",
    shift: (S.written?.rpt || "S") !== "S", busy: !S.squelched && S.s > 1 && !S.tx,
    tx: !!S.tx,
  };
  for (const [key, on] of Object.entries(icons)) toggle($(`[data-ic="${key}"]`), "on", on);
  renderFreq();
  const sub = [];
  if (S.ptt_cat) sub.push(`TX ${S.ptt_left ?? ""}s`);
  if (S.ptt_alarm) sub.push(S.ptt_alarm);
  if (S.error) sub.push(S.error);
  if (S.tune) sub.push(`TUNE ${S.tune.phase || ""}`);
  if (S.memread?.running) sub.push(`mem ${S.memread.pos}/${S.memread.total}`);
  if (!sub.length && S.connected) sub.push(`${S.cfg?.sim ? "SIM" : S.cfg?.port || ""} ${S.cfg?.baud || ""} 8N${S.cfg?.stopbits || 2} | ${S.stats?.rate || 0}/s`);
  setText($("#lcdSub"), sub.join(" | ") || "\u00a0");

  const tx = !!S.tx;
  const meterLabel = tx ? (S.ee?.mtr || "PWR") : "S";
  setText($("#meterLabel"), meterLabel);
  let value, label;
  if (tx) {
    const meter = S.tm || {};
    value = S.ee?.mtr === "SWR" ? (meter.swr ?? S.tx_bars) : (S.ee?.mtr === "ALC" ? meter.alc : S.ee?.mtr === "MOD" ? meter.mod : meter.pwr);
    value = Number(value || 0);
    label = S.ee?.mtr === "SWR" ? (meter.ratio ? meter.ratio.toFixed(1) : String(value)) : `${value}/15`;
    if (S.hi_swr) label += " HI SWR";
  } else {
    value = Number(S.s || 0);
    label = sLabel(value);
  }
  $("#meterFill").style.width = `${Math.max(0, Math.min(100, value / 15 * 100))}%`;
  setText($("#meterRead"), label);

  toggle($("#btnSplit"), "on", !!S.written?.split);
  toggle($("#btnLock"), "on", !!S.written?.lock);
  toggle($("#btnClar"), "on", !!S.written?.clar_on);
  toggle($("#btnTone"), "on", (S.written?.tone_mode || "OFF") !== "OFF");
  toggle($("#ptt"), "active", !!S.ptt_cat || pttLatchOn);
  toggle($("#pttLatch"), "on", pttLatchOn);
  toggle($("#btnPower"), "active", !!S.radio);
  $("#pttInfo").textContent = S.ptt_cat
    ? `${t("tx")} ${S.ptt_left ?? ""}s | ${S.cfg?.ptt?.toUpperCase() || "CAT"}`
    : (S.ptt_alarm || (S.connected ? `${t("rx")} | ${S.cfg?.ptt?.toUpperCase() || "CAT"}` : ""));
  const m = memoryAt(S.freq, S.mode);
  if (m) setText($("#lcdTag"), m.name || "");

  setText($("#stFreq"), fmtShort(S.freq || 0));
  setText($("#stMode"), mode);
  setText($("#stBand"), S.band ? `${S.band} m` : "--");
  setText($("#stS"), sLabel(Number(S.s || 0)));
  setText($("#stTx"), S.tx ? (S.tm ? `PWR ${S.tm.pwr} ALC ${S.tm.alc} SWR ${S.tm.ratio}` : `bars ${S.tx_bars}`) : "--");
  setText($("#stEe"), S.ee_ok === false ? "error" : (S.ee_ok ? "ok" : "--"));
  setText($("#stRate"), `${S.stats?.rate ?? 0}/s`);
  $("#meter").style.opacity = S.connected ? "1" : ".35";
  setText($("#catStats"), `timeouts ${S.stats?.timeouts ?? 0} | errors ${S.stats?.errors ?? 0}`);
}

function memoryAt(hz, mode) {
  if (!hz) return null;
  return MEMORIES.find(m => Math.abs((m.f || 0) - hz) <= 10 && (m.m === mode || m.m === modeName()));
}

const EXTRA_EE = {
  ipo: { values: ["OFF", "ON"], writable: true },
  att: { values: ["OFF", "ON"], writable: true },
  nar: { values: ["OFF", "ON"], writable: true },
  ant: { values: null, writable: true },
};

function buildEe() {
  const quick = ["agc", "nb", "mtr", "pwr", "ipo", "att", "nar", "ant"];
  const full = ["agc", "nb", "mtr", "pwr", "ipo", "att", "nar", "ant", "dig", "bk", "kyr", "vox", "split"];
  const make = (name, container) => {
    const spec = INFO.ee_fields[name] || EXTRA_EE[name];
    if (!spec) return;
    const values = spec.values || INFO.ant_values;
    const wrap = document.createElement("div");
    wrap.className = "ee-item" + (spec.writable ? "" : " readonly");
    const label = document.createElement("label");
    label.textContent = name.toUpperCase();
    const select = document.createElement("select");
    select.dataset.ee = name;
    for (const value of values) select.add(new Option(value, value));
    select.disabled = !spec.writable;
    select.onchange = async () => {
      try {
        await cmd("ee_set", { name, value: select.value });
        toast(`${name.toUpperCase()} = ${select.value}`);
      } catch { renderEe(); }
    };
    wrap.append(label, select);
    container.append(wrap);
  };
  const quickBox = $("#eeQuick");
  const fullBox = $("#eeFull");
  quickBox.innerHTML = "";
  fullBox.innerHTML = "";
  for (const name of quick) make(name, quickBox);
  for (const name of full) make(name, fullBox);
}

function renderEe() {
  for (const select of $$("[data-ee]")) {
    const name = select.dataset.ee;
    if (document.activeElement !== select && S.ee && S.ee[name] != null) select.value = S.ee[name];
  }
  const toneMode = $("#toneMode");
  const wanted = S.written?.tone_mode || "OFF";
  if (document.activeElement !== toneMode && toneMode.value !== wanted) {
    toneMode.value = wanted;
    fillToneValues();
  }
  const toneVal = $("#toneVal");
  if (document.activeElement !== toneVal) {
    if (wanted === "DCS" && S.written?.dcs) toneVal.value = `D${S.written.dcs[0]}`;
    else if (S.written?.ctcss) toneVal.value = String(S.written.ctcss[0]);
  }
}

function renderButtons() {
  for (const button of $$("#modeRow .btn")) toggle(button, "active", button.dataset.mode === S.mode);
  for (const button of $$("#bandGrid .btn")) toggle(button, "active", button.dataset.band === S.band);
}

function renderScope() {
  const canvas = $("#scopeCanvas");
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#081013";
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "#1d3038";
  ctx.lineWidth = 1;
  for (let i = 1; i < 5; i++) {
    ctx.beginPath(); ctx.moveTo(0, h * i / 5); ctx.lineTo(w, h * i / 5); ctx.stroke();
  }
  const scope = S.scope;
  if (!scope?.values?.length) {
    ctx.fillStyle = "#5b7280";
    ctx.font = "13px sans-serif";
    ctx.fillText(t("start"), 16, 24);
    setText($("#scopeInfo"), "");
    return;
  }
  const values = scope.values;
  ctx.strokeStyle = "#46c8a6";
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = values.length === 1 ? w / 2 : index / (values.length - 1) * w;
    const y = h - 8 - (value / 15) * (h - 20);
    if (index) ctx.lineTo(x, y); else ctx.moveTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = "#8aa0a7";
  ctx.font = "11px monospace";
  ctx.fillText(`${(scope.center - scope.span) / 1e6} MHz`, 6, h - 4);
  ctx.fillText(`${(scope.center + scope.span) / 1e6} MHz`, w - 92, h - 4);
  ctx.fillText(`${scope.center / 1e6}`, w / 2 - 22, 13);
  setText($("#scopeInfo"), scope.running ? `${scope.pos}/${scope.points}` : `${scope.points} pts`);
}

function renderSwr() {
  const canvas = $("#swrCanvas");
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#081013";
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "#1d3038";
  for (let i = 1; i < 4; i++) {
    ctx.beginPath(); ctx.moveTo(0, h * i / 4); ctx.lineTo(w, h * i / 4); ctx.stroke();
  }
  const swr = S.swr;
  if (!swr?.values?.length) {
    ctx.fillStyle = "#5b7280";
    ctx.font = "13px sans-serif";
    ctx.fillText(t("measure"), 16, 24);
    setText($("#swrInfo"), "");
    setText($("#swrText"), "");
    return;
  }
  const values = swr.values.filter(Boolean);
  let best = null;
  ctx.strokeStyle = "#f0a23b";
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((item, index) => {
    const ratio = item.swr ?? (item.bars ? item.bars / 4 : 0);
    if (!ratio) return;
    const x = values.length === 1 ? w / 2 : index / (values.length - 1) * w;
    const y = h - 8 - Math.min(ratio, 5) / 5 * (h - 20);
    if (!best || ratio < best.ratio) best = { ratio, hz: item.hz };
    if (index) ctx.lineTo(x, y); else ctx.moveTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = "#8aa0a7";
  ctx.font = "11px monospace";
  ctx.fillText(`${(swr.lo / 1e6).toFixed(3)}`, 6, h - 4);
  ctx.fillText(`${(swr.hi / 1e6).toFixed(3)}`, w - 60, h - 4);
  ctx.fillText("2:1", 6, h - 8 - 2 / 5 * (h - 20));
  setText($("#swrInfo"), swr.running ? `${swr.pos}/${swr.points}` : swr.src?.toUpperCase() || "");
  setText($("#swrText"), best ? `min ${best.ratio.toFixed(2)} @ ${(best.hz / 1e6).toFixed(4)} MHz` : "");
}

async function recallMemory(memory) {
  if (!S.connected) { toast(t("connectFirst"), "err"); return; }
  try {
    await cmd("freq", { hz: memory.f });
    const mode = memory.m === "FM-N" ? "FM" : memory.m;
    if (mode) await cmd("mode", { mode });
    if (memory.rpt === "-" || memory.rpt === "+") {
      await cmd("rpt_shift", { dir: memory.rpt });
      if (memory.off) await cmd("rpt_offset", { hz: memory.off });
    } else if (memory.rpt === "S") {
      await cmd("rpt_shift", { dir: "S" });
    }
    if (memory.tone && memory.tone !== "OFF") {
      await cmd("tone_mode", { mode: memory.tone });
      if (memory.tone.startsWith("CTCSS") && memory.ctcss) {
        await cmd("ctcss", { tx: memory.ctcss, rx: memory.ctcss });
      } else if (memory.tone === "DCS" && memory.dcs) {
        await cmd("dcs", { tx: memory.dcs, rx: memory.dcs });
      }
    } else {
      await cmd("tone_mode", { mode: "OFF" });
    }
    if (memory.m === "FM-N") {
      try { await cmd("ee_set", { name: "nar", value: "ON" }); } catch { /* EEPROM writes may be off */ }
    }
    toast(memory.name || `M-${memory.ch || ""}`);
  } catch { /* reported by cmd() */ }
}

function renderMemories() {
  const query = ($("#memSearch").value || "").trim().toLowerCase();
  const list = MEMORIES.filter(m => !query || `${m.name || ""} ${m.f} ${m.m}`.toLowerCase().includes(query));
  setText($("#memCount"), `${MEMORIES.length} ${t("memories").toLowerCase()}`);
  const box = $("#memList");
  box.innerHTML = "";
  for (const memory of list) {
    const row = document.createElement("div");
    row.className = "mem-row";
    row.innerHTML = `<span class="ch">${memory.ch ? String(memory.ch).padStart(3, "0") : "-"}</span>
      <span class="name">${escapeHtml(memory.name || t("empty"))}</span>
      <span class="freqm">${(memory.f / 1e6).toFixed(5)} ${escapeHtml(memory.m || "")}</span>
      <button class="del" title="delete">x</button>`;
    const details = [];
    if (memory.rpt) details.push(memory.rpt === "S" ? "simplex" : `${memory.rpt} shift`);
    if (memory.off) details.push(`${memory.off / 1000} kHz`);
    if (memory.tone) details.push(memory.tone);
    if (memory.ctcss) details.push(`${memory.ctcss} Hz`);
    if (memory.dcs) details.push(`DCS ${memory.dcs}`);
    row.title = details.join(" · ");
    row.onclick = event => {
      if (event.target.classList.contains("del")) return;
      recallMemory(memory);
    };
    row.querySelector(".del").onclick = async () => {
      if (!confirm(t("confirmDelete"))) return;
      MEMORIES = MEMORIES.filter(item => item !== memory);
      await saveMemories();
      renderMemories();
    };
    box.append(row);
  }
  const quick = $("#quickMems");
  quick.innerHTML = "";
  if (!MEMORIES.length) {
    const hint = document.createElement("div");
    hint.className = "muted small";
    hint.textContent = t("noMemories");
    quick.append(hint);
  }
  for (const memory of MEMORIES.slice(0, 8)) {
    const row = document.createElement("div");
    row.className = "quick-mem";
    row.innerHTML = `<b>${escapeHtml(memory.name || "-")}</b><span>${(memory.f / 1e6).toFixed(5)} ${escapeHtml(memory.m || "")}</span>`;
    row.onclick = () => recallMemory(memory);
    quick.append(row);
  }
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function loadMemories() {
  try { MEMORIES = (await api("/api/memories")).memories || []; } catch (err) { toast(err.message, "err"); }
  renderMemories();
}

async function saveMemories() {
  try { await api("/api/memories", { memories: MEMORIES }); toast(t("saved")); }
  catch (err) { toast(err.message, "err"); }
}

function renderTrace() {
  const showPoll = $("#tracePoll").checked;
  const box = $("#traceList");
  box.querySelectorAll(".trace-line.poll").forEach(el => { if (!showPoll) el.remove(); });
  if (showPoll) {
    // polling rows already appended when they arrived
  }
}

async function pollTrace() {
  if (!document.querySelector('[data-page="console"]').classList.contains("active")) return;
  try {
    const data = await api(`/api/trace?since=${lastTraceN}`);
    const box = $("#traceList");
    for (const row of data.trace || []) {
      lastTraceN = Math.max(lastTraceN, row.n);
      if (row.poll && !$("#tracePoll").checked) continue;
      const line = document.createElement("div");
      line.className = "trace-line" + (row.poll ? " poll" : "");
      line.innerHTML = `<span class="n">${row.n}</span><span class="tx">${escapeHtml(row.tx || "")}</span>
        <span class="rx">${escapeHtml(row.rx || row.note || "")}</span><span>${row.poll ? "p" : ""}</span>`;
      box.append(line);
    }
    while (box.children.length > 400) box.firstChild.remove();
    box.scrollTop = box.scrollHeight;
  } catch { /* ignore */ }
}

function renderCw() {
  const cw = S.cw || {};
  setText($("#cwStatus"), cw.busy ? `${cw.pos}/${cw.marks?.length || 0}` : (cw.beacon ? "beacon" : ""));
  const strip = $("#cwStrip");
  strip.innerHTML = "";
  if (!cw.marks?.length) return;
  const total = cw.marks.reduce((sum, mark) => sum + mark.ms, 0) || 1;
  let x = 0;
  for (const mark of cw.marks) {
    if (mark.on) {
      const bar = document.createElement("div");
      bar.style.left = `${x / total * 100}%`;
      bar.style.width = `${Math.max(0.4, mark.ms / total * 100)}%`;
      strip.append(bar);
    }
    x += mark.ms;
  }
}

function playCw(cw) {
  if (!cw?.marks?.length || cw.job === cwLastJob) return;
  if (!$("#monOn").checked) { cwLastJob = cw.job; return; }
  cwLastJob = cw.job;
  const pitch = Number($("#monPitch").value) || 650;
  const volume = Number($("#monVol").value) / 100;
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    for (const node of audioNodes) { try { node.stop(); } catch { /* ignore */ } }
    audioNodes = [];
    const gain = audioCtx.createGain();
    gain.gain.value = 0;
    gain.connect(audioCtx.destination);
    const osc = audioCtx.createOscillator();
    osc.type = "sine";
    osc.frequency.value = pitch;
    osc.connect(gain);
    osc.start();
    let at = audioCtx.currentTime + 0.05;
    for (const mark of cw.marks) {
      const dur = mark.ms / 1000;
      if (mark.on) {
        gain.gain.setValueAtTime(volume, at);
        gain.gain.setValueAtTime(0, at + dur);
      }
      at += dur;
    }
    osc.stop(at + 0.05);
    audioNodes.push(osc, gain);
  } catch { /* audio not available */ }
}

function onState(state) {
  const prev = S;
  S = state;
  if (state.cw?.job && state.cw.job !== prev.cw?.job) playCw(state.cw);
  if (prev.memread?.running && state.memread && !state.memread.running) finishRadioMemories(state.memread);
  renderTop();
  renderDisplay();
  renderButtons();
  renderEe();
  renderScope();
  renderSwr();
  renderCw();
  if (state.ptt_alarm && state.ptt_alarm !== prev.ptt_alarm) toast(state.ptt_alarm, "err");
  if (pttLatchOn && !state.ptt_cat && state.ptt_alarm) {
    pttLatchOn = false;
    if (pttBeat) { clearInterval(pttBeat); pttBeat = null; }
    toggle($("#pttLatch"), "on", false);
    toggle($("#ptt"), "active", false);
  }
  if (state.memread?.running) {
    $("#memReadBar").hidden = false;
    $("#memReadFill").style.width = `${state.memread.total ? state.memread.pos / state.memread.total * 100 : 0}%`;
    setText($("#memReadText"), `${t("readRunning")} ${state.memread.pos}/${state.memread.total} (${state.memread.found})`);
  }
  if (pttLatchOn && !state.ptt_cat && state.connected) {
    // keep latch state independent; server watchdog may release and clear
  }
}

function startEvents() {
  const source = new EventSource("/api/events");
  source.onmessage = event => {
    try { onState(JSON.parse(event.data)); } catch { /* ignore malformed frame */ }
  };
  source.onerror = () => {
    if (!S.connected) return;
    setTimeout(() => { try { source.close(); } catch { /* ignore */ } startEvents(); }, 2000);
  };
}

async function connectRadio(cfg) {
  try {
    const data = await api("/api/connect", cfg);
    toast(`${t("connected")}: ${data.description || ""}`);
    $("#settingsDlg").close();
  } catch (err) { toast(err.message, "err"); }
}

function openSettings() {
  const cfg = S.cfg || {};
  $("#cfgSim").checked = !!cfg.sim;
  $("#cfgModel").value = cfg.model || "auto";
  $("#cfgBaud").value = String(cfg.baud || 4800);
  $("#cfgStop").value = String(cfg.stopbits || 2);
  $("#cfgPtt").value = cfg.ptt || "cat";
  $("#cfgPoll").value = cfg.poll_ms || 100;
  $("#cfgTimeout").value = cfg.timeout_ms || 300;
  $("#cfgTot").value = cfg.tot_s || 180;
  $("#cfgEe").checked = !!cfg.ee_write;
  $("#cfgAuto").checked = cfg.auto !== false;
  refreshPorts();
  $("#settingsDlg").showModal();
}

async function refreshPorts() {
  try {
    const data = await api("/api/ports");
    const select = $("#cfgPort");
    select.innerHTML = "";
    for (const port of data.ports) select.add(new Option(`${port.device} - ${port.description}`, port.device));
    if (data.defaults?.port) select.add(new Option(data.defaults.port, data.defaults.port));
  } catch { /* ignore */ }
}

function settingsConfig() {
  return {
    sim: $("#cfgSim").checked,
    model: $("#cfgModel").value,
    port: $("#cfgPort").value,
    baud: Number($("#cfgBaud").value),
    stopbits: Number($("#cfgStop").value),
    ptt: $("#cfgPtt").value,
    poll_ms: Number($("#cfgPoll").value),
    timeout_ms: Number($("#cfgTimeout").value),
    tot_s: Number($("#cfgTot").value),
    ee_write: $("#cfgEe").checked,
    auto: $("#cfgAuto").checked,
  };
}

function setupPtt() {
  const ptt = $("#ptt");
  const down = event => {
    if (event.button !== undefined && event.button !== 0) return;
    event.preventDefault();
    pttHeld = true;
    pttOn();
  };
  const up = () => {
    if (!pttHeld) return;
    pttHeld = false;
    if (!pttLatchOn) pttOff();
  };
  ptt.addEventListener("pointerdown", down);
  ptt.addEventListener("pointerup", up);
  ptt.addEventListener("pointerleave", up);
  ptt.addEventListener("pointercancel", up);
  $("#pttLatch").onclick = () => {
    pttLatchOn = !pttLatchOn;
    if (pttLatchOn) pttOn(); else pttOff();
    toggle($("#pttLatch"), "on", pttLatchOn);
  };
}

function pttOn() {
  if (!S.connected) { toast(t("connectFirst"), "err"); return; }
  cmd("ptt", { on: true }).catch(() => {});
  if (pttBeat) clearInterval(pttBeat);
  pttBeat = setInterval(() => api("/api/cmd", { op: "ptt_keepalive" }).catch(() => {}), 500);
  toggle($("#ptt"), "active", true);
}

function pttOff() {
  if (pttBeat) { clearInterval(pttBeat); pttBeat = null; }
  api("/api/cmd", { op: "ptt", on: false }).catch(() => {});
  toggle($("#ptt"), "active", false);
}

function setupTune() {
  const button = $("#tune");
  const on = event => {
    event.preventDefault();
    if (!S.connected) { toast(t("connectFirst"), "err"); return; }
    tuneHeld = true;
    cmd("tune", { on: true }).catch(() => {});
    if (tuneBeat) clearInterval(tuneBeat);
    tuneBeat = setInterval(() => api("/api/cmd", { op: "ptt_keepalive" }).catch(() => {}), 500);
    button.classList.add("active");
  };
  const off = () => {
    if (!tuneHeld) return;
    tuneHeld = false;
    if (tuneBeat) { clearInterval(tuneBeat); tuneBeat = null; }
    cmd("tune", { on: false }).catch(() => {});
    button.classList.remove("active");
  };
  button.addEventListener("pointerdown", on);
  button.addEventListener("pointerup", off);
  button.addEventListener("pointerleave", off);
  button.addEventListener("pointercancel", off);
}

function setupKnob() {
  const knob = $("#knob");
  let dragging = false, lastAngle = 0, accum = 0;
  const angleOf = event => {
    const rect = knob.getBoundingClientRect();
    return Math.atan2(event.clientY - (rect.top + rect.height / 2), event.clientX - (rect.left + rect.width / 2)) * 180 / Math.PI;
  };
  const rotate = angle => knob.style.setProperty("--knob-angle", `${angle}deg`);
  knob.addEventListener("pointerdown", event => {
    dragging = true;
    lastAngle = angleOf(event);
    knob.setPointerCapture(event.pointerId);
    knob.focus();
  });
  knob.addEventListener("pointermove", event => {
    if (!dragging) return;
    const angle = angleOf(event);
    let delta = angle - lastAngle;
    if (delta > 180) delta -= 360;
    if (delta < -180) delta += 360;
    lastAngle = angle;
    accum += delta;
    const detents = Math.trunc(accum / 10);
    if (detents) {
      accum -= detents * 10;
      changeFreq(detents * step);
    }
    rotate((angle + 360) % 360);
  });
  knob.addEventListener("pointerup", () => { dragging = false; });
  knob.addEventListener("wheel", event => {
    event.preventDefault();
    const dir = event.deltaY > 0 ? 1 : -1;
    changeFreq(dir * step);
  }, { passive: false });
}

function changeFreq(delta) {
  if (!S.connected) { toast(t("connectFirst"), "err"); return; }
  const hz = Math.round(((S.freq || 0) + delta) / 10) * 10;
  if (!inRx(hz)) return;
  S.freq = hz;
  renderFreq();
  setFreqLatest(hz);
}

function setupEntry() {
  const open = () => {
    entryOpen = true;
    $("#entry").hidden = false;
    $("#entryInput").value = (S.freq / 1e6).toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
    $("#entryInput").focus();
    $("#entryInput").select();
  };
  const close = () => { entryOpen = false; $("#entry").hidden = true; };
  const commit = () => {
    const raw = $("#entryInput").value.trim().replace(/\s/g, "").replace(",", ".");
    if (!raw) { close(); return; }
    let hz;
    if (raw.includes(".")) hz = Math.round(parseFloat(raw) * 1e6);
    else {
      const value = Number(raw);
      if (!Number.isFinite(value)) { toast(t("invalidFreq"), "err"); return; }
      if (value >= 1e6) hz = value;
      else if (value >= 1e4) hz = value * 1e3;
      else if (value >= 1e3) hz = value * 1e3;
      else hz = value * 1e6;
    }
    if (!Number.isFinite(hz) || !inRx(hz)) { toast(t("invalidFreq"), "err"); return; }
    setFreq(hz);
    close();
  };
  $("#freq").onclick = open;
  $("#entryInput").addEventListener("keydown", event => {
    if (event.key === "Enter") { event.preventDefault(); commit(); }
    if (event.key === "Escape") { event.preventDefault(); close(); }
  });
  document.addEventListener("mousedown", event => {
    if (entryOpen && !$("#entry").contains(event.target) && event.target !== $("#freq")) close();
  });
  document.addEventListener("keydown", event => {
    const tag = document.activeElement?.tagName;
    const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
    if (event.key === "Escape") {
      pttLatchOn = false;
      pttOff();
      if (tuneHeld) { tuneHeld = false; cmd("tune", { on: false }).catch(() => {}); }
      return;
    }
    if (typing || entryOpen) return;
    const mult = event.shiftKey ? 10 : event.altKey ? 100 : 1;
    if (event.key === "ArrowUp" || event.key === "ArrowRight") { event.preventDefault(); changeFreq(step * mult); }
    if (event.key === "ArrowDown" || event.key === "ArrowLeft") { event.preventDefault(); changeFreq(-step * mult); }
    if (event.key === "PageUp") { event.preventDefault(); changeFreq(step * 10 * mult); }
    if (event.key === "PageDown") { event.preventDefault(); changeFreq(-step * 10 * mult); }
    if (event.key === "Enter") { event.preventDefault(); open(); }
    if (event.key === " " && S.connected) {
      event.preventDefault();
      if (!event.repeat) { pttHeld = true; pttOn(); }
    }
  });
  document.addEventListener("keyup", event => {
    if (event.key === " " && pttHeld) { pttHeld = false; if (!pttLatchOn) pttOff(); }
  });
}

function setupTabs() {
  for (const tab of $$(".tab")) {
    tab.onclick = () => {
      for (const other of $$(".tab")) other.classList.toggle("active", other === tab);
      for (const page of $$(".tabpage")) page.classList.toggle("active", page.dataset.page === tab.dataset.tab);
      if (tab.dataset.tab === "console") pollTrace();
      if (tab.dataset.tab === "memories") renderMemories();
    };
  }
}

function setupMemories() {
  $("#memSearch").oninput = renderMemories;
  $("#memSave").onclick = async () => {
    if (!S.radio || !S.freq) { toast(t("noRadio"), "err"); return; }
    const memory = { name: ($("#memName").value || "").trim(), f: S.freq, m: modeName() };
    const written = S.written || {};
    if (/FM|PKT/.test(memory.m) && written.rpt) memory.rpt = written.rpt;
    if (written.off) memory.off = written.off;
    if (written.tone_mode) memory.tone = written.tone_mode;
    if (written.ctcss) memory.ctcss = written.ctcss[0];
    if (written.dcs) memory.dcs = written.dcs[0];
    MEMORIES.push(memory);
    $("#memName").value = "";
    await saveMemories();
    renderMemories();
  };
  $("#memExport").onclick = () => {
    const blob = new Blob([JSON.stringify({ memories: MEMORIES }, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "ft817-memories.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    toast(t("exported"));
  };
  $("#memImportBtn").onclick = () => $("#memImportFile").click();
  $("#memImportFile").onchange = async event => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      const list = Array.isArray(data) ? data : data.memories || [];
      for (const item of list) {
        if (!item || !Number.isFinite(Number(item.f))) continue;
        MEMORIES.push({ name: String(item.name || ""), f: Number(item.f), m: String(item.m || "USB") });
      }
      await saveMemories();
      renderMemories();
      toast(t("imported"));
    } catch (err) { toast(err.message, "err"); }
    event.target.value = "";
  };
  $("#memRead").onclick = async () => {
    if (!S.connected) { toast(t("connectFirst"), "err"); return; }
    $("#memReadBar").hidden = false;
    await api("/api/cmd", { op: "read_memories", wait: false }).catch(err => toast(err.message, "err"));
  };
  $("#memReadStop").onclick = () => api("/api/cmd", { op: "memread_stop" }).catch(() => {});
}

async function finishRadioMemories(progress) {
  $("#memReadBar").hidden = true;
  if (progress?.error) toast(progress.error, "err");
  try {
    const list = (await api("/api/radio_memories")).memories || [];
    if (!list.length) { toast(t("noMemories")); return; }
    let added = 0;
    for (const item of list) {
      const name = item.name || `M-${String(item.ch).padStart(3, "0")}`;
      if (MEMORIES.some(m => m.f === item.f && m.m === item.m && (m.name || "") === name)) continue;
      MEMORIES.push({ name, f: item.f, m: item.m, ch: item.ch, src: "radio" });
      added++;
    }
    await saveMemories();
    renderMemories();
    toast(`${t("readDone")}: ${added}`);
  } catch (err) { toast(err.message, "err"); }
}

function setupScope() {
  $("#scopeStart").onclick = () => {
    if (!S.connected) { toast(t("connectFirst"), "err"); return; }
    const span = Number($("#scopeSpan").value) * 1000;
    const points = Number($("#scopePts").value);
    api("/api/cmd", { op: "scope", span, points, dwell_ms: 20, wait: false })
      .catch(err => toast(err.message, "err"));
  };
  $("#scopeStop").onclick = () => {
    changeFreq(0);
  };
  $("#swrStart").onclick = async () => {
    if (!S.connected) { toast(t("connectFirst"), "err"); return; }
    const band = bandOf(S.freq);
    if (!band) { toast(t("invalidFreq"), "err"); return; }
    const whole = $("#swrSpan").value === "band";
    const span = whole ? Math.round((band.hi - band.lo) / 2) : Number($("#swrSpan").value) * 1000;
    const points = Number($("#swrPts").value);
    await api("/api/cmd", { op: "swr_sweep", span, points, lo: band.lo, hi: band.hi, whole_band: whole, settle_ms: 250, wait: false })
      .catch(err => toast(err.message, "err"));
    if (swrBeat) clearInterval(swrBeat);
    swrBeat = setInterval(() => api("/api/cmd", { op: "ptt_keepalive" }).catch(() => {}), 500);
  };
  $("#swrStop").onclick = () => {
    if (swrBeat) { clearInterval(swrBeat); swrBeat = null; }
    api("/api/cmd", { op: "swr_stop" }).catch(() => {});
  };
  setInterval(() => {
    if (swrBeat && !S.swr?.running) { clearInterval(swrBeat); swrBeat = null; }
  }, 1000);
}

function setupConsole() {
  $("#rawSend").onclick = async () => {
    const value = $("#rawHex").value.trim();
    if (!value) return;
    try {
      const data = await cmd("raw", { hex: value });
      toast(`reply: ${data.reply || "(none)"} (${data.n})`);
      pollTrace();
    } catch { /* reported */ }
  };
  $("#eeRead").onclick = async () => {
    try {
      const data = await cmd("ee_read", { addr: $("#eeAddr").value.trim() });
      toast(`${data.addr}: ${data.data}`);
      pollTrace();
    } catch { /* reported */ }
  };
  $("#tracePoll").onchange = renderTrace;
  $("#traceClear").onclick = () => { $("#traceList").innerHTML = ""; };
  traceTimer = setInterval(pollTrace, 1000);
}

function cwConfigFromUi() {
  return {
    params: {
      wpm: Number($("#cwWpm").value),
      farnsworth: Number($("#cwFarn").value),
      ratio: Number($("#cwRatio").value),
      weight: Number($("#cwWeight").value),
      comp_ms: Number($("#cwComp").value),
      cut: false,
    },
    port: $("#cwPort").value.trim(),
    line: $("#cwLine").value,
    ptt: $("#cwPtt").value,
    auto_cw: true,
    lead_ms: 60,
    tail_ms: 250,
    station: {
      mycall: $("#cwMyCall").value.trim(),
      call: $("#cwCall").value.trim(),
      rst: $("#cwRst").value.trim() || "599",
      nr: Number($("#cwNr").value) || 1,
      loc: $("#cwLoc").value.trim(),
    },
    memories: CWCFG?.memories || [],
    beacon: {
      text: $("#beaconText").value,
      interval: Number($("#beaconInterval").value) || 60,
      repeat: Number($("#beaconRepeat").value) || 0,
    },
    monitor: {
      on: $("#monOn").checked,
      pitch: Number($("#monPitch").value) || 650,
      vol: Number($("#monVol").value) || 40,
    },
    live: $("#cwLive").checked,
  };
}

let cwSaveTimer = null;
function saveCwConfigSoon() {
  clearTimeout(cwSaveTimer);
  cwSaveTimer = setTimeout(() => {
    api("/api/cw", { config: cwConfigFromUi() }).catch(() => {});
  }, 350);
}

function fillCwConfig(config) {
  CWCFG = config;
  const p = config.params || {};
  $("#cwWpm").value = p.wpm ?? 22;
  $("#cwFarn").value = p.farnsworth ?? 0;
  $("#cwRatio").value = p.ratio ?? 3;
  $("#cwWeight").value = p.weight ?? 50;
  $("#cwComp").value = p.comp_ms ?? 0;
  $("#cwLine").value = config.line || "dtr";
  $("#cwPort").value = config.port || "";
  $("#cwPtt").value = config.ptt || "auto";
  const station = config.station || {};
  $("#cwMyCall").value = station.mycall || "";
  $("#cwCall").value = station.call || "";
  $("#cwRst").value = station.rst || "599";
  $("#cwNr").value = station.nr ?? 1;
  $("#cwLoc").value = station.loc || "";
  $("#beaconText").value = config.beacon?.text || "";
  $("#beaconInterval").value = config.beacon?.interval ?? 60;
  $("#beaconRepeat").value = config.beacon?.repeat ?? 0;
  $("#monOn").checked = config.monitor?.on ?? true;
  $("#monPitch").value = config.monitor?.pitch ?? 650;
  $("#monVol").value = config.monitor?.vol ?? 40;
  $("#cwLive").checked = !!config.live;
  const box = $("#cwMems");
  box.innerHTML = "";
  (config.memories || []).forEach((memory, index) => {
    const button = document.createElement("button");
    button.className = "btn";
    button.textContent = memory.label || `F${index + 1}`;
    button.title = memory.text;
    button.onclick = () => { $("#cwText").value = memory.text; };
    box.append(button);
  });
}

function setupCw() {
  for (const id of ["cwWpm", "cwFarn", "cwRatio", "cwWeight", "cwComp", "cwLine", "cwPort", "cwPtt",
    "cwMyCall", "cwCall", "cwRst", "cwNr", "cwLoc", "beaconText", "beaconInterval", "beaconRepeat",
    "monOn", "monPitch", "monVol", "cwLive"]) {
    $(`#${id}`).addEventListener("change", saveCwConfigSoon);
    $(`#${id}`).addEventListener("input", saveCwConfigSoon);
  }
  $("#cwSend").onclick = async () => {
    const text = $("#cwText").value.trim();
    if (!text) return;
    try {
      if (!audioCtx) { try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch { /* ignore */ } }
      await cmd("cw_send", { text, live: $("#cwLive").checked });
    } catch { /* reported */ }
  };
  $("#cwStop").onclick = () => cmd("cw_stop").catch(() => {});
  $("#beaconStart").onclick = async () => {
    try {
      await cmd("cw_beacon", {
        on: true, text: $("#beaconText").value,
        interval: Number($("#beaconInterval").value) || 60,
        repeat: Number($("#beaconRepeat").value) || 0,
      });
    } catch { /* reported */ }
  };
  $("#beaconStop").onclick = () => cmd("cw_beacon", { on: false }).catch(() => {});
}

function setupTone() {
  $("#btnToneApply").onclick = () => {
    const mode = $("#toneMode").value;
    const value = $("#toneVal").value;
    (async () => {
      try {
        await cmd("tone_mode", { mode });
        if (mode === "DCS" && value.startsWith("D")) await cmd("dcs", { tx: Number(value.slice(1)) });
        else if (mode !== "OFF") await cmd("ctcss", { tx: Number(value) });
        toast(`${mode} ${value}`);
      } catch { /* reported */ }
    })();
  };
  $("#toneMode").onchange = fillToneValues;
}

function setupSettings() {
  $("#btnSettings").onclick = openSettings;
  $("#cfgClose").onclick = () => $("#settingsDlg").close();
  $("#cfgConnect").onclick = () => connectRadio(settingsConfig());
  $("#cfgDisconnect").onclick = async () => {
    await api("/api/disconnect", {}).catch(err => toast(err.message, "err"));
    $("#settingsDlg").close();
  };
  $("#btnQuit").onclick = async () => {
    if (!confirm(`${t("quit")}?`)) return;
    await api("/api/quit", {}).catch(() => {});
    document.body.innerHTML = `<div style="display:grid;place-items:center;height:100vh;color:#8aa0a7;font:16px sans-serif">${t("quit")}</div>`;
  };
  $("#btnPower").onclick = () => cmd("power", { on: !S.radio }).catch(() => {});
  $("#btnRefreshEe").onclick = () => {
    if (S.connected) cmd("ee_read", { addr: "0x7A" }).catch(() => {});
  };
  $("#btnVfo").onclick = () => cmd("vfo_ab").catch(() => {});
  $("#btnAeqB").onclick = () => cmd("a_eq_b").catch(() => {});
  $("#btnSwap").onclick = () => cmd("swap").catch(() => {});
  $("#btnSplit").onclick = () => cmd("split", { on: !S.written?.split }).catch(() => {});
  $("#btnLock").onclick = () => cmd("lock", { on: !S.written?.lock }).catch(() => {});
  $("#btnClar").onclick = () => cmd("clar", { on: !S.written?.clar_on }).catch(() => {});
  $("#btnTone").onclick = () => {
    const mode = (S.written?.tone_mode || "OFF") === "OFF" ? "CTCSS-ENC" : "OFF";
    cmd("tone_mode", { mode }).catch(() => {});
  };
  $("#btnApplyRpt").onclick = () => {
    (async () => {
      try {
        await cmd("rpt_shift", { dir: $("#rptSel").value });
        await cmd("rpt_offset", { hz: Number($("#rptOff").value) });
      } catch { /* reported */ }
    })();
  };
  $("#clarDown").onclick = () => nudgeClar(-step);
  $("#clarUp").onclick = () => nudgeClar(step);
  $("#clarVal").addEventListener("change", () => {
    const hz = Math.max(-9990, Math.min(9990, Number($("#clarVal").value) || 0));
    cmd("clar_freq", { hz }).catch(() => {});
  });
  $("#btnDown").onclick = () => changeFreq(-step);
  $("#btnUp").onclick = () => changeFreq(step);
  $("#btnStep").onclick = () => {
    const index = STEPS.indexOf(step);
    setStep(STEPS[(index + 1) % STEPS.length]);
  };
  const digits = { digit1: 100000, digit2: 10000, digit3: 1000, digit4: 100, digit5: 10 };
  for (const [id, value] of Object.entries(digits)) $("#" + id).onclick = () => setStep(value);
}

function nudgeClar(delta) {
  const hz = Math.max(-9990, Math.min(9990, Number($("#clarVal").value) + delta));
  $("#clarVal").value = hz;
  cmd("clar_freq", { hz }).catch(() => {});
}

function setupLang() {
  const select = $("#langSel");
  select.value = CURRENT_LANG;
  select.onchange = () => {
    CURRENT_LANG = select.value;
    localStorage.setItem("ft817.lang", CURRENT_LANG);
    setLang(CURRENT_LANG);
    api("/api/lang", { lang: CURRENT_LANG }).catch(() => {});
    renderTop();
    renderDisplay();
  };
  $("#lcdColor").value = localStorage.getItem("ft817.lcd") || "green";
  document.body.dataset.lcd = $("#lcdColor").value;
  $("#lcdColor").onchange = () => {
    document.body.dataset.lcd = $("#lcdColor").value;
    localStorage.setItem("ft817.lcd", $("#lcdColor").value);
  };
}

function clock() {
  const now = new Date();
  setText($("#utc"), now.toISOString().slice(11, 19));
}

async function boot() {
  setLang(CURRENT_LANG);
  setupLang();
  setupTabs();
  setupSettings();
  setupPtt();
  setupTune();
  setupKnob();
  setupEntry();
  setupMemories();
  setupScope();
  setupConsole();
  setupCw();
  setupTone();
  clock();
  setInterval(clock, 1000);
  try {
    INFO = await api("/api/info");
  } catch (err) {
    toast(err.message, "err");
    return;
  }
  initSelects();
  buildEe();
  try { await loadMemories(); } catch { /* ignore */ }
  try {
    const cw = await api("/api/cw");
    fillCwConfig(cw.config);
  } catch { /* ignore */ }
  try {
    const state = await api("/api/state");
    onState(state.state);
    if (!state.state.connected) setTimeout(openSettings, 600);
  } catch { /* ignore */ }
  startEvents();
  setInterval(() => {
    if (S.connected && !pttHeld && !pttLatchOn && S.ptt_cat) {
      // server watchdog will release; keep UI honest
    }
  }, 1000);
}

window.addEventListener("DOMContentLoaded", boot);

