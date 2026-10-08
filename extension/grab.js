const params = new URLSearchParams(location.search);
const MODE = params.get("mode") === "photo" ? "photo" : "product";
const src = params.get("src") || "";
const page = params.get("page") || "";
let fits = [];
let fit = null;      // the selected fit
let chosen = null;   // product mode: selected item
let pins = [];       // photo mode: [{slide, x, y}] in the order placed

$("#modeLabel").textContent = MODE === "photo" ? "Set cover photo" : "Add product image";
$("#productBox").hidden = MODE === "photo";
$("#productFields").hidden = MODE === "photo";
$("#photoBox").hidden = MODE !== "photo";
$("#photoFields").hidden = MODE !== "photo";
$("#img").src = src;
$("#photo").src = src;
$("#pageUrl").textContent = page;
$("#close").onclick = () => window.close();

function msg(text, kind = "") { $("#msg").innerHTML = text ? `<div class="msg ${kind}">${text}</div>` : ""; }

function selectFit() {
  const v = $("#find").value.trim().replace(/^#/, "").split(" ")[0];
  fit = fits.find(x => x.find === v.padStart(3, "0")) || null;
  chosen = null;
  pins = [];
  if (MODE === "product") showItems(); else showPins();
  updateSave();
}

function updateSave() {
  $("#save").disabled = MODE === "product" ? !chosen : !(fit && $("#credit").value.trim());
}

// ---- product mode ----
function showItems() {
  if (!fit) { $("#items").innerHTML = ""; return; }
  $("#items").innerHTML = `<h2>#${fit.find} ${esc(fit.celeb)}: which item is this?</h2>` + fit.items.map(it => `
    <label class="check" for="it${it.slide}"><input type="radio" name="it" id="it${it.slide}" value="${it.slide}">
      <span><span class="lab ${it.label.toLowerCase()}">${it.label.toUpperCase()}</span>${esc(it.brand ? it.brand + " · " : "")}${esc(it.name)}</span>
      ${it.product_url ? `<span class="have">has link</span>` : ""}</label>`).join("");
  $("#items").querySelectorAll("input").forEach(r => r.onchange = () => {
    const it = fit.items.find(i => i.slide === +r.value);
    chosen = { find: fit.find, slide: it.slide, name: it.name };
    updateSave();
  });
}

// ---- photo mode: click the photo to drop numbered pins, one per item in order ----
function showPins() {
  $("#pinwrap").querySelectorAll(".mk").forEach(m => m.remove());
  if (!fit) { $("#pinList").innerHTML = ""; $("#pinHelp").textContent = "Pick the Find # first."; return; }
  if (!$("#credit").value && fit.photo && fit.photo.credit) $("#credit").value = fit.photo.credit;
  const next = fit.items[pins.length];
  $("#pinHelp").textContent = next
    ? `Optional: click the photo where item ${pins.length + 1} is (${next.name}). Skip pins if you like.`
    : "All items pinned.";
  $("#pinList").innerHTML = fit.items.map((it, i) => `<li class="${i < pins.length ? "done" : i === pins.length ? "now" : ""}"><span class="badge">${i + 1}</span>${esc(it.brand ? it.brand + " · " : "")}${esc(it.name)}</li>`).join("");
  pins.forEach((p, i) => {
    const m = document.createElement("span");
    m.className = "mk";
    m.textContent = i + 1;
    m.style.left = p.x * 100 + "%";
    m.style.top = p.y * 100 + "%";
    $("#pinwrap").appendChild(m);
  });
}

$("#photo").addEventListener("click", e => {
  if (!fit || pins.length >= fit.items.length) return;
  const r = e.currentTarget.getBoundingClientRect();
  pins.push({ slide: fit.items[pins.length].slide, x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height });
  showPins();
});
$("#undo").onclick = () => { pins.pop(); showPins(); };
$("#clear").onclick = () => { pins = []; showPins(); };
$("#credit").addEventListener("input", updateSave);

// Any image the browser can show → PNG (products) or JPEG (photos), max 1600px on the long side.
async function convert(url, type) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Couldn't download the image (${res.status}). Try opening the image in its own tab and right-clicking it there.`);
  const bmp = await createImageBitmap(await res.blob());
  const scale = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
  const c = new OffscreenCanvas(Math.round(bmp.width * scale), Math.round(bmp.height * scale));
  const ctx = c.getContext("2d");
  if (type === "image/jpeg") { ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, c.width, c.height); }
  ctx.drawImage(bmp, 0, 0, c.width, c.height);
  const blob = await c.convertToBlob(type === "image/jpeg" ? { type, quality: 0.9 } : { type });
  return GH.b64bytes(new Uint8Array(await blob.arrayBuffer()));
}

$("#save").onclick = async () => {
  $("#save").disabled = true;
  msg("Saving…");
  try {
    if (MODE === "product") {
      const key = `${chosen.find}-${chosen.slide}`;
      const files = [{ path: `images/inbox/${key}.png`, base64: await convert(src, "image/png") }];
      if ($("#useLink").checked && /^https?:/.test(page)) {
        files.push({ path: `images/inbox/${key}.json`, base64: GH.b64text(JSON.stringify({ product_url: page }) + "\n") });
      }
      await GH.commitFiles(files, `Image for #${chosen.find} slide ${chosen.slide}: ${chosen.name}`);
      msg("Saved. The background gets removed and the slides and site update in about 3 minutes.", "ok");
    } else {
      const meta = {
        credit: $("#credit").value.trim(), source_url: page,
        pins: Object.fromEntries(pins.map(p => [String(p.slide), [+p.x.toFixed(4), +p.y.toFixed(4)]]))
      };
      await GH.commitFiles([
        { path: `images/inbox/${fit.find}-photo.jpg`, base64: await convert(src, "image/jpeg") },
        { path: `images/inbox/${fit.find}-photo.json`, base64: GH.b64text(JSON.stringify(meta) + "\n") }
      ], `Cover photo for #${fit.find} ${fit.celeb}`);
      msg(`Saved. #${fit.find}'s cover updates in about 3 minutes.`, "ok");
    }
  } catch (e) {
    msg(esc(e.message), "err");
    $("#save").disabled = false;
  }
};

(async () => {
  try {
    const { doc } = await GH.readFits();
    fits = doc.fits.filter(f => f.status !== "rejected" && f.status !== "posted").sort((a, b) => +b.find - +a.find);
    $("#finds").innerHTML = fits.map(f => `<option value="${f.find} ${esc(f.celeb)}">`).join("");
    $("#find").addEventListener("input", selectFit);
    $("#find").addEventListener("change", () => chrome.storage.local.set({ lastFind: $("#find").value }));
    const last = (await chrome.storage.local.get("lastFind")).lastFind;
    if (last) { $("#find").value = last; selectFit(); }
    $("#find").focus();
  } catch (e) {
    msg(esc(e.message), "err");
  }
})();
