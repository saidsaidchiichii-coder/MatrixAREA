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

## Safety boundaries

- The agent can do anything *inside* `sandbox_world/`, nothing outside it.
- Active clones never exceed `MAX_CLONES` (10), enforced with a lock.
- Every self-modification is snapshotted and can be rolled back.
- The API key is read from the environment only.
