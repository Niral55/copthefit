// Runs on your Cop the Fit admin page: copies the GitHub connection you saved there into the extension,
// so you only ever enter the token once (in the admin page's GitHub settings).
(() => {
  let s;
  try { s = JSON.parse(localStorage.getItem("ctf-admin") || "{}"); } catch (e) { return; }
  if (!s.token) return;
  const owner = s.owner || location.hostname.split(".")[0];
  const repo = s.repo || location.pathname.split("/")[1] || "copthefit";
  chrome.storage.local.get(["owner", "repo", "token", "branch"], cur => {
    if (cur.token === s.token && cur.owner === owner && cur.repo === repo) return;
    chrome.storage.local.set({ owner, repo, token: s.token, branch: s.branch || "main", site: location.origin + "/" + repo }, () => {
      console.log("Cop the Fit Studio: connected to GitHub using your admin settings.");
    });
  });
})();
