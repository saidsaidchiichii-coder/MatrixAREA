// MatrixAREA - operator panel + Boss Panel client.
// Connects to the agent over WebSocket, streams the think-act-observe log,
// drives the Boss Panel overrides, and refreshes the monitor + transparency
// ledger.

(function () {
  "use strict";

  const log = document.getElementById("log");
  const form = document.getElementById("form");
  const order = document.getElementById("order");
  const themeBtn = document.getElementById("theme");

  // -- theme ---------------------------------------------------------------
  const saved = localStorage.getItem("matrix-theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
  syncThemeLabel();
  themeBtn.addEventListener("click", function () {
    const cur = document.documentElement.getAttribute("data-theme");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("matrix-theme", next);
    syncThemeLabel();
  });
  function syncThemeLabel() {
    const cur = document.documentElement.getAttribute("data-theme");
    themeBtn.textContent = cur === "dark" ? "LIGHT" : "DARK";
  }

  // -- helpers -------------------------------------------------------------
  function post(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    }).then(function (r) { return r.json(); });
  }

  // -- log -----------------------------------------------------------------
  function append(kind, payload) {
    const row = document.createElement("div");
    row.className = "entry " + kind;
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = kind;
    const body = document.createElement("span");
    body.textContent = " " + payload;
    row.appendChild(tag);
    row.appendChild(body);
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  }

  // -- websocket -----------------------------------------------------------
  let socket;
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(proto + "://" + location.host + "/ws");
    socket.onopen = function () { append("system", "connection established"); };
    socket.onclose = function () {
      append("system", "connection lost - retrying in 3s");
      setTimeout(connect, 3000);
    };
    socket.onmessage = function (ev) {
      const msg = JSON.parse(ev.data);
      if (msg.kind === "state") { refreshState(); return; }
      append(msg.kind, msg.payload);
      if (msg.kind === "override" || msg.kind === "observe") refreshState();
    };
  }
  connect();

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    const text = order.value.trim();
    if (!text || !socket || socket.readyState !== 1) return;
    socket.send(JSON.stringify({ order: text }));
    order.value = "";
  });
  order.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  // -- Boss Panel : override / control -------------------------------------
  const focusForm = document.getElementById("focus-form");
  const focusInput = document.getElementById("focus");
  focusForm.addEventListener("submit", function (e) {
    e.preventDefault();
    post("/api/override", { focus: focusInput.value.trim() }).then(refreshState);
  });
  document.getElementById("focus-clear").addEventListener("click", function () {
    focusInput.value = "";
    post("/api/override", { focus: "" }).then(refreshState);
  });

  document.getElementById("sw-cloning").addEventListener("change", function (e) {
    post("/api/control", { pause_cloning: e.target.checked }).then(refreshState);
  });
  document.getElementById("sw-evolution").addEventListener("change", function (e) {
    post("/api/control", { pause_evolution: e.target.checked }).then(refreshState);
  });
  document.getElementById("halt").addEventListener("click", function () {
    post("/api/control", { halt: true }).then(refreshState);
  });
  document.getElementById("resume").addEventListener("click", function () {
    post("/api/clear_halt", {}).then(refreshState);
  });

  // -- approvals -----------------------------------------------------------
  function decide(id, approved) {
    const note = approved ? "" : (prompt("Reason for rejection (optional):") || "");
    post("/api/approve", { id: id, approved: approved, note: note }).then(refreshState);
  }

  function renderPending(items) {
    const el = document.getElementById("m-pending");
    el.innerHTML = "";
    if (!items || !items.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "no changes awaiting approval";
      el.appendChild(li);
      return;
    }
    items.forEach(function (p) {
      const li = document.createElement("li");
      li.className = "pending-item";
      const head = document.createElement("div");
      head.className = "pending-head";
      head.textContent = "[" + p.kind + "] " + (p.payload.path || "system prompt");
      const why = document.createElement("div");
      why.className = "pending-why";
      why.textContent = "why: " + (p.rationale || "(none given)");
      const actions = document.createElement("div");
      actions.className = "pending-actions";
      const ok = document.createElement("button");
      ok.textContent = "APPROVE"; ok.className = "ok";
      ok.onclick = function () { decide(p.id, true); };
      const no = document.createElement("button");
      no.textContent = "REJECT"; no.className = "no";
      no.onclick = function () { decide(p.id, false); };
      actions.appendChild(ok); actions.appendChild(no);
      li.appendChild(head); li.appendChild(why); li.appendChild(actions);
      el.appendChild(li);
    });
  }

  // -- monitor state -------------------------------------------------------
  function fillList(el, items) {
    el.innerHTML = "";
    if (!items || !items.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "none";
      el.appendChild(li);
      return;
    }
    items.forEach(function (it) {
      const li = document.createElement("li");
      li.textContent = it;
      el.appendChild(li);
    });
  }

  function renderAudit(entries, integrity) {
    const el = document.getElementById("m-audit");
    el.innerHTML = "";
    const badge = document.getElementById("m-integrity");
    if (integrity) {
      badge.textContent = integrity.intact
        ? "chain intact \u2713" : "TAMPERED \u2717";
      badge.className = "integrity " + (integrity.intact ? "ok" : "bad");
    }
    if (!entries || !entries.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "ledger empty";
      el.appendChild(li);
      return;
    }
    entries.slice().reverse().forEach(function (e) {
      const li = document.createElement("li");
      li.className = "audit-item lvl" + (e.level || 0);
      const meta = document.createElement("div");
      meta.className = "audit-meta";
      meta.textContent = e.ts + "  " + e.actor + "  " + e.action +
                         (e.level ? "  [L" + e.level + "]" : "");
      const why = document.createElement("div");
      why.className = "audit-why";
      why.textContent = e.rationale ? ("why: " + e.rationale) : "";
      li.appendChild(meta);
      if (e.rationale) li.appendChild(why);
      el.appendChild(li);
    });
  }

  function renderRoles(roleMap) {
    const el = document.getElementById("m-roles");
    el.innerHTML = "";
    const keys = Object.keys(roleMap || {});
    if (!keys.length) {
      el.textContent = "no clones active";
      el.className = "roles empty";
      return;
    }
    el.className = "roles";
    keys.forEach(function (k) {
      const chip = document.createElement("span");
      chip.className = "chip role-" + k;
      chip.textContent = k + " \u00d7 " + roleMap[k];
      el.appendChild(chip);
    });
  }

  function renderClones(items) {
    const el = document.getElementById("m-clonelist");
    el.innerHTML = "";
    if (!items || !items.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "swarm empty";
      el.appendChild(li);
      return;
    }
    items.forEach(function (c) {
      const li = document.createElement("li");
      li.className = "clone-item";
      const tasks = (c.tasks || []).length;
      li.innerHTML = "<b>" + c.role + "</b> " + c.id +
        (c.purpose ? " — " + c.purpose : "") +
        (tasks ? " (" + tasks + " task" + (tasks > 1 ? "s" : "") + ")" : "");
      el.appendChild(li);
    });
  }

  function renderTools(toolMap) {
    const el = document.getElementById("m-tools");
    el.innerHTML = "";
    const keys = Object.keys(toolMap || {});
    if (!keys.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "no tools built yet";
      el.appendChild(li);
      return;
    }
    keys.forEach(function (k) {
      const li = document.createElement("li");
      li.textContent = k + (toolMap[k].description ? " — " + toolMap[k].description : "");
      el.appendChild(li);
    });
  }

  function refreshState() {
    fetch("/api/state").then(function (r) { return r.json(); }).then(function (s) {
      document.getElementById("m-model").textContent = s.model;
      document.getElementById("m-key").textContent = s.key_set ? "set" : "missing";
      document.getElementById("m-clones").textContent = s.active_clones + " / " + s.max_clones;
      document.getElementById("m-gate").textContent =
        s.require_l3_approval ? "approval required" : "autonomous";
      document.getElementById("m-search").textContent =
        s.search_provider + (s.search_ready ? " (ready)" : " (no key)");
      const pct = (s.active_clones / s.max_clones) * 100;
      document.getElementById("m-bar").style.width = pct + "%";
      document.getElementById("m-prompt").textContent = s.system_prompt;
      fillList(document.getElementById("m-source"), s.source_files);
      fillList(document.getElementById("m-snaps"), s.snapshots);
      fillList(document.getElementById("m-ui"), s.ui_drafts);
      renderRoles(s.clone_roles);
      renderClones(s.clones);
      renderTools(s.tools);

      // Boss Panel controls
      const c = s.controls || {};
      document.getElementById("m-focus").textContent = c.focus || "none";
      if (document.activeElement.id !== "sw-cloning")
        document.getElementById("sw-cloning").checked = !!c.pause_cloning;
      if (document.activeElement.id !== "sw-evolution")
        document.getElementById("sw-evolution").checked = !!c.pause_evolution;
      const hs = document.getElementById("halt-state");
      hs.textContent = c.halt ? "HALTED" : "running";
      hs.className = "halt-state " + (c.halt ? "halted" : "");

      renderPending(s.pending);
    }).catch(function () {});

    fetch("/api/audit").then(function (r) { return r.json(); }).then(function (a) {
      renderAudit(a.entries, a.integrity);
    }).catch(function () {});
  }
  refreshState();
  setInterval(refreshState, 4000);
})();
