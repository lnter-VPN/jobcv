"use strict";

const $ = (id) => document.getElementById(id);
const el = {
  jd: $("jd"), resume: $("resume"),
  backend: $("backend"), model: $("model"), baseUrl: $("baseUrl"), apiKey: $("apiKey"),
  scoreBtn: $("scoreBtn"), polishBtn: $("polishBtn"), hint: $("hint"),
  scoreVal: $("scoreVal"), scoreSub: $("scoreSub"), gauge: $("gauge"), delta: $("delta"),
  matched: $("matched"), missing: $("missing"), matchCount: $("matchCount"), missCount: $("missCount"),
  polishedBlock: $("polishedBlock"), polishedText: $("polishedText"), copyBtn: $("copyBtn"),
  healthDot: $("healthDot"),
};

// --- persistence (key + inputs stay local to the browser) ---
const SAVE_KEYS = ["jd", "resume", "model", "baseUrl", "apiKey", "backend"];
function loadState() {
  SAVE_KEYS.forEach((k) => {
    const v = localStorage.getItem("jobcv:" + k);
    if (v != null && el[k]) el[k].value = v;
  });
  toggleCustom();
}
function saveState() {
  SAVE_KEYS.forEach((k) => el[k] && localStorage.setItem("jobcv:" + k, el[k].value));
}

function toggleCustom() {
  document.body.classList.toggle("show-custom", el.backend.value === "custom");
}

function setHint(msg, isErr = false) {
  el.hint.textContent = msg || "";
  el.hint.classList.toggle("err", isErr);
}

function renderChips(box, words, cls) {
  box.innerHTML = "";
  if (!words || !words.length) {
    box.innerHTML = '<span class="chips-empty">暂无</span>';
    return;
  }
  words.forEach((w) => {
    const c = document.createElement("span");
    c.className = "chip " + cls;
    c.textContent = w;
    box.appendChild(c);
  });
}

// score band → ring color
function ringColor(score) {
  if (score >= 75) return "var(--ok)";
  if (score >= 50) return "var(--warn)";
  return "var(--miss)";
}

// animated count-up for the gauge number
let countTimer = null;
function animateScore(target) {
  if (countTimer) cancelAnimationFrame(countTimer);
  const start = performance.now();
  const from = parseFloat(el.scoreVal.textContent) || 0;
  const dur = 700;
  const tick = (now) => {
    const t = Math.min(1, (now - start) / dur);
    const eased = 1 - Math.pow(1 - t, 3);
    el.scoreVal.textContent = Math.round(from + (target - from) * eased);
    if (t < 1) countTimer = requestAnimationFrame(tick);
  };
  countTimer = requestAnimationFrame(tick);
}

function renderMatch(m) {
  el.gauge.style.setProperty("--ring", ringColor(m.score));
  el.gauge.style.setProperty("--pct", m.score);
  animateScore(m.score);
  el.scoreSub.textContent = `${m.matched.length}/${m.total} 关键词命中`;
  el.matchCount.textContent = `(${m.matched.length})`;
  el.missCount.textContent = `(${m.missing.length})`;
  renderChips(el.matched, m.matched, "ok");
  renderChips(el.missing, m.missing, "miss");
}

function payload(extra = {}) {
  const backend = el.backend.value;
  return {
    resume: el.resume.value.trim(),
    jd: el.jd.value.trim(),
    top: 40,
    backend: backend === "custom" ? "custom" : backend,
    model: el.model.value.trim() || null,
    base_url: backend === "custom" ? el.baseUrl.value.trim() || null : null,
    api_key: el.apiKey.value.trim() || null,
    ...extra,
  };
}

function validate() {
  if (!el.jd.value.trim() || !el.resume.value.trim()) {
    setHint("请先填写 JD 和简历。", true);
    return false;
  }
  return true;
}

async function post(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}

async function doScore() {
  if (!validate()) return;
  saveState();
  el.scoreBtn.disabled = true;
  setHint("计算中…");
  try {
    const m = await post("/api/score", payload());
    renderMatch(m);
    el.delta.textContent = "";
    setHint("ATS 分已更新。缺失关键词如属实，可写进简历提升过筛率。");
  } catch (e) {
    setHint(e.message, true);
  } finally {
    el.scoreBtn.disabled = false;
  }
}

async function doPolish() {
  if (!validate()) return;
  saveState();
  el.polishBtn.disabled = true;
  setHint("AI 优化中，约几十秒…");
  try {
    const res = await post("/api/polish", payload());
    renderMatch(res.after);
    const d = +(res.after.score - res.before.score).toFixed(1);
    el.delta.textContent = `优化前 ${res.before.score} → 优化后 ${res.after.score}  (${d >= 0 ? "+" : ""}${d})`;
    el.polishedText.textContent = res.polished;
    el.polishedBlock.hidden = false;
    setHint(`已用 ${res.backend} / ${res.model} 优化完成。`);
  } catch (e) {
    setHint(e.message, true);
  } finally {
    el.polishBtn.disabled = false;
  }
}

async function checkHealth() {
  try {
    const r = await fetch("/api/health");
    el.healthDot.classList.toggle("ok", r.ok);
  } catch {
    el.healthDot.classList.remove("ok");
  }
}

el.scoreBtn.addEventListener("click", doScore);
el.polishBtn.addEventListener("click", doPolish);
el.backend.addEventListener("change", () => { toggleCustom(); saveState(); });
el.copyBtn.addEventListener("click", () => {
  navigator.clipboard.writeText(el.polishedText.textContent).then(
    () => setHint("已复制优化后简历到剪贴板。"),
    () => setHint("复制失败，请手动选择。", true)
  );
});

loadState();
checkHealth();
