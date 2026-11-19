const chat = document.getElementById("chat");
const form = document.getElementById("ask");
const q = document.getElementById("q");
const send = document.getElementById("send");

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (r.status === 401) { location.href = "/login"; throw new Error("signed out"); }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

async function openSource(id) {
  const s = await api(`/api/source/${id}`);
  document.getElementById("ptitle").textContent = `${s.file} · ${s.ref}`;
  document.getElementById("ptext").textContent = s.text;
  document.getElementById("panel").hidden = false;
}
document.getElementById("pclose").onclick = () => (document.getElementById("panel").hidden = true);

// Render the answer as text, turning [S1] markers into buttons that open the cited passage.
function renderAnswer(text, sources) {
  const byN = Object.fromEntries(sources.map((s) => [s.n, s]));
  const box = el("div", "answer");
  text.split(/(\[S\d+\])/g).forEach((part) => {
    const m = part.match(/^\[S(\d+)\]$/);
    if (m && byN[m[1]]) {
      const b = el("button", "cite", m[1]);
      b.title = `${byN[m[1]].file}, ${byN[m[1]].ref}`;
      b.onclick = () => openSource(byN[m[1]].id);
      box.append(b);
    } else {
      // **bold** from the model becomes <strong>; everything else stays plain text (no HTML injection).
      part.split(/(\*\*[^*]+\*\*)/g).forEach((seg) => {
        const b = seg.match(/^\*\*([^*]+)\*\*$/);
        box.append(b ? el("strong", null, b[1]) : document.createTextNode(seg));
      });
    }
  });
  if (sources.length) {
    const list = el("ol", "sources");
    sources.forEach((s) => {
      const li = el("li");
      const a = el("button", "link", `${s.file} — ${s.ref}`);
      a.onclick = () => openSource(s.id);
      li.value = s.n;
      li.append(a);
      list.append(li);
    });
    box.append(list);
  }
  return box;
}

async function ask(text) {
  document.querySelector(".hint")?.remove();
  chat.append(el("div", "question", text));
  const pending = el("div", "answer muted", "Searching the documents…");
  chat.append(pending);
  chat.scrollTop = chat.scrollHeight;
  send.disabled = true;
  try {
    const r = await api("/api/ask", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question: text }),
    });
    pending.replaceWith(renderAnswer(r.answer, r.sources));
  } catch (e) {
    pending.textContent = `Something went wrong: ${e.message}`;
  } finally {
    send.disabled = false;
    chat.scrollTop = chat.scrollHeight;
  }
}

form.onsubmit = (e) => { e.preventDefault(); const t = q.value.trim(); if (t) { q.value = ""; ask(t); } };
q.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
document.querySelectorAll(".ex").forEach((b) => (b.onclick = () => ask(b.textContent)));

api("/api/me").then((m) => {
  document.getElementById("meta").textContent = `${m.user} · ${m.files} documents · model ${m.model}`;
}).catch(() => {});
