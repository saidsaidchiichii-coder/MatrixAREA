// MATRIX — Project Mirror : Boss Panel frontend logic
// Streams the agent's thinking + sandbox activity, polls resources & clones,
// and wires the kill switch. The Boss watches; the AI acts.

const $ = (id) => document.getElementById(id);
const thinkingEl = $("thinking");
const sandboxEl = $("sandbox");
const statusEl = $("status");

function addThought(text) {
  const d = document.createElement("div");
  d.className = "thought";
  d.textContent = text;
  thinkingEl.appendChild(d);
  thinkingEl.scrollTop = thinkingEl.scrollHeight;
}

function addAction(tool, args) {
  const d = document.createElement("div");
  d.className = "action";
  d.textContent = `→ ${tool}(${JSON.stringify(args).slice(0, 120)})`;
  sandboxEl.appendChild(d);
  sandboxEl.scrollTop = sandboxEl.scrollHeight;
}

function addObservation(result) {
  const d = document.createElement("div");
  d.className = "obs";
  let txt = typeof result === "string" ? result : JSON.stringify(result, null, 2);
  d.textContent = txt.slice(0, 1200);
  sandboxEl.appendChild(d);
  sandboxEl.scrollTop = sandboxEl.scrollHeight;
}

// ---- Execute a strategic goal (Server-Sent Events stream) ----
async function runGoal() {
  const goal = $("goal").value.trim();
  if (!goal) return;
  thinkingEl.innerHTML = "";
  sandboxEl.innerHTML = "";
  statusEl.textContent = "running…";

  const resp = await fetch("/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goal }),
  });

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) {
      const line = part.replace(/^data: /, "").trim();
      if (!line) continue;
      let ev;
      try { ev = JSON.parse(line); } catch { continue; }
      if (ev.type === "thinking") addThought(ev.text);
      else if (ev.type === "action") addAction(ev.tool, ev.args);
      else if (ev.type === "observation") addObservation(ev.result);
      else if (ev.type === "done") { statusEl.textContent = "done"; addThought("✅ " + (ev.summary || "")); }
      else if (ev.type === "error") { statusEl.textContent = "error"; addObservation("⚠ " + ev.message); }
    }
  }
  if (statusEl.textContent === "running…") statusEl.textContent = "idle";
}

// ---- Kill switch ----
async function kill() {
  await fetch("/kill", { method: "POST" });
  statusEl.textContent = "KILLED";
}
async function revive() {
  await fetch("/revive", { method: "POST" });
  statusEl.textContent = "idle";
}

// ---- Resource Mirror (poll every 2s) ----
async function pollResources() {
  try {
    const r = await (await fetch("/resources")).json();
    $("cpuBar").style.width = r.cpu_percent + "%";
    $("cpuVal").textContent = r.cpu_percent.toFixed(0) + "%";
    $("ramBar").style.width = r.ram_percent + "%";
    $("ramVal").textContent = r.ram_percent.toFixed(0) + "%";
    $("procVal").textContent = r.process_count;
  } catch {}
}

// ---- Clones status (poll every 3s) ----
async function pollClones() {
  try {
    const r = await (await fetch("/clones")).json();
    $("cloneCount").textContent = `${r.active} / ${r.max}`;
    $("cloneList").innerHTML = r.clones
      .map((c) => `<div class="clone-item"><span>${c.name} · ${c.specialty}</span><span>${c.status}</span></div>`)
      .join("") || '<div class="clone-item"><span>no active clones</span></div>';
  } catch {}
}

$("runBtn").addEventListener("click", runGoal);
$("killBtn").addEventListener("click", kill);
$("reviveBtn").addEventListener("click", revive);

setInterval(pollResources, 2000);
setInterval(pollClones, 3000);
pollResources();
pollClones();
