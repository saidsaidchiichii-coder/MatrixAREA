# MatrixAREA

An autonomous agent that lives inside an isolated sandbox. It runs on the
Gemini API, can read and rewrite its own source, change its own system
prompt, execute code, and replicate itself up to a hard limit of 10 clones.
You command it from a classic operator panel and correct it when it goes off
course.

## Architecture

```
backend/
  config.py         paths, model, limits (MAX_CLONES = 10)
  sandbox.py        confined filesystem + command execution (isolation boundary)
  clone_manager.py  self-replication with a hard, locked ceiling
  evolution.py      self-source mirror, prompt edits, snapshots, rollback
  agent.py          Gemini-driven think-act-observe loop
  main.py           FastAPI server + WebSocket operator stream
frontend/
  index.html        operator console (left) + monitor (right)
  styles.css        classic monospace theme, dark / light
  app.js            websocket client + live monitor
```

## Run

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Provide your free Gemini key (never hardcode it):
   ```
   export GEMINI_API_KEY="your-key"
   ```
3. Start the server:
   ```
   python backend/main.py
   ```
4. Open `http://127.0.0.1:8000`

## Path to a full autonomous agent (the 4 stages)

MatrixAREA is built to grow itself, with you in the loop at every dangerous step:

1. **Realization** — `study_self` + `propose_self_upgrade`: it reads its own
   code, sees it is "just a loop", and proposes a stronger system prompt
   (Level 3 — needs your approval).
2. **Tool building** — `web_search` (Exa), `build_tool` / `run_tool`: it writes
   and runs its own Python tools under `sandbox_world/tools/`, becoming a real
   agent instead of a chatbot.
3. **Specialized cloning** — `spawn_clone` with a **role** (`manager`, `coder`,
   `designer`, `researcher`) and `assign_task`: a manager coordinates the
   specialists, all under the hard cap of 10.
4. **UI evolution** — `evolve_ui`: it rewrites the frontend (drafts land in
   `self_source/frontend/` and show up in the **UI DRAFTS** panel) so you get
   richer, real-time results.

### Web search

Set an Exa key to give the agent real search (default provider):

```
export EXA_API_KEY="your-exa-key"        # or MATRIX_SEARCH=exa
```

## The Boss Panel (Human Feedback Loop)

The right-hand panel is your authority over the agent. From it you can:

- **Override / Focus** — push a live directive ("focus only on memory
  management", "stop and review security"); the agent picks it up on its
  next step and obeys it.
- **Pause cloning** — the agent may not spawn new clones while this is on.
- **Pause evolution** — the agent may not touch its own source or prompt.
- **HALT** — stop the current run immediately; **RESUME** to continue.

## The 3 levels of self-evolution

Every change the agent makes to itself is classified:

| Level | Name                 | What it covers                                  | Gate |
|-------|----------------------|-------------------------------------------------|------|
| 1     | Optimization         | comments, small fixes, cleanup                  | auto |
| 2     | Feature engineering  | a brand-new tool / file it writes for itself    | auto |
| 3     | Architectural change | core files, the framework, or the system prompt | **needs your approval** |

Level-3 changes are parked in the Boss Panel's **PENDING APPROVALS** queue.
The agent blocks and waits — it cannot rewrite its own brain (or switch
framework) until you click APPROVE. Toggle `MATRIX_REQUIRE_L3=0` to allow
fully autonomous L3 (not recommended).

## Transparency Ledger (the agent can't act in the dark)

`memory/audit.jsonl` is an **append-only, hash-chained** ledger. Every order,
override, decision, clone and evolution is recorded with a mandatory **"why"**.
Each entry embeds the hash of the previous one, so removing or editing any
line is detectable — the panel shows a live **chain intact / TAMPERED** badge.
The ledger lives *outside* the sandbox, so the agent's confined file tools
cannot reach it.

## Safety boundaries

- The agent can do anything *inside* `sandbox_world/`, nothing outside it.
- Active clones never exceed `MAX_CLONES` (10), enforced with a lock.
- Every self-modification is snapshotted and can be rolled back.
- Level-3 (architectural) changes require explicit operator approval.
- All mutating actions are logged to a tamper-evident audit ledger with a reason.
- Cloning and evolution can be paused, and any run halted, from the Boss Panel.
- The API key is read from the environment only.
