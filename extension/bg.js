// Right-click menus for Cop the Fit.
//  - "Save product to Cop the Fit" (any page): saves the product (name, brand, image, price, link) to the
//    Products tab in the admin, where you add it to a post. AI tidies the name in the background.
//  - "Set as cover photo" / "Add product image" (on an image): add it straight to a post.
importScripts("gh.js");
let SAVES = Promise.resolve(); // one save at a time

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "ctf-save", title: "Save product to Cop the Fit", contexts: ["page", "image", "link", "selection"] });
    chrome.contextMenus.create({ id: "ctf-photo", title: "Cop the Fit: set as cover photo", contexts: ["image"] });
    chrome.contextMenus.create({ id: "ctf-grab", title: "Cop the Fit: add product image", contexts: ["image"] });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "ctf-save") { SAVES = SAVES.then(() => saveProduct(info, tab)); return; }
  if (!["ctf-grab", "ctf-photo"].includes(info.menuItemId)) return;
  const q = new URLSearchParams({
    mode: info.menuItemId === "ctf-photo" ? "photo" : "product",
    src: info.srcUrl || "", page: info.pageUrl || "", title: (tab && tab.title) || ""
  });
  chrome.windows.create({ url: "grab.html?" + q.toString(), type: "popup", width: 480, height: 820 });
});

// Runs inside the store page: read the product from structured data, Open Graph tags and store-specific markup.
function readProduct() {
  const txt = s => (s || "").replace(/\s+/g, " ").trim();
  const meta = n => (document.querySelector(`meta[property="${n}"],meta[name="${n}"]`) || {}).content || "";
  const out = { url: "", title_raw: "", brand: "", image: "", price: "", currency: "" };
  // JSON-LD Product (most stores, StockX, GOAT, Nike, Farfetch, SSENSE…)
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    let data; try { data = JSON.parse(s.textContent); } catch (e) { continue; }
    const all = [].concat(data, ...(Array.isArray(data) ? [] : [data["@graph"] || []]));
    const prod = all.flat().find(x => x && /Product/i.test([].concat(x["@type"] || []).join(" ")));
    if (!prod) continue;
    out.title_raw = txt(prod.name) || out.title_raw;
    out.brand = txt(typeof prod.brand === "string" ? prod.brand : prod.brand && prod.brand.name) || out.brand;
    const img = [].concat(prod.image || [])[0];
    out.image = (typeof img === "string" ? img : img && (img.url || img.contentUrl)) || out.image;
    const offer = [].concat(prod.offers || [])[0] || {};
    out.price = String(offer.price || offer.lowPrice || (offer.priceSpecification || {}).price || "") || out.price;
    out.currency = offer.priceCurrency || out.currency;
    break;
  }
  // Amazon
  if (/(^|\.)amazon\./.test(location.hostname)) {
    out.title_raw = txt((document.querySelector("#productTitle") || {}).textContent) || out.title_raw;
    const by = txt((document.querySelector("#bylineInfo") || {}).textContent);
    out.brand = by.replace(/^(Visit the|Brand:)\s*/i, "").replace(/\s*Store$/i, "") || out.brand;
    const li = document.querySelector("#landingImage, #imgBlkFront");
    if (li) {
      let best = li.getAttribute("data-old-hires") || "";
      try { const dyn = JSON.parse(li.getAttribute("data-a-dynamic-image") || "{}"); best = best || Object.entries(dyn).sort((a, b) => b[1][0] - a[1][0])[0][0]; } catch (e) {}
      out.image = best || li.src || out.image;
    }
    const pr = document.querySelector("#corePrice_feature_div .a-offscreen, #corePriceDisplay_desktop_feature_div .a-offscreen, .a-price .a-offscreen");
    if (pr) { out.price = txt(pr.textContent).replace(/[^0-9.]/g, ""); out.currency = "USD"; }
    const asin = (location.pathname.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/) || [])[1] || (document.querySelector("#ASIN") || {}).value;
    if (asin) out.url = `https://${location.hostname}/dp/${asin}`;
  }
  // eBay
  if (/(^|\.)ebay\./.test(location.hostname)) {
    out.title_raw = txt((document.querySelector(".x-item-title__mainTitle, h1") || {}).textContent) || out.title_raw;
    const im = document.querySelector(".ux-image-carousel-item.active img, .ux-image-carousel-item img");
    if (im) out.image = im.getAttribute("data-zoom-src") || im.src;
    const id = (location.pathname.match(/\/itm\/(?:[^/]+\/)?(\d{9,})/) || [])[1];
    if (id) out.url = `https://www.ebay.com/itm/${id}`;
  }
  out.title_raw = out.title_raw || txt(meta("og:title")) || txt(document.title);
  out.brand = out.brand || txt(meta("product:brand") || meta("og:brand"));
  out.image = out.image || meta("og:image") || meta("twitter:image");
  out.price = out.price || meta("product:price:amount") || meta("og:price:amount");
  out.currency = out.currency || meta("product:price:currency") || meta("og:price:currency");
  out.url = out.url || (document.querySelector('link[rel="canonical"]') || {}).href || location.href;
  try { out.image = new URL(out.image, location.href).href; } catch (e) { out.image = ""; }
  return out;
}

