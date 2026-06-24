"use strict";

const $ = (id) => document.getElementById(id);
const el = {
  jd: $("jd"), resume: $("resume"),
  resumeFile: $("resumeFile"), uploadBtn: $("uploadBtn"),
  jdList: $("jdList"), addJd: $("addJd"),
  backend: $("backend"), model: $("model"), baseUrl: $("baseUrl"), apiKey: $("apiKey"),
  actionBtn: $("actionBtn"), hint: $("hint"),
  inTitle: $("inTitle"), inDesc: $("inDesc"), outTitle: $("outTitle"), outDesc: $("outDesc"),
  scoreVal: $("scoreVal"), scoreSub: $("scoreSub"), gauge: $("gauge"), delta: $("delta"),
  matched: $("matched"), missing: $("missing"), matchCount: $("matchCount"), missCount: $("missCount"),
  rankList: $("rankList"), reportBox: $("reportBox"),
  textTitle: $("textTitle"), textBody: $("textBody"), copyBtn: $("copyBtn"),
  healthDot: $("healthDot"), tabs: $("tabs"),
};

// ── mode registry ─────────────────────────────────────────────────────────
const MODES = {
  score:     { btn: "算 ATS 匹配分", inDesc: "粘贴目标岗位 JD 与你的简历正文", outTitle: "ATS 匹配分", outDesc: "关键词命中与缺失" },
  match:     { btn: "多岗位匹配排序", inDesc: "一份简历，比对多个岗位 JD", outTitle: "岗位匹配排序", outDesc: "按匹配度从高到低排序" },
  report:    { btn: "简历体检",       inDesc: "只需简历，纯本地诊断（不调用 AI）", outTitle: "简历体检报告", outDesc: "量化率 / 强动词 / 板块 / 联系方式" },
  polish:    { btn: "AI 优化简历",     inDesc: "按目标 JD 重写简历，提升过筛率", outTitle: "优化结果", outDesc: "优化后简历 + ATS 分变化" },
  cover:     { btn: "生成求职信",       inDesc: "按目标 JD 生成定制求职信", outTitle: "求职信", outDesc: "基于你简历真实经历生成" },
  interview: { btn: "预测面试题",       inDesc: "按 JD + 简历预测高频面试题", outTitle: "面试题预测", outDesc: "技术 / 项目 / 行为题 + 考点" },
};
let mode = "score";

// ── persistence ────────────────────────────────────────────────────────────
const SAVE_KEYS = ["jd", "resume", "model", "baseUrl", "apiKey", "backend"];
function loadState() {
  SAVE_KEYS.forEach((k) => {
    const v = localStorage.getItem("jobcv:" + k);
    if (v != null && el[k]) el[k].value = v;
  });
  const m = localStorage.getItem("jobcv:mode");
  toggleCustom();
  setMode(MODES[m] ? m : "score");
}
function saveState() {
  SAVE_KEYS.forEach((k) => el[k] && localStorage.setItem("jobcv:" + k, el[k].value));
  localStorage.setItem("jobcv:mode", mode);
}
function toggleCustom() { document.body.classList.toggle("show-custom", el.backend.value === "custom"); }

function setMode(m) {
  mode = m;
  document.body.className = "mode-" + m + (document.body.classList.contains("show-custom") ? " show-custom" : "");
  const cfg = MODES[m];
  el.actionBtn.firstChild.textContent = cfg.btn;
  el.inDesc.textContent = cfg.inDesc;
  el.outTitle.textContent = cfg.outTitle;
  el.outDesc.textContent = cfg.outDesc;
  [...el.tabs.children].forEach((t) => t.classList.toggle("active", t.dataset.mode === m));
  if (m === "match" && !el.jdList.children.length) { addJdRow(); addJdRow(); }
  setHint("");
  saveState();
}

function setHint(msg, isErr = false) {
  el.hint.textContent = msg || "";
  el.hint.classList.toggle("err", isErr);
}

// ── shared rendering ────────────────────────────────────────────────────────
function renderChips(box, words, cls) {
  box.innerHTML = "";
  if (!words || !words.length) { box.innerHTML = '<span class="chips-empty">暂无</span>'; return; }
  words.forEach((w) => {
    const c = document.createElement("span");
    c.className = "chip " + cls;
    c.textContent = w;
    box.appendChild(c);
  });
}
function ringColor(s) { return s >= 75 ? "var(--ok)" : s >= 50 ? "var(--warn)" : "var(--miss)"; }

