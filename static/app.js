/* Plateforme de révision #AlmaUteam4ever — front (vanilla JS, sans dépendance) */
(() => {
  const $app = document.getElementById("app");
  const COLORS = {"global-marketing": "#2f6f5e", "ai-marketing": "#5b4bd6", "customer-development": "#d9652b", "lodging": "#b23a5b"};
  const T = {
    fr: {home: "Accueil", board: "Classement", admin: "Admin", pwd: "Mot de passe", out: "Déconnexion",
         fiches: "Fiches", quiz: "Quiz", coach: "Coach IA", drive: "Cours (Drive)", agenda: "Agenda"},
    en: {home: "Home", board: "Leaderboard", admin: "Admin", pwd: "Password", out: "Log out",
         fiches: "Notes", quiz: "Quiz", coach: "AI Coach", drive: "Course files", agenda: "Agenda"},
  };
  const S = {me: null, lang: localStorage.getItem("lang") || "fr", coachEnabled: false, coachLimit: 40,
             chats: {}, quiz: null, subjectCache: {}};
  const t = (k) => T[S.lang][k];

  /* ---------- utils ---------- */
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  function inline(s) {
    return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|[\s(])\*(?!\s)(.+?)\*(?=[\s).,;:!?]|$)/g, "$1<i>$2</i>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }
  function md(text) {
    const lines = String(text).split("\n"); let html = "", list = false;
    for (const ln of lines) {
      const m = ln.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)/);
      if (m) { if (!list) { html += "<ul>"; list = true; } html += "<li>" + inline(m[1]) + "</li>"; }
      else { if (list) { html += "</ul>"; list = false; } if (ln.trim()) html += "<p>" + inline(ln) + "</p>"; }
    }
    return html + (list ? "</ul>" : "");
  }
  function toast(msg) {
    const el = document.getElementById("toast"); el.textContent = msg; el.classList.add("show");
    clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove("show"), 2600);
  }
  async function api(path, body, method) {
    const opt = {headers: {"X-Requested-With": "fetch"}, credentials: "same-origin"};
    if (method) opt.method = method;
    if (body instanceof FormData) { opt.method = "POST"; opt.body = body; }
    else if (body !== undefined) { opt.method = "POST"; opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
    const r = await fetch(path, opt);
    let data = {}; try { data = await r.json(); } catch (e) { /* vide */ }
    if (r.status === 401 && path !== "/api/login") { S.me = null; go("#/login"); throw new Error("auth"); }
    if (!r.ok) { const e = new Error(data.error || "Erreur"); e.status = r.status; throw e; }
    return data;
  }
  const go = (h) => { if (location.hash === h) route(); else location.hash = h; };
  const bar = (p, color) => `<div class="bar"><i style="width:${p}%;${color ? "background:" + color : ""}"></i></div>`;

  /* ---------- shell ---------- */
  function shell(inner, active) {
    const admin = S.me && S.me.is_admin;
    return `<header class="top"><div class="top-in">
      <a class="brand" href="#/">📚 Révisions <span>#AlmaUteam4ever</span></a>
      <nav class="nav">
        <a href="#/" class="${active === "home" ? "on" : ""}">${t("home")}</a>
        <a href="#/agenda" class="${active === "agenda" ? "on" : ""}">📅 ${t("agenda")}</a>
        <a href="#/board" class="${active === "board" ? "on" : ""}">${t("board")}</a>
        ${admin ? `<a href="#/admin" class="${active === "admin" ? "on" : ""}">${t("admin")}</a>` : ""}
        <a href="#/me" class="${active === "me" ? "on" : ""}">${esc(S.me.name)}</a>
        <span class="lang"><button data-l="fr" class="${S.lang === "fr" ? "on" : ""}">FR</button><button data-l="en" class="${S.lang === "en" ? "on" : ""}">EN</button></span>
      </nav></div></header><main class="wrap">${inner}</main>`;
  }
  function paint(html, active) {
    $app.innerHTML = shell(html, active);
    $app.querySelectorAll(".lang button").forEach((b) => b.onclick = () => {
      S.lang = b.dataset.l; localStorage.setItem("lang", S.lang); route();
    });
  }

  /* ---------- login ---------- */
  function viewLogin() {
    $app.innerHTML = `<div class="wrap"><div class="card login">
      <div class="hero">📚</div><h1>#AlmaUteam4ever</h1>
      <p class="muted">Plateforme de révision pour le midterm.<br>Connecte-toi avec ton prénom.</p>
      <form id="lf"><input name="u" placeholder="Prénom" autocomplete="username" autocapitalize="none" required>
        <input name="p" type="password" placeholder="Mot de passe" autocomplete="current-password" required>
        <div class="err" id="le"></div><button class="btn">Se connecter</button></form></div></div>`;
    document.getElementById("lf").onsubmit = async (e) => {
      e.preventDefault(); const f = e.target;
      try { await api("/api/login", {username: f.u.value, password: f.p.value}); await boot(); go("#/"); }
      catch (er) { document.getElementById("le").textContent = er.message; }
    };
  }

  /* ---------- home ---------- */
  async function viewHome() {
    const d = await api("/api/subjects");
    const cards = d.subjects.map((s) => {
      const p = s.progress;
      return `<a class="card subj" style="--c:${COLORS[s.id] || "#2f6f5e"}" href="#/s/${s.id}/fiches">
        <div class="row spread"><span class="em">${s.emoji}</span><span class="chip">${p.level.icon} ${p.level.name}</span></div>
        <div><h3>${esc(s.name[S.lang])}</h3><div class="muted small">${esc(s.teacher)}</div></div>
        ${bar(p.pct, COLORS[s.id])}
        <div class="row spread small muted"><span>${p.mastered}/${p.total} ${S.lang === "fr" ? "questions maîtrisées" : "questions mastered"}</span><b>${p.pct}%</b></div>
        <div class="small muted">${s.n_fiches} ${S.lang === "fr" ? "fiches" : "notes"} · ${s.n_qcm} QCM</div></a>`;
    }).join("");
    paint(`<div class="card hero-card"><div class="ring" style="--p:${d.overall}"><b>${d.overall}%</b></div>
      <div><h1>${S.lang === "fr" ? "Salut" : "Hi"} ${esc(S.me.name)} 👋</h1>
      <p class="muted" style="margin:0">${S.lang === "fr" ? "Niveau global" : "Overall level"} : <b>${d.level.icon} ${d.level.name}</b> · ${d.score} pts<br>
      ${S.lang === "fr" ? "Une question est « maîtrisée » quand ta dernière réponse était juste." : "A question is “mastered” when your latest answer was correct."}</p></div></div>
      <div id="upnext"></div><div class="grid two">${cards}</div>`, "home");
    upNext();
  }
  async function upNext() {
    try {
      const d = await api("/api/events?from=" + new Date().toISOString().slice(0, 10) + "T00:00");
      const mine = d.events.filter((e) => e.mine).slice(0, 4), el = document.getElementById("upnext"); if (!el) return;
      if (!mine.length) return;
      el.innerHTML = `<div class="card" style="margin-bottom:16px"><div class="row spread"><h3 style="margin:0">📅 ${S.lang === "fr" ? "Prochains événements" : "Coming up"}</h3><a class="small" href="#/agenda">${S.lang === "fr" ? "Tout l'agenda →" : "Full agenda →"}</a></div>
        ${mine.map((e) => `<div class="ev-line"><span class="ev-when">${fmtWhen(e)}</span><b>${esc(e.title)}</b> ${subChips(e)}</div>`).join("")}</div>`;
    } catch (e) { /* silencieux */ }
  }

  /* ---------- subject ---------- */
  async function viewSubject(sid, tab) {
    const s = await api("/api/subjects/" + sid); S.subjectCache[sid] = s;
    const c = COLORS[sid] || "#2f6f5e"; const p = s.progress;
    const tabs = [["fiches", t("fiches")], ["quiz", t("quiz")], ["coach", t("coach")], ["drive", "📂 " + t("drive")]]
      .map(([k, l]) => `<a href="#/s/${sid}/${k}" class="${tab === k ? "on" : ""}">${l}</a>`).join("");
    paint(`<div style="--accent:${c};--accent-soft:color-mix(in srgb,${c} 14%,var(--card))">
      <div class="row spread" style="margin-top:22px"><div><div class="muted small"><a href="#/">← ${t("home")}</a></div>
        <h1>${s.emoji} ${esc(s.name[S.lang])}</h1><div class="muted">${esc(s.teacher)}</div></div>
        <div style="min-width:180px"><span class="chip">${p.level.icon} ${p.level.name} · ${p.pct}%</span>${bar(p.pct, c)}
          <div class="small muted" style="margin-top:4px">${p.mastered}/${p.total} ${S.lang === "fr" ? "maîtrisées" : "mastered"}</div></div></div>
      <div class="tabs">${tabs}</div><div id="tab"></div></div>`, "home");
    const box = document.getElementById("tab");
    if (tab === "quiz") tabQuiz(box, s); else if (tab === "coach") tabCoach(box, s); else if (tab === "drive") tabDrive(box, s); else tabFiches(box, s);
  }

  function tabFiches(box, s) {
    box.innerHTML = `<div class="notice" style="margin-bottom:14px">📌 ${esc(s.coverage)}</div>` + s.fiches.map((f, i) => `
      <details class="card fiche" ${i === 0 ? "open" : ""}><summary><h3>${i + 1}. ${esc(f.title[S.lang])}</h3>
        <span class="chip">${f.mastered}/${f.n_qcm} QCM</span></summary>
        <ul>${f.body[S.lang].map((b) => `<li>${inline(b)}</li>`).join("")}</ul>
        <div class="foot row"><button class="btn" data-quiz="${f.id}">${S.lang === "fr" ? "S'entraîner sur cette fiche" : "Practice this sheet"}</button>
        <button class="btn ghost" data-ask="${f.id}">${S.lang === "fr" ? "Demander au coach" : "Ask the coach"}</button></div></details>`).join("");
    box.querySelectorAll("[data-quiz]").forEach((b) => b.onclick = () => { S.quizPreset = {fiche: b.dataset.quiz}; go(`#/s/${s.id}/quiz`); });
    box.querySelectorAll("[data-ask]").forEach((b) => b.onclick = () => {
      const f = s.fiches.find((x) => x.id === b.dataset.ask);
      S.coachPreset = (S.lang === "fr" ? "Explique-moi simplement : " : "Explain simply: ") + f.title[S.lang]; go(`#/s/${s.id}/coach`);
    });
  }

  /* ---------- quiz ---------- */
  function tabQuiz(box, s) {
    const preset = S.quizPreset || {}; S.quizPreset = null;
    let n = 10, mode = "mixed", fiche = preset.fiche || "";
    S.quiz = null;
    const fr = S.lang === "fr";
    box.innerHTML = `<div class="card setup">
      <div class="field"><label>${fr ? "Nombre de questions" : "Number of questions"}</label><div class="seg" id="sn">
        ${[5, 10, 20].map((x) => `<button data-n="${x}" class="${x === n ? "on" : ""}">${x}</button>`).join("")}</div></div>
      <div class="field"><label>${fr ? "Mode" : "Mode"}</label><div class="seg" id="sm">
        <button data-m="mixed" class="on">${fr ? "Mélange intelligent" : "Smart mix"}</button>
        <button data-m="weak">${fr ? "Mes points faibles" : "My weak spots"}</button></div>
        <div class="small muted">${fr ? "Le mélange privilégie les questions ratées ou jamais vues. Les réponses sont mélangées à chaque fois." : "The mix favours missed or unseen questions. Answers are reshuffled every time."}</div></div>
      <div class="field"><label>${fr ? "Fiche" : "Sheet"}</label><select id="sf"><option value="">${fr ? "Toutes les fiches" : "All sheets"}</option>
        ${s.fiches.map((f) => `<option value="${f.id}" ${f.id === fiche ? "selected" : ""}>${esc(f.title[S.lang])}</option>`).join("")}</select></div>
      <div class="err" id="qe"></div><button class="btn" id="go">${fr ? "Lancer le quiz" : "Start quiz"}</button></div>
      <div id="qbox"></div>`;
    box.querySelectorAll("#sn button").forEach((b) => b.onclick = () => { n = +b.dataset.n; box.querySelectorAll("#sn button").forEach((x) => x.classList.toggle("on", x === b)); });
    box.querySelectorAll("#sm button").forEach((b) => b.onclick = () => { mode = b.dataset.m; box.querySelectorAll("#sm button").forEach((x) => x.classList.toggle("on", x === b)); });
    document.getElementById("sf").onchange = (e) => fiche = e.target.value;
    document.getElementById("go").onclick = async () => {
      try {
        const d = await api("/api/quiz/start", {subject: s.id, n, mode, fiche});
        if (!d.questions.length) { document.getElementById("qe").textContent = fr ? "Aucune question disponible." : "No question available."; return; }
        S.quiz = {s, questions: d.questions, i: 0, res: [], done: false};
        box.querySelector(".setup").style.display = "none"; renderQ();
      } catch (e) { document.getElementById("qe").textContent = e.message; }
    };
    if (preset.fiche) document.getElementById("go").click();
  }

  function renderQ() {
    const Q = S.quiz, q = Q.questions[Q.i], fr = S.lang === "fr"; const qb = document.getElementById("qbox");
    qb.innerHTML = `<div class="card"><div class="qhead"><span class="chip">${Q.i + 1} / ${Q.questions.length}</span>
      <span class="small muted">${esc(q.fiche_title[S.lang])}</span></div>
      ${bar(Math.round(100 * Q.i / Q.questions.length))}
      <div class="qtext">${esc(q.q)}</div>
      <div class="opts">${q.options.map((o, i) => `<button class="opt" data-i="${i}"><span class="k">${"ABCD"[i]}</span><span>${esc(o)}</span></button>`).join("")}</div>
      <div id="fb"></div></div>`;
    qb.querySelectorAll(".opt").forEach((b) => b.onclick = () => answer(+b.dataset.i));
  }

  async function answer(i) {
    const Q = S.quiz, q = Q.questions[Q.i], fr = S.lang === "fr"; if (Q.busy) return; Q.busy = true;
    const opts = document.querySelectorAll(".opt"); opts.forEach((b) => b.disabled = true);
    try {
      const r = await api("/api/quiz/answer", {qid: q.id, choice: q.options[i]});
      opts.forEach((b, k) => { if (q.options[k] === r.right) b.classList.add("right"); else if (k === i) b.classList.add("wrong"); });
      Q.res.push({q, ok: r.correct, right: r.right, chosen: q.options[i], why: r.why});
      const last = Q.i === Q.questions.length - 1;
      document.getElementById("fb").innerHTML = `<div class="explain ${r.correct ? "" : "bad"}"><b>${r.correct ? (fr ? "✅ Bien joué !" : "✅ Well done!") : (fr ? "❌ Pas tout à fait" : "❌ Not quite")}</b>
        ${r.correct ? "" : `<div>${fr ? "Bonne réponse" : "Correct answer"} : <b>${esc(r.right)}</b></div>`}<div style="margin-top:6px">${esc(r.why)}</div></div>
        <div class="row" style="margin-top:14px"><button class="btn" id="nx">${last ? (fr ? "Voir mon résultat" : "See my result") : (fr ? "Question suivante →" : "Next question →")}</button></div>`;
      document.getElementById("nx").onclick = () => { Q.busy = false; if (last) renderResult(); else { Q.i++; renderQ(); } };
    } catch (e) { Q.busy = false; opts.forEach((b) => b.disabled = false); toast(e.message); }
  }

  function renderResult() {
    const Q = S.quiz, fr = S.lang === "fr", ok = Q.res.filter((r) => r.ok).length, tot = Q.res.length, pct = Math.round(100 * ok / tot);
    const wrong = Q.res.filter((r) => !r.ok);
    const msg = pct >= 90 ? (fr ? "Excellent, tu gères ! 🔥" : "Excellent! 🔥") : pct >= 60 ? (fr ? "Solide, encore un effort 💪" : "Solid, keep going 💪") : (fr ? "Pas de panique : relis la fiche et retente 🌱" : "No worries: reread the sheet and retry 🌱");
    document.getElementById("qbox").innerHTML = `<div class="card results"><div class="big">${ok}/${tot}</div><h2>${msg}</h2>
      ${wrong.length ? `<div class="review"><b>${fr ? "À revoir" : "To review"} :</b>${wrong.map((r) => `<div><b>${esc(r.q.q)}</b><br>→ ${esc(r.right)}<br><span class="muted small">${esc(r.q.fiche_title[S.lang])}</span></div>`).join("")}</div>` : ""}
      <div class="row" style="justify-content:center"><button class="btn" id="again">${fr ? "Rejouer" : "Play again"}</button>
      <button class="btn ghost" id="tofi">${fr ? "Relire les fiches" : "Back to notes"}</button>
      <button class="btn ghost" id="tocoach">${fr ? "Demander au coach" : "Ask the coach"}</button></div></div>`;
    const sid = Q.s.id;
    document.getElementById("again").onclick = () => route();
    document.getElementById("tofi").onclick = () => go(`#/s/${sid}/fiches`);
    document.getElementById("tocoach").onclick = () => {
      if (wrong.length) S.coachPreset = (fr ? "Je me suis trompé sur : " : "I got these wrong: ") + wrong.slice(0, 3).map((r) => `« ${r.q.q} »`).join(" ; ") + (fr ? ". Peux-tu m'expliquer ?" : ". Can you explain?");
      go(`#/s/${sid}/coach`);
    };
  }

  /* ---------- coach ---------- */
  function tabCoach(box, s) {
    const fr = S.lang === "fr"; const hist = S.chats[s.id] = S.chats[s.id] || [];
    if (!S.coachEnabled) {
      box.innerHTML = `<div class="card"><h3>${t("coach")}</h3><p class="muted">${fr ? "Le coach IA sera disponible dès que l'admin aura ajouté la clé API sur le serveur." : "The AI coach will be available once the admin adds the API key on the server."}</p></div>`; return;
    }
    const pick = s.fiches.slice().sort(() => Math.random() - .5).slice(0, 2);
    const chips = [...pick.map((f) => (fr ? "Explique-moi simplement : " : "Explain simply: ") + f.title[S.lang]),
      fr ? "Interroge-moi sur ce cours" : "Quiz me on this course", fr ? "Quels sont les pièges classiques de l'examen ?" : "What are the classic exam traps?",
      fr ? "Donne-moi un exemple concret" : "Give me a concrete example"];
    box.innerHTML = `<div class="card"><div class="chat" id="chat"></div>
      <div class="chips" id="chips">${chips.map((c) => `<button>${esc(c)}</button>`).join("")}</div>
      <div class="composer"><textarea id="ci" rows="1" maxlength="2000" placeholder="${fr ? "Pose ta question… (Entrée pour envoyer)" : "Ask your question… (Enter to send)"}"></textarea>
      <button class="btn" id="cs">${fr ? "Envoyer" : "Send"}</button></div>
      <div class="small muted" style="margin-top:8px">${fr ? "Le coach s'appuie sur tes fiches. Il peut se tromper : en cas de doute, vérifie avec le support de cours." : "The coach relies on your notes. It can be wrong: double-check with the course slides."}</div></div>`;
    const chat = document.getElementById("chat"), ci = document.getElementById("ci");
    const draw = () => {
      chat.innerHTML = hist.length ? hist.map((m) => `<div class="msg ${m.role === "user" ? "u" : "a"}">${m.role === "user" ? esc(m.content) : md(m.content)}</div>`).join("")
        : `<div class="msg a">${fr ? `Salut ${esc(S.me.name)} ! Je suis ton coach pour <b>${esc(s.name[S.lang])}</b>. Demande-moi d'expliquer une notion, de te donner un exemple concret ou de t'interroger.` : `Hi ${esc(S.me.name)}! I'm your coach for <b>${esc(s.name[S.lang])}</b>. Ask me to explain a concept, give an example, or quiz you.`}</div>`;
      chat.scrollTop = chat.scrollHeight;
    };
    let busy = false;
    const send = async (text) => {
      text = (text || "").trim(); if (!text || busy) return; busy = true; ci.value = "";
      const before = hist.slice(); hist.push({role: "user", content: text}); draw();
      chat.insertAdjacentHTML("beforeend", `<div class="msg a dots" id="typing"><span></span><span></span><span></span></div>`); chat.scrollTop = chat.scrollHeight;
      try {
        const r = await api("/api/coach", {subject: s.id, message: text, history: before});
        hist.push({role: "assistant", content: r.reply});
      } catch (e) { hist.pop(); toast(e.message); ci.value = text; }
      busy = false; draw();
    };
    document.getElementById("cs").onclick = () => send(ci.value);
    ci.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(ci.value); } };
    document.getElementById("chips").querySelectorAll("button").forEach((b) => b.onclick = () => send(b.textContent));
    draw();
    if (S.coachPreset) { const p = S.coachPreset; S.coachPreset = null; send(p); }
  }


  /* ---------- Drive : cours ---------- */
  const fileIcon = (f) => f.folder ? "📁" : /pdf/.test(f.mime) ? "📕" : /presentation|powerpoint/.test(f.mime) ? "📊" : /word|document/.test(f.mime) ? "📄" : /sheet|excel/.test(f.mime) ? "📈" : /^image/.test(f.mime) ? "🖼️" : "📎";
  const fsize = (n) => n == null ? "" : n > 1048576 ? (n / 1048576).toFixed(1) + " Mo" : Math.max(1, Math.round(n / 1024)) + " Ko";
  async function tabDrive(box, s) {
    const fr = S.lang === "fr"; const stack = []; let folder = "";
    async function load() {
      box.innerHTML = `<div class="card muted">${fr ? "Chargement du Drive…" : "Loading Drive…"}</div>`;
      let d;
      try { d = await api(`/api/drive/${s.id}/files` + (folder ? "?folder=" + encodeURIComponent(folder) : "")); }
      catch (e) { box.innerHTML = `<div class="card"><h3>📂 ${t("drive")}</h3><p class="muted">${esc(e.message)}</p></div>`; return; }
      const up = `<div class="card" style="margin-top:14px"><h3 style="font-size:1rem">➕ ${fr ? "Ajouter un cours au Drive" : "Add a file to the Drive"}</h3>
        <div class="small muted" style="margin-bottom:8px">${fr ? "Le fichier sera envoyé dans le dossier" : "The file goes to the folder"} « ${esc(stack.length ? stack[stack.length - 1].name : s.name[S.lang])} » ${fr ? "(PDF, PPTX, DOCX, images…)" : "(PDF, PPTX, DOCX, images…)"}</div>
        <div class="row"><input type="file" id="upf"><button class="btn" id="upb">${fr ? "Envoyer" : "Upload"}</button></div><div class="err" id="upe"></div></div>`;
      box.innerHTML = `<div class="row small" style="margin-bottom:8px">${stack.length ? `<button class="btn ghost" id="back">← ${fr ? "Retour" : "Back"}</button>` : ""}
        <span class="muted">${["", ...stack.map((x) => x.name)].map((n, i) => i ? esc(n) : "📂 " + esc(s.name[S.lang])).join(" / ")}</span></div>
        <div class="card" style="padding:6px 16px">${d.files.length ? d.files.map((f) => `<div class="file-row" data-id="${f.id}" data-dir="${f.folder ? 1 : 0}" data-name="${esc(f.name)}">
          <span class="fi">${fileIcon(f)}</span><span class="fn"><b>${esc(f.name)}</b><span class="muted small">${f.folder ? "" : fsize(f.size)} ${f.modified ? "· " + f.modified.slice(0, 10) : ""} ${f.note ? "· " + esc(f.note) : ""}</span></span>
          ${f.folder ? "" : `<a class="btn ghost" href="/api/drive/file/${f.id}" target="_blank" rel="noopener">${fr ? "Ouvrir" : "Open"}</a><a class="btn ghost" href="/api/drive/file/${f.id}?dl=1">⬇</a>`}</div>`).join("")
          : `<p class="muted" style="padding:14px 4px">${fr ? "Aucun fichier dans ce dossier pour l'instant. Ajoute le premier ci-dessous 👇" : "No files here yet. Add the first one below 👇"}</p>`}</div>${up}`;
      d.folder && (folder = d.folder);
      box.querySelectorAll('.file-row[data-dir="1"]').forEach((r) => { r.style.cursor = "pointer"; r.onclick = () => { stack.push({id: r.dataset.id, name: r.dataset.name}); folder = r.dataset.id; load(); }; });
      const back = document.getElementById("back"); if (back) back.onclick = () => { stack.pop(); folder = stack.length ? stack[stack.length - 1].id : ""; load(); };
      document.getElementById("upb").onclick = async () => {
        const f = document.getElementById("upf").files[0], er = document.getElementById("upe"); er.textContent = "";
        if (!f) { er.textContent = fr ? "Choisis un fichier." : "Pick a file."; return; }
        const fd = new FormData(); fd.append("file", f); if (folder) fd.append("folder", folder);
        const b = document.getElementById("upb"); b.disabled = true; b.textContent = "…";
        try { await api(`/api/drive/${s.id}/upload`, fd); toast(fr ? "Ajouté au Drive ✅" : "Added to Drive ✅"); load(); }
        catch (e) { er.textContent = e.message; b.disabled = false; b.textContent = fr ? "Envoyer" : "Upload"; }
      };
    }
    load();
  }

  /* ---------- Agenda ---------- */
  const pad = (n) => String(n).padStart(2, "0");
  const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  function fmtWhen(e) {
    const d = new Date(e.start), fr = S.lang === "fr";
    const day = d.toLocaleDateString(fr ? "fr-FR" : "en-GB", {weekday: "short", day: "numeric", month: "short"});
    return e.all_day ? day : `${day} · ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
  function subChips(e) {
    return e.subjects.map((id) => `<span class="dot" style="background:${COLORS[id] || "#888"}" title="${esc(id)}"></span>`).join("");
  }
  async function viewAgenda() {
    const fr = S.lang === "fr";
    const [ev, pp] = await Promise.all([api("/api/events"), api("/api/people")]);
    const subj = Object.fromEntries(pp.subjects.map((x) => [x.id, x]));
    let mine = false, sel = ymd(new Date()), cur = new Date(); cur.setDate(1);
    const view = () => ev.events.filter((e) => !mine || e.mine);
    const who = (e) => e.everyone ? (fr ? "Tout le groupe" : "Everyone") : e.people.map((p) => p.name).join(", ");
    const card = (e) => `<div class="ev card" style="border-left:5px solid ${COLORS[e.subjects[0]] || "var(--line)"}">
      <div class="row spread"><div><b>${esc(e.title)}</b> ${e.mine ? `<span class="chip">${fr ? "Me concerne" : "For me"}</span>` : ""}
      <div class="small muted">${fmtWhen(e)}${e.end && !e.all_day ? " → " + e.end.slice(11, 16) : ""} · ${fr ? "par" : "by"} ${esc(e.author)}</div></div>
      ${e.editable ? `<div class="row"><button class="btn ghost" data-edit="${e.id}">✏️</button><button class="btn ghost" data-del="${e.id}">🗑</button></div>` : ""}</div>
      ${e.subjects.length ? `<div class="row small" style="margin-top:6px">${e.subjects.map((id) => subj[id] ? `<span class="chip" style="background:color-mix(in srgb,${COLORS[id]} 16%,var(--card))">${subj[id].emoji} ${esc(subj[id].name[S.lang])}</span>` : "").join("")}</div>` : ""}
      <div class="small" style="margin-top:6px">👥 ${esc(who(e))}</div>${e.description ? `<div class="small muted" style="margin-top:6px;white-space:pre-wrap">${esc(e.description)}</div>` : ""}</div>`;
    function draw() {
      const y = cur.getFullYear(), m = cur.getMonth(), first = new Date(y, m, 1), lead = (first.getDay() + 6) % 7, days = new Date(y, m + 1, 0).getDate();
      const list = view(), byDay = {}; list.forEach((e) => (byDay[e.start.slice(0, 10)] = byDay[e.start.slice(0, 10)] || []).push(e));
      let cells = ""; for (let i = 0; i < lead; i++) cells += "<i></i>";
      for (let d = 1; d <= days; d++) {
        const k = `${y}-${pad(m + 1)}-${pad(d)}`, es = byDay[k] || [];
        cells += `<button class="day ${k === sel ? "sel" : ""} ${k === ymd(new Date()) ? "today" : ""}" data-d="${k}">${d}<span class="dots">${es.slice(0, 4).map((e) => `<span class="dot" style="background:${COLORS[e.subjects[0]] || "#888"}"></span>`).join("")}</span></button>`;
      }
      const title = cur.toLocaleDateString(fr ? "fr-FR" : "en-GB", {month: "long", year: "numeric"});
      const dayEv = byDay[sel] || [], up = list.filter((e) => e.start.slice(0, 10) >= ymd(new Date())).slice(0, 12);
      paint(`<div class="row spread" style="margin-top:22px"><h1 style="margin:0">📅 ${t("agenda")}</h1><button class="btn" id="add">＋ ${fr ? "Ajouter un événement" : "Add event"}</button></div>
        <label class="row small" style="margin:10px 0"><input type="checkbox" id="mine" ${mine ? "checked" : ""}> ${fr ? "N'afficher que ce qui me concerne" : "Only show what concerns me"}</label>
        <div class="grid two" style="align-items:start"><div class="card"><div class="row spread"><button class="btn ghost" id="pm">‹</button><b style="text-transform:capitalize">${title}</b><button class="btn ghost" id="nm">›</button></div>
          <div class="cal-h">${(fr ? ["L", "M", "M", "J", "V", "S", "D"] : ["M", "T", "W", "T", "F", "S", "S"]).map((x) => `<span>${x}</span>`).join("")}</div><div class="cal">${cells}</div>
          <div class="row small muted" style="margin-top:10px">${pp.subjects.map((x) => `<span><span class="dot" style="background:${COLORS[x.id]}"></span> ${esc(x.name[S.lang])}</span>`).join("")}</div></div>
          <div><h3>${new Date(sel + "T12:00").toLocaleDateString(fr ? "fr-FR" : "en-GB", {weekday: "long", day: "numeric", month: "long"})}</h3>
            ${dayEv.length ? dayEv.map(card).join("") : `<p class="muted small">${fr ? "Rien ce jour-là." : "Nothing that day."}</p>`}
            <h3 style="margin-top:18px">${fr ? "À venir" : "Upcoming"}</h3>${up.length ? up.map(card).join("") : `<p class="muted small">${fr ? "Aucun événement à venir." : "No upcoming events."}</p>`}</div></div>`, "agenda");
      document.getElementById("mine").onchange = (e) => { mine = e.target.checked; draw(); };
      document.getElementById("pm").onclick = () => { cur.setMonth(cur.getMonth() - 1); draw(); };
      document.getElementById("nm").onclick = () => { cur.setMonth(cur.getMonth() + 1); draw(); };
      $app.querySelectorAll(".day").forEach((b) => b.onclick = () => { sel = b.dataset.d; draw(); });
      document.getElementById("add").onclick = () => form(null);
      $app.querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => form(ev.events.find((e) => e.id === +b.dataset.edit)));
      $app.querySelectorAll("[data-del]").forEach((b) => b.onclick = async () => {
        if (!confirm(fr ? "Supprimer cet événement ?" : "Delete this event?")) return;
        try { await api("/api/events/" + b.dataset.del, undefined, "DELETE"); viewAgenda(); } catch (e) { toast(e.message); }
      });
    }
    function form(e) {
      const st = e ? e.start : sel + "T09:00", en = e && e.end ? e.end : "";
      const checked = (id) => e ? e.people.some((p) => p.id === id) : false;
      const ov = document.createElement("div"); ov.className = "overlay";
      ov.innerHTML = `<form class="card modal"><h3>${e ? (fr ? "Modifier l'événement" : "Edit event") : (fr ? "Nouvel événement" : "New event")}</h3>
        <div class="field"><label>${fr ? "Titre" : "Title"}</label><input name="title" required maxlength="140" value="${e ? esc(e.title) : ""}" placeholder="${fr ? "Ex : Révision Global Marketing" : "e.g. Global Marketing midterm"}"></div>
        <div class="row"><div class="field" style="flex:1"><label>${fr ? "Début" : "Start"}</label><input type="datetime-local" name="start" required value="${st}"></div>
          <div class="field" style="flex:1"><label>${fr ? "Fin (optionnel)" : "End (optional)"}</label><input type="datetime-local" name="end" value="${en}"></div></div>
        <label class="row small"><input type="checkbox" name="all_day" ${e && e.all_day ? "checked" : ""}> ${fr ? "Toute la journée" : "All day"}</label>
        <div class="field"><label>${fr ? "Matière(s) concernée(s)" : "Subject(s)"}</label><div class="checks">${pp.subjects.map((x) => `<label class="pick" style="--c:${COLORS[x.id]}"><input type="checkbox" name="sub" value="${x.id}" ${e && e.subjects.includes(x.id) ? "checked" : ""}> ${x.emoji} ${esc(x.name[S.lang])}</label>`).join("")}</div></div>
        <div class="field"><label>${fr ? "Personnes concernées" : "People involved"}</label>
          <label class="pick"><input type="checkbox" name="everyone" ${e && e.everyone ? "checked" : ""}> ${fr ? "Tout le groupe" : "Everyone"}</label>
          <div class="checks" id="ppl">${pp.people.map((x) => `<label class="pick"><input type="checkbox" name="ppl" value="${x.id}" ${checked(x.id) || (!e && x.me) ? "checked" : ""}> ${esc(x.name)}</label>`).join("")}</div></div>
        <div class="field"><label>${fr ? "Détails (lieu, chapitres…)" : "Details"}</label><textarea name="description" rows="2" maxlength="1500" style="border:1px solid var(--line);border-radius:12px;padding:10px;background:var(--card)">${e ? esc(e.description) : ""}</textarea></div>
        <div class="err" id="fe"></div><div class="row"><button class="btn">${fr ? "Enregistrer" : "Save"}</button><button type="button" class="btn ghost" id="cx">${fr ? "Annuler" : "Cancel"}</button></div></form>`;
      document.body.appendChild(ov);
      const f = ov.querySelector("form"), tick = () => ov.querySelectorAll("#ppl input").forEach((i) => i.disabled = f.everyone.checked);
      f.everyone.onchange = tick; tick();
      ov.querySelector("#cx").onclick = () => ov.remove(); ov.onclick = (ev2) => { if (ev2.target === ov) ov.remove(); };
      f.onsubmit = async (evt) => {
        evt.preventDefault();
        const body = {title: f.title.value, start: f.start.value, end: f.end.value || null, all_day: f.all_day.checked, description: f.description.value,
          subjects: [...f.querySelectorAll('[name=sub]:checked')].map((i) => i.value), everyone: f.everyone.checked,
          people: [...f.querySelectorAll('[name=ppl]:checked')].map((i) => +i.value)};
        try { await api(e ? "/api/events/" + e.id : "/api/events", body); ov.remove(); toast(fr ? "Agenda mis à jour ✅" : "Agenda updated ✅"); viewAgenda(); }
        catch (er) { ov.querySelector("#fe").textContent = er.message; }
      };
    }
    draw();
  }

  /* ---------- leaderboard ---------- */
  async function viewBoard() {
    const d = await api("/api/leaderboard"), fr = S.lang === "fr";
    const rows = d.board.map((b, i) => `<tr class="${b.me ? "me" : ""}"><td>${["🥇", "🥈", "🥉"][i] || i + 1}</td><td><b>${esc(b.name)}</b></td>
      <td>${b.level.icon} ${b.level.name}</td><td><b>${b.score}</b></td>
      ${d.subjects.map((s) => `<td><div class="mini">${bar(b.subjects[s.id], COLORS[s.id])}<span class="small">${b.subjects[s.id]}%</span></div></td>`).join("")}</tr>`).join("");
    paint(`<h1 style="margin-top:22px">🏆 ${t("board")}</h1><p class="muted">${fr ? "Score = 10 pts par question maîtrisée + 1 pt par bonne réponse. Barres = % de maîtrise par matière." : "Score = 10 pts per mastered question + 1 pt per correct answer. Bars = mastery % per subject."}</p>
      <div class="card tablewrap"><table><thead><tr><th>#</th><th>${fr ? "Nom" : "Name"}</th><th>${fr ? "Niveau" : "Level"}</th><th>Score</th>
      ${d.subjects.map((s) => `<th>${s.emoji} ${esc(s.name[S.lang]).slice(0, 14)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`, "board");
  }

  /* ---------- profile ---------- */
  function viewMe() {
    const fr = S.lang === "fr";
    paint(`<h1 style="margin-top:22px">${esc(S.me.name)}</h1><div class="card" style="max-width:460px"><h3>${fr ? "Changer mon mot de passe" : "Change my password"}</h3>
      <form id="pf" class="setup"><input class="form-inline" style="padding:10px 12px;border:1px solid var(--line);border-radius:12px;background:var(--card)" name="o" type="password" placeholder="${fr ? "Ancien mot de passe" : "Current password"}" required autocomplete="current-password">
      <input style="padding:10px 12px;border:1px solid var(--line);border-radius:12px;background:var(--card)" name="n" type="password" placeholder="${fr ? "Nouveau mot de passe (6+ caractères)" : "New password (6+ chars)"}" required autocomplete="new-password">
      <div class="err" id="pe"></div><button class="btn">${fr ? "Enregistrer" : "Save"}</button></form>
      <hr style="border:0;border-top:1px solid var(--line);margin:18px 0"><button class="btn ghost" id="lo">${t("out")}</button></div>`, "me");
    document.getElementById("pf").onsubmit = async (e) => {
      e.preventDefault(); const f = e.target;
      try { await api("/api/password", {old: f.o.value, new: f.n.value}); toast(fr ? "Mot de passe mis à jour ✅" : "Password updated ✅"); f.reset(); }
      catch (er) { document.getElementById("pe").textContent = er.message; }
    };
    document.getElementById("lo").onclick = async () => { await api("/api/logout", {}); S.me = null; go("#/login"); };
  }

  /* ---------- admin ---------- */
  async function viewAdmin() {
    const d = await api("/api/admin/users");
    paint(`<h1 style="margin-top:22px">⚙️ Admin</h1>
      <div class="card tablewrap"><table><thead><tr><th>Nom</th><th>Identifiant</th><th>Réponses</th><th></th></tr></thead><tbody>
      ${d.users.map((u) => `<tr><td><b>${esc(u.name)}</b>${u.is_admin ? " 👑" : ""}</td><td>${esc(u.username)}</td><td>${u.answers}</td>
        <td><button class="btn ghost" data-reset="${esc(u.username)}">Nouveau mot de passe</button></td></tr>`).join("")}</tbody></table></div>
      <div class="card" style="margin-top:16px"><h3>Ajouter un ami</h3><form id="af" class="form-inline"><input name="n" placeholder="Prénom" required>
      <input name="p" placeholder="Mot de passe (6+)" required minlength="6"><button class="btn">Ajouter</button></form><div class="err" id="ae"></div></div>`, "admin");
    document.getElementById("af").onsubmit = async (e) => {
      e.preventDefault(); try { await api("/api/admin/users", {name: e.target.n.value, password: e.target.p.value}); toast("Ami ajouté ✅"); viewAdmin(); }
      catch (er) { document.getElementById("ae").textContent = er.message; }
    };
    document.querySelectorAll("[data-reset]").forEach((b) => b.onclick = async () => {
      const p = prompt("Nouveau mot de passe pour " + b.dataset.reset + " (6 caractères min) :"); if (!p) return;
      try { await api("/api/admin/reset", {username: b.dataset.reset, password: p}); toast("Mot de passe changé ✅"); } catch (er) { toast(er.message); }
    });
  }

  /* ---------- router ---------- */
  async function route() {
    const h = location.hash || "#/";
    try {
      if (!S.me) { if (h !== "#/login") { history.replaceState(null, "", "#/login"); } return viewLogin(); }
      if (h === "#/login") return go("#/");
      if (h === "#/board") return await viewBoard();
      if (h === "#/agenda") return await viewAgenda();
      if (h === "#/me") return viewMe();
      if (h === "#/admin") return await viewAdmin();
      const m = h.match(/^#\/s\/([\w-]+)\/(fiches|quiz|coach|drive)$/);
      if (m) return await viewSubject(m[1], m[2]);
      return await viewHome();
    } catch (e) { if (e.message !== "auth") { paint(`<div class="card" style="margin-top:22px"><h3>Oups</h3><p>${esc(e.message)}</p></div>`); } }
    window.scrollTo(0, 0);
  }
  async function boot() {
    const d = await api("/api/me");
    S.me = d.user; S.coachEnabled = !!d.coach_enabled; S.coachLimit = d.coach_limit || 40;
  }
  window.addEventListener("hashchange", route);
  boot().then(route).catch(() => { S.me = null; route(); });
})();