function toast(text, ok) {
  const id = "ctf-toast";
  document.getElementById(id)?.remove();
  const d = document.createElement("div");
  d.id = id; d.textContent = text;
  Object.assign(d.style, { position: "fixed", zIndex: 2147483647, right: "20px", bottom: "20px", maxWidth: "360px", padding: "12px 16px",
    borderRadius: "8px", font: "600 14px/1.4 -apple-system, system-ui, sans-serif", color: "#fff", background: ok ? "#2238C9" : "#B3261E",
    boxShadow: "0 6px 24px rgba(0,0,0,.25)" });
  document.body.appendChild(d);
  setTimeout(() => d.remove(), 5000);
}

async function saveProduct(info, tab) {
  const say = (text, ok = true) => chrome.scripting.executeScript({ target: { tabId: tab.id }, func: toast, args: [text, ok] }).catch(() => {});
  try {
    const [{ result: p }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: readProduct });
    if (info.srcUrl) p.image = info.srcUrl;                       // right-clicked a specific photo: use that one
    if (info.linkUrl && !/(^|\.)(amazon|ebay)\./.test(new URL(tab.url).hostname)) p.url = p.url || info.linkUrl;
    const host = new URL(p.url || tab.url).hostname.replace(/^www\./, "");
    const product = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      url: p.url || tab.url, store: host, title_raw: p.title_raw.slice(0, 300), brand: p.brand.slice(0, 60), name: "",
      image: p.image, price: p.price, currency: p.currency, added: new Date().toISOString(), enriched: null
    };
    await say("Saving to Cop the Fit…");
    const s = await GH.settings();
    for (let attempt = 0; attempt < 6; attempt++) {
      // Read the list at the newest commit, add this product, write it back. If something else saved
      // in between (another save, or the AI tidy-up), GitHub says 409/422: wait a moment and redo it.
      let doc = { products: [] }, sha;
      try { const r = await GH.readJson("data/products.json", await GH.headSha()); doc = r.doc; sha = r.sha; } catch (e) { if (!/ 404/.test(e.message)) throw e; }
      if (doc.products.some(x => x.url === product.url)) { await say("Already saved: it's in the Products tab."); return; }
      doc.products.unshift(product);
      try {
        await GH.req(`/contents/data/products.json`, { method: "PUT", body: JSON.stringify({
          message: `Save product: ${product.title_raw.slice(0, 60)}`, branch: s.branch, ...(sha ? { sha } : {}),
          content: GH.b64text(JSON.stringify(doc, null, 1) + "\n") }) });
        await say(`Saved to Cop the Fit ✓ ${product.brand ? product.brand + " · " : ""}${product.title_raw.slice(0, 60)}`);
        return;
      } catch (e) {
        if (attempt === 5 || !/ 409| 422/.test(e.message)) throw e;
        await new Promise(r => setTimeout(r, 800 + attempt * 700 + Math.random() * 500));
      }
    }
  } catch (e) {
    await say("Couldn't save: " + (e.message || e), false);
  }
}