let countTimer = null;
function animateScore(target) {
  if (countTimer) cancelAnimationFrame(countTimer);
  const start = performance.now();
  const from = parseFloat(el.scoreVal.textContent) || 0;
  const tick = (now) => {
    const t = Math.min(1, (now - start) / 700);
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

// ── multi-JD rows ────────────────────────────────────────────────────────────
let jdSeq = 0;
function addJdRow(label = "", text = "") {
  jdSeq++;
  const row = document.createElement("div");
  row.className = "jd-row";
  row.innerHTML = `
    <div class="jd-row-top">
      <input class="jd-label" placeholder="岗位名 / 公司（如：字节-后端）" />
      <button type="button" class="jd-del" title="删除">×</button>
    </div>
    <textarea class="jd-text" placeholder="粘贴这个岗位的 JD…"></textarea>`;
  row.querySelector(".jd-label").value = label || `岗位 ${jdSeq}`;
  row.querySelector(".jd-text").value = text;
  row.querySelector(".jd-del").addEventListener("click", () => {
    if (el.jdList.children.length <= 1) { setHint("至少保留一个岗位。", true); return; }
    row.remove();
  });
  el.jdList.appendChild(row);
}
function collectJds() {
  const jds = {};
  [...el.jdList.querySelectorAll(".jd-row")].forEach((row, i) => {
    const label = row.querySelector(".jd-label").value.trim() || `岗位 ${i + 1}`;
    const text = row.querySelector(".jd-text").value.trim();
    if (text) jds[label] = text;
  });
  return jds;
}

// ── network ──────────────────────────────────────────────────────────────────
async function post(path, body) {
  const r = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}
function aiPayload(extra = {}) {
  const backend = el.backend.value;
  return {
    resume: el.resume.value.trim(), jd: el.jd.value.trim(), top: 40,
    backend, model: el.model.value.trim() || null,
    base_url: backend === "custom" ? el.baseUrl.value.trim() || null : null,
    api_key: el.apiKey.value.trim() || null, ...extra,
  };
}
function needResume() {
  if (!el.resume.value.trim()) { setHint("请先填写简历（可上传文件）。", true); return false; }
  return true;
}
function needResumeJd() {
  if (!el.resume.value.trim() || !el.jd.value.trim()) { setHint("请先填写 JD 和简历。", true); return false; }
  return true;
}

// ── actions per mode ─────────────────────────────────────────────────────────
async function run() {
  const fn = { score: doScore, match: doMatch, report: doReport, polish: doPolish, cover: doCover, interview: doInterview }[mode];
  el.actionBtn.disabled = true;
  try { await fn(); }
  catch (e) { setHint(e.message, true); }
  finally { el.actionBtn.disabled = false; }
}

async function doScore() {
  if (!needResumeJd()) return;
  saveState(); setHint("计算中…");
  const m = await post("/api/score", { resume: el.resume.value.trim(), jd: el.jd.value.trim(), top: 40 });
  renderMatch(m); el.delta.textContent = "";
  setHint("ATS 分已更新。缺失关键词如属实，可写进简历提升过筛率。");
}

async function doMatch() {
  if (!needResume()) return;
  const jds = collectJds();
  if (Object.keys(jds).length < 1) { setHint("请至少填写一个岗位的 JD。", true); return; }
  saveState(); setHint("匹配排序中…");
  const { ranked } = await post("/api/match", { resume: el.resume.value.trim(), jds, top: 40 });
  el.rankList.innerHTML = "";
  ranked.forEach((it, i) => {
    const r = it.result;
    const row = document.createElement("div");
    row.className = "rank-row" + (i === 0 ? " top" : "");
    const miss = r.missing.length ? `<b>缺失：</b>${r.missing.slice(0, 10).join("、")}${r.missing.length > 10 ? " …" : ""}` : "全部关键词命中 ✅";
    const v = r.score >= 75 ? ["verdict-ok", "建议投递"] : r.score >= 50 ? ["verdict-mid", "可冲刺"] : ["verdict-low", "差距较大"];
    row.innerHTML = `
      <div class="rank-row-head">
        <span class="rank-no">${i + 1}</span>
        <span class="rank-label"></span>
        <span class="rank-verdict ${v[0]}">${v[1]}</span>
        <span class="rank-score">${r.score}<small>/100 · ${r.matched.length}/${r.total}</small></span>
      </div>
      <div class="rank-bar"><i style="width:0"></i></div>
      <div class="rank-miss">${miss}</div>`;
    row.querySelector(".rank-label").textContent = it.label;
    el.rankList.appendChild(row);
    requestAnimationFrame(() => { row.querySelector(".rank-bar i").style.width = r.score + "%"; });
  });
  setHint(`已比对 ${ranked.length} 个岗位。最匹配：「${ranked[0].label}」（${ranked[0].result.score} 分）。`);
}

async function doReport() {
  if (!needResume()) return;
  saveState(); setHint("体检中…");
  const rep = await post("/api/report", { resume: el.resume.value.trim() });
  const grade = rep.score >= 80 ? ["优秀", "var(--ok)"] : rep.score >= 60 ? ["良好", "var(--warn)"] : ["待改进", "var(--miss)"];
  const yn = (b) => b ? "✓" : "✗";
  const stat = (k, v) => `<div class="rep-stat"><span>${k}</span><b>${v}</b></div>`;
  const issues = rep.issues.map((it) =>
    `<div class="rep-issue ${it.level === "warn" ? "warn" : ""}"><span class="ic">${it.level === "warn" ? "⚠️" : "💡"}</span><span>${escapeHtml(it.msg)}</span></div>`
  ).join("");
  el.reportBox.innerHTML = `
    <div class="rep-top">
      <div><div class="rep-score" style="color:${grade[1]}">${rep.score}<small>/100</small></div>
      <div class="rep-grade" style="color:${grade[1]}">${grade[0]}</div></div>
      <div style="font-size:13px;color:var(--muted);line-height:1.6">综合量化成果、动词力度、篇幅、板块与联系方式得出。<br>下方是逐项明细与改进建议。</div>
    </div>
    <div class="rep-stats">
      ${stat("总字数", rep.word_count)}
      ${stat("经历条目", rep.bullet_count)}
      ${stat("量化条目", `${rep.quantified}/${rep.bullet_count}（${Math.round(rep.quantified_ratio * 100)}%）`)}
      ${stat("强动词开头", rep.strong_verb_bullets)}
      ${stat("弱开头", rep.weak_opener_bullets)}
      ${stat("含板块", rep.sections_present.length ? rep.sections_present.join(" / ") : "无")}
      ${stat("邮箱", yn(rep.has_email))}
      ${stat("电话", yn(rep.has_phone))}
    </div>
    <div class="kw-head" style="margin-bottom:12px">改进建议</div>
    <div class="rep-issues">${issues}</div>`;
  setHint(`体检完成：${rep.score}/100（${grade[0]}）。`);
}

async function doAiText(path, busy) {
  if (!needResumeJd()) return;
  saveState();
  el.copyBtn.hidden = true;
  el.textBody.innerHTML = `<p class="empty">${busy}</p>`;
  setHint(busy);
  const res = await post(path, aiPayload());
  el.textTitle.textContent = MODES[mode].outTitle;
  el.textBody.textContent = res.text;
  el.copyBtn.hidden = false;
  setHint(`已用 ${res.backend} / ${res.model} 生成完成。`);
}
const doCover = () => doAiText("/api/cover", "AI 生成求职信中，约几十秒…");
const doInterview = () => doAiText("/api/interview", "AI 预测面试题中，约几十秒…");

async function doPolish() {
  if (!needResumeJd()) return;
  saveState();
  el.copyBtn.hidden = true;
  el.textBody.innerHTML = '<p class="empty">AI 优化中，约几十秒…</p>';
  setHint("AI 优化中，约几十秒…");
  const res = await post("/api/polish", aiPayload());
  renderMatch(res.after);
  const d = +(res.after.score - res.before.score).toFixed(1);
  el.delta.textContent = `优化前 ${res.before.score} → 优化后 ${res.after.score}  (${d >= 0 ? "+" : ""}${d})`;
  el.textTitle.textContent = "优化后简历";
  el.textBody.textContent = res.polished;
  el.copyBtn.hidden = false;
  setHint(`已用 ${res.backend} / ${res.model} 优化完成，ATS 分变化见上。`);
}

// ── file upload ──────────────────────────────────────────────────────────────
async function uploadResume(file) {
  el.uploadBtn.disabled = true;
  const old = el.uploadBtn.textContent;
  el.uploadBtn.textContent = "解析中…";
  try {
    const fd = new FormData(); fd.append("file", file);
    const r = await fetch("/api/extract", { method: "POST", body: fd });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    el.resume.value = data.text;
    saveState();
    setHint(`已从「${data.filename}」提取简历文本（${data.text.length} 字），可直接使用。`);
  } catch (e) {
    setHint("文件解析失败：" + e.message, true);
  } finally {
    el.uploadBtn.disabled = false; el.uploadBtn.textContent = old;
  }
}

function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

async function checkHealth() {
  try { const r = await fetch("/api/health"); el.healthDot.classList.toggle("ok", r.ok); }
  catch { el.healthDot.classList.remove("ok"); }
}

// ── wiring ───────────────────────────────────────────────────────────────────
el.tabs.addEventListener("click", (e) => { const t = e.target.closest(".tab"); if (t) setMode(t.dataset.mode); });
el.actionBtn.addEventListener("click", run);
el.addJd.addEventListener("click", () => addJdRow());
el.backend.addEventListener("change", () => { toggleCustom(); saveState(); });
el.uploadBtn.addEventListener("click", () => el.resumeFile.click());
el.resumeFile.addEventListener("change", (e) => { if (e.target.files[0]) uploadResume(e.target.files[0]); e.target.value = ""; });
el.copyBtn.addEventListener("click", () => {
  navigator.clipboard.writeText(el.textBody.textContent).then(
    () => setHint("已复制到剪贴板。"),
    () => setHint("复制失败，请手动选择。", true)
  );
});

loadState();
checkHealth();
