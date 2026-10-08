const params = new URLSearchParams(location.search);
const src = params.get("src") || "";
const page = params.get("page") || "";
let fits = [];
let chosen = null;

$("#img").src = src;
$("#pageUrl").textContent = page;
$("#close").onclick = () => window.close();

function msg(text, kind = "") { $("#msg").innerHTML = text ? `<div class="msg ${kind}">${text}</div>` : ""; }

function showItems() {
  const v = $("#find").value.trim().replace(/^#/, "").split(" ")[0];
  const f = fits.find(x => x.find === v.padStart(3, "0"));
  chosen = null;
  $("#save").disabled = true;
  if (!f) { $("#items").innerHTML = ""; return; }
  $("#items").innerHTML = `<h2>#${f.find} ${esc(f.celeb)}: which item is this?</h2>` + f.items.map(it => `
    <label class="check" for="it${it.slide}"><input type="radio" name="it" id="it${it.slide}" value="${it.slide}">
      <span><span class="lab ${it.label.toLowerCase()}">${it.label.toUpperCase()}</span>${esc(it.brand ? it.brand + " · " : "")}${esc(it.name)}</span>
      ${it.product_url ? `<span class="have">has link</span>` : ""}</label>`).join("");
  $("#items").querySelectorAll("input").forEach(r => r.onchange = () => { chosen = { find: f.find, slide: +r.value, name: f.items[+r.value - 2].name }; $("#save").disabled = false; });
}

// Any image format the browser can show → PNG, max 1600px on the long side.
async function toPng(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Couldn't download the image (${res.status}).`);
  const bmp = await createImageBitmap(await res.blob());
  const scale = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
  const c = new OffscreenCanvas(Math.round(bmp.width * scale), Math.round(bmp.height * scale));
  c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
  const blob = await c.convertToBlob({ type: "image/png" });
  return GH.b64bytes(new Uint8Array(await blob.arrayBuffer()));
}

$("#save").onclick = async () => {
  if (!chosen) return;
  $("#save").disabled = true;
  msg("Saving…");
  try {
    const key = `${chosen.find}-${chosen.slide}`;
    const files = [{ path: `images/inbox/${key}.png`, base64: await toPng(src) }];
    if ($("#useLink").checked && /^https?:/.test(page)) {
      files.push({ path: `images/inbox/${key}.json`, base64: GH.b64text(JSON.stringify({ product_url: page }) + "\n") });
    }
    await GH.commitFiles(files, `Image for #${chosen.find} slide ${chosen.slide}: ${chosen.name}`);
    msg(`Saved. The background gets removed and the slides and site update in about 3 minutes.`, "ok");
  } catch (e) {
    msg(esc(e.message), "err");
    $("#save").disabled = false;
  }
};

(async () => {
  try {
    const { doc } = await GH.readFits();
    fits = doc.fits.filter(f => f.status !== "rejected").sort((a, b) => +b.find - +a.find);
    $("#finds").innerHTML = fits.map(f => `<option value="${f.find} ${esc(f.celeb)}">`).join("");
    $("#find").addEventListener("input", showItems);
    const last = (await chrome.storage.local.get("lastFind")).lastFind;
    if (last) { $("#find").value = last; showItems(); }
    $("#find").addEventListener("change", () => chrome.storage.local.set({ lastFind: $("#find").value }));
    $("#find").focus();
  } catch (e) {
    msg(esc(e.message), "err");
  }
})();
