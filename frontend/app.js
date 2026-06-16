// MatrixAREA - operator panel client.
// Connects to the agent over WebSocket, streams the think-act-observe log,
// and refreshes the monitor state.

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

  function refreshState() {
    fetch("/api/state").then(function (r) { return r.json(); }).then(function (s) {
      document.getElementById("m-model").textContent = s.model;
      document.getElementById("m-key").textContent = s.key_set ? "set" : "missing";
      document.getElementById("m-clones").textContent = s.active_clones + " / " + s.max_clones;
      const pct = (s.active_clones / s.max_clones) * 100;
      document.getElementById("m-bar").style.width = pct + "%";
      document.getElementById("m-prompt").textContent = s.system_prompt;
      fillList(document.getElementById("m-source"), s.source_files);
      fillList(document.getElementById("m-snaps"), s.snapshots);
    }).catch(function () {});
  }
  refreshState();
  setInterval(refreshState, 5000);
})();
