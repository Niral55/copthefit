// Right-click any product image → "Add image to Cop the Fit" → small window to pick the Find # and item.
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "ctf-grab", title: "Add image to Cop the Fit", contexts: ["image"] });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== "ctf-grab") return;
  const q = new URLSearchParams({ src: info.srcUrl || "", page: info.pageUrl || "", title: (tab && tab.title) || "" });
  chrome.windows.create({ url: "grab.html?" + q.toString(), type: "popup", width: 460, height: 760 });
});
