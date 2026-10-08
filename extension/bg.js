// Right-click an image → add it to a Cop the Fit post.
//  - "Set as cover photo": the photo of the look, shown on the first slide with numbered item pins.
//  - "Add product image": a product shot for one item (background gets removed).
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "ctf-photo", title: "Cop the Fit: set as cover photo", contexts: ["image"] });
  chrome.contextMenus.create({ id: "ctf-grab", title: "Cop the Fit: add product image", contexts: ["image"] });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!["ctf-grab", "ctf-photo"].includes(info.menuItemId)) return;
  const q = new URLSearchParams({
    mode: info.menuItemId === "ctf-photo" ? "photo" : "product",
    src: info.srcUrl || "", page: info.pageUrl || "", title: (tab && tab.title) || ""
  });
  chrome.windows.create({ url: "grab.html?" + q.toString(), type: "popup", width: 480, height: 820 });
});
