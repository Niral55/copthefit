let DOC = null;
let CFG = null;

function msg(id, text, kind = "") { $(id).innerHTML = text ? `<div class="msg ${kind}">${text}</div>` : ""; }

function showTab(name) {
  document.querySelectorAll("nav button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === name));
  document.querySelectorAll("main").forEach(m => m.hidden = m.id !== "tab-" + name);
  chrome.storage.local.set({ tab: name });
}
document.querySelectorAll("nav button").forEach(b => b.onclick = () => showTab(b.dataset.tab));

const queue = doc => doc.fits.filter(f => f.status === "approved" && f.ig_queue)
  .sort((a, b) => (a.priority ?? 1) - (b.priority ?? 1) || +a.find - +b.find);

function dayLabel(i) {
  const d = new Date(); d.setDate(d.getDate() + i);
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

async function renderQueue() {
  const s = await GH.settings();
  const q = queue(DOC);
  const review = DOC.fits.filter(f => f.status === "review");
  $("#sPosted").textContent = DOC.fits.filter(f => f.status === "posted").length;
  $("#sQueue").textContent = q.length;
  $("#sReview").textContent = review.length;
  $("#rcount").hidden = !review.length;
  $("#rcount").textContent = review.length;
  const ready = CFG && CFG.require_photo ? q.filter(f => f.photo) : q;
  const missing = q.slice(0, 10).filter(f => !f.photo);
  $("#next").innerHTML = ready.slice(0, 6).map((f, i) => `<li><span class="d">${dayLabel(i)}</span><span>#${f.find} <b>${esc(f.celeb)}</b> · ${esc(f.headline)}</span></li>`).join("")
    || `<li><span class="d">–</span><span>${q.length ? "Nothing ready yet. Add cover photos to the fits below to start posting." : "Queue is empty. Approve or add fits to keep posting."}</span></li>`;
  $("#needs").innerHTML = missing.length ? `<h2>Needs a cover photo</h2><ul class="q">${missing.map(f => `<li><span class="d">#${f.find}</span><span><b>${esc(f.celeb)}</b> · ${esc(f.context)}${(f.photo_candidates || []).map((c, i) => ` · <a href="${esc(c.page)}" target="_blank" title="${esc(c.license)}, ${esc(c.taken)}">free photo ${i + 1}</a>`).join("")}${(f.photo_leads || []).map(l => ` · <a href="${esc(l.url)}" target="_blank">${({ video: "video", x: "X", photo: "photo" })[l.kind] || "IG"}: ${esc(l.by || "link")}${l.at ? " " + esc(l.at) : ""}</a>`).join("")}${f.photo_source ? ` · <a href="${esc(f.photo_source)}" target="_blank">article</a>` : ""} · <a href="https://www.youtube.com/results?search_query=${encodeURIComponent(f.celeb + " " + f.context)}" target="_blank">search YouTube</a></span></li>`).join("")}</ul><p class="hint">${CFG && CFG.require_photo ? "Fits without a cover photo are skipped until you add one." : ""} Right-click the photo → <b>Cop the Fit: set as cover photo</b>.</p>` : "";
  const gh = `https://github.com/${s.owner}/${s.repo}`;
  $("#links").innerHTML = [s.site && `<a href="${esc(s.site)}" target="_blank">Open site</a>`,
    `<a href="${gh}/actions" target="_blank">Build &amp; post runs</a>`,
    `<a href="${gh}/blob/${s.branch}/data/fits.json" target="_blank">Data file</a>`].filter(Boolean).join(" · ");
}

async function renderReview() {
  const s = await GH.settings();
  const list = DOC.fits.filter(f => f.status === "review").sort((a, b) => +a.find - +b.find);
  $("#rlist").innerHTML = list.length ? list.map(f => `
    <div class="card" data-find="${f.find}">
      <div class="num">FIND #${f.find} · ${esc(f.category)} · ${esc(f.context)} · ${esc(f.date)}</div>
      <div class="who">${esc(f.celeb)}</div>
      <div>${esc(f.headline)}</div>
      ${s.site ? `<img class="prev" src="${esc(s.site)}/slides/${f.find}/01.jpg" alt="Cover slide preview">` : ""}
      <div class="muted">${esc(f.detail)}</div>
      <ul class="items">${f.items.map(it => `<li><span class="lab ${it.label.toLowerCase()}">${it.label.toUpperCase()}</span>${esc(it.brand ? it.brand + " · " : "")}${esc(it.name)}</li>`).join("")}</ul>
      <div class="muted">Source: ${f.sources.map(x => `<a href="${esc(x.url)}" target="_blank">${esc(x.label)}</a>`).join(", ")}${(f.photo_leads || []).map(l => ` · <a href="${esc(l.url)}" target="_blank">${({ video: "Video", x: "X post", photo: "Photo" })[l.kind] || "IG post"}: ${esc(l.by || "link")}${l.at ? " " + esc(l.at) : ""}</a>`).join("")}</div>
      <div class="row">
        <button class="btn primary" data-act="next" type="button">Approve · post next</button>
        <button class="btn" data-act="approve" type="button">Approve</button>
        <button class="btn danger" data-act="reject" type="button">Reject</button>
      </div>
    </div>`).join("") : `<p class="hint">Nothing to review. The lead finder adds new fits twice a week.</p>`;
  $("#rlist").querySelectorAll("img.prev").forEach(i => i.addEventListener("error", () => i.remove()));
  $("#rlist").querySelectorAll("button[data-act]").forEach(b => b.onclick = () => decide(b.closest(".card").dataset.find, b.dataset.act, b));
}

async function decide(find, act, btn) {
  btn.closest(".card").querySelectorAll("button").forEach(x => x.disabled = true);
  try {
    await GH.updateFits(doc => {
      const f = doc.fits.find(x => x.find === find);
      if (!f) throw new Error(`#${find} isn't in the data file anymore.`);
      f.status = act === "reject" ? "rejected" : "approved";
      f.ig_queue = act !== "reject";
      if (act === "next") f.priority = 0;
      DOC = doc;
    }, `${act === "reject" ? "Reject" : "Approve"} #${find}`);
    await renderQueue();
    await renderReview();
  } catch (e) {
    btn.closest(".card").insertAdjacentHTML("beforeend", `<div class="msg err">${esc(e.message)}</div>`);
    btn.closest(".card").querySelectorAll("button").forEach(x => x.disabled = false);
  }
}

function parseItems(text) {
  const items = [];
  const lines = text.split("\n").map(l => l.trim()).filter(Boolean);
  if (!lines.length) throw new Error("Add at least one item.");
  if (lines.length > 8) throw new Error("8 items max (Instagram allows 10 slides).");
  lines.forEach((line, i) => {
    const p = line.split("|").map(x => x.trim());
    if (p.length < 3) throw new Error(`Line ${i + 1}: use Exact or Similar | brand | item name | link`);
    const label = /^e/i.test(p[0]) ? "Exact" : /^s/i.test(p[0]) ? "Similar" : null;
    if (!label) throw new Error(`Line ${i + 1}: start with Exact or Similar.`);
    if (!p[2]) throw new Error(`Line ${i + 1}: item name is missing.`);
    const it = { slide: i + 2, label, brand: p[1] || "", name: p[2], retailer: "", query: "", product_url: "", note: "" };
    const link = p[3] || "";
    const m = link.match(/^([a-z0-9]+)\s*:\s*(.+)$/i);
    if (/^https?:\/\//.test(link)) it.product_url = link;
    else if (m && !/^https?$/i.test(m[1])) {
      if (!CFG.retailers[m[1].toLowerCase()]) throw new Error(`Line ${i + 1}: unknown retailer "${m[1]}". Use one of: ${Object.keys(CFG.retailers).join(", ")}`);
      it.retailer = m[1].toLowerCase(); it.query = m[2];
    } else if (!link || /^custom$/i.test(link)) it.note = "Custom piece — not for sale";
    else throw new Error(`Line ${i + 1}: the last part should be a link, retailer: search words, or custom.`);
    if (/\b(dupe|fake|faux|replica)\b/i.test(it.name)) throw new Error(`Line ${i + 1}: avoid dupe/fake/faux/replica wording.`);
    items.push(it);
  });
  return items;
}

$("#aSave").onclick = async () => {
  const v = id => $(id).value.trim();
  try {
    for (const [id, name] of [["#aCeleb", "Who"], ["#aContext", "Where"], ["#aDate", "When"], ["#aHead", "Headline"], ["#aDetail", "What they wore"], ["#aSrcLabel", "Source"], ["#aSrcUrl", "Source link"]])
      if (!v(id)) throw new Error(`${name} is empty.`);
    if (!/^https?:\/\//.test(v("#aSrcUrl"))) throw new Error("Source link should start with https://");
    const items = parseItems($("#aItems").value);
    $("#aSave").disabled = true;
    msg("#amsg", "Saving…");
    const find = await GH.updateFits(doc => {
      const n = String(Math.max(0, ...doc.fits.map(f => +f.find)) + 1).padStart(3, "0");
      doc.fits.push({
        find: n, status: "approved", ig_queue: true, priority: $("#aNext").checked ? 0 : 1, added: new Date().toISOString().slice(0, 10),
        celeb: v("#aCeleb"), context: v("#aContext"), date: v("#aDate"), category: $("#aCat").value, timing: "Recent",
        headline: v("#aHead"), detail: v("#aDetail"), tags: [], sources: [{ label: v("#aSrcLabel"), url: v("#aSrcUrl") }],
        note: "", items, posted_at: null, ig_media_id: null, ig_permalink: null
      });
      DOC = doc;
      return n;
    }, `Add fit: ${v("#aCeleb")}`);
    msg("#amsg", `Added as Find #${find}. Slides and the site update in about 3 minutes. Right-click product images to add them to #${find}.`, "ok");
    ["#aCeleb", "#aContext", "#aDate", "#aHead", "#aDetail", "#aSrcLabel", "#aSrcUrl", "#aItems"].forEach(id => $(id).value = "");
    chrome.storage.local.set({ lastFind: find });
    renderQueue();
  } catch (e) {
    msg("#amsg", esc(e.message), "err");
  } finally {
    $("#aSave").disabled = false;
  }
};

$("#sSave").onclick = async () => {
  await chrome.storage.local.set({ owner: $("#sOwner").value, repo: $("#sRepo").value || "copthefit", branch: $("#sBranch").value || "main", token: $("#sToken").value, site: $("#sSite").value });
  msg("#smsg", "Testing…");
  try { await load(); msg("#smsg", `Connected. ${DOC.fits.length} fits in the repo.`, "ok"); }
  catch (e) { msg("#smsg", esc(e.message), "err"); }
};

async function load() {
  const [{ doc }, cfg] = await Promise.all([GH.readFits(), GH.readConfig()]);
  DOC = doc; CFG = cfg;
  const s = await GH.settings();
  if (!s.site && cfg.site_url && !/YOUR-GITHUB-USERNAME/.test(cfg.site_url)) {
    await chrome.storage.local.set({ site: cfg.site_url });
    $("#sSite").value = cfg.site_url;
  }
  $("#who").textContent = `${s.owner}/${s.repo}`;
  await renderQueue();
  await renderReview();
}

(async () => {
  const s = await GH.settings();
  $("#sOwner").value = s.owner; $("#sRepo").value = s.repo; $("#sBranch").value = s.branch; $("#sToken").value = s.token; $("#sSite").value = s.site;
  const { tab } = await chrome.storage.local.get("tab");
  if (!s.owner || !s.token) { showTab("settings"); msg("#smsg", "Connect your GitHub repo to get started."); return; }
  showTab(tab || "queue");
  try { await load(); } catch (e) { msg("#qmsg", esc(e.message), "err"); }
})();
