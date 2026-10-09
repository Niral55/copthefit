// Small GitHub REST helper for the copthefit repo (contents + git data APIs).
const GH = {
  async settings() {
    const s = await chrome.storage.local.get(["owner", "repo", "branch", "token", "site"]);
    return {
      owner: (s.owner || "").trim(), repo: (s.repo || "copthefit").trim(), branch: (s.branch || "main").trim(),
      token: (s.token || "").trim(), site: (s.site || "").trim().replace(/\/$/, "")
    };
  },

  async req(path, opts = {}) {
    const s = await GH.settings();
    if (!s.owner || !s.token) throw new Error("Not connected yet. Open your Cop the Fit admin page once (it connects the extension automatically), then try again.");
    const r = await fetch(`https://api.github.com/repos/${s.owner}/${s.repo}${path}`, {
      ...opts,
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${s.token}`,
        "X-GitHub-Api-Version": "2022-11-28",
        ...(opts.body ? { "Content-Type": "application/json" } : {})
      }
    });
    if (!r.ok) {
      const t = await r.text();
      const hint = r.status === 401 ? " (token wrong or expired)" : r.status === 404 ? " (check username/repo, and that the token can access this repo)" : "";
      throw new Error(`GitHub ${r.status}${hint}: ${t.slice(0, 140)}`);
    }
    return r.status === 204 ? null : r.json();
  },

  b64decode(b64) {
    const bin = atob(b64.replace(/\n/g, ""));
    return new TextDecoder().decode(Uint8Array.from(bin, c => c.charCodeAt(0)));
  },
  b64bytes(bytes) {
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(s);
  },
  b64text(t) { return GH.b64bytes(new TextEncoder().encode(t)); },

  async readJson(path) {
    const s = await GH.settings();
    const f = await GH.req(`/contents/${path}?ref=${encodeURIComponent(s.branch)}`);
    const raw = f.content ? f.content : (await GH.req(`/git/blobs/${f.sha}`)).content;
    return { doc: JSON.parse(GH.b64decode(raw)), sha: f.sha };
  },

  readFits() { return GH.readJson("data/fits.json"); },
  readConfig() { return GH.readJson("config.json").then(r => r.doc); },

  // Read data/fits.json, let mutate() change it, write it back. Retries once if someone else saved first.
  async updateFits(mutate, message) {
    const s = await GH.settings();
    for (let attempt = 0; attempt < 2; attempt++) {
      const { doc, sha } = await GH.readFits();
      const result = mutate(doc);
      try {
        await GH.req(`/contents/data/fits.json`, {
          method: "PUT",
          body: JSON.stringify({ message, sha, branch: s.branch, content: GH.b64text(JSON.stringify(doc, null, 1) + "\n") })
        });
        return result;
      } catch (e) {
        if (attempt === 1 || !/ 409| 422/.test(e.message)) throw e;
      }
    }
  },

  // Commit several files in one commit. files: [{ path, base64 }]
  async commitFiles(files, message) {
    const s = await GH.settings();
    const ref = await GH.req(`/git/ref/heads/${encodeURIComponent(s.branch)}`);
    const head = ref.object.sha;
    const commit = await GH.req(`/git/commits/${head}`);
    const tree = [];
    for (const f of files) {
      const blob = await GH.req(`/git/blobs`, { method: "POST", body: JSON.stringify({ content: f.base64, encoding: "base64" }) });
      tree.push({ path: f.path, mode: "100644", type: "blob", sha: blob.sha });
    }
    const t = await GH.req(`/git/trees`, { method: "POST", body: JSON.stringify({ base_tree: commit.tree.sha, tree }) });
    const c = await GH.req(`/git/commits`, { method: "POST", body: JSON.stringify({ message, tree: t.sha, parents: [head] }) });
    await GH.req(`/git/refs/heads/${encodeURIComponent(s.branch)}`, { method: "PATCH", body: JSON.stringify({ sha: c.sha }) });
    return c.sha;
  }
};

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (sel, root = document) => root.querySelector(sel);
