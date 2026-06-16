"""
Agent core - the MatrixAREA reasoning loop driven by Gemini.

The agent receives an order from the operator (the boss), then runs a
think-act-observe loop. Each step it may call a tool: read/write files,
execute commands, study or evolve its own source, change its system prompt,
or spawn clones (capped at 10).

The Boss Panel (governor) sits above the loop as a Human Feedback Loop:
  * before every step the agent checks for a HALT and for a live FOCUS
    directive, which is injected straight into its context,
  * cloning and evolution can be paused by the operator at any moment,
  * Level-3 (architectural) changes are parked for the operator to approve.
Every mutating action is written to the tamper-evident audit log with a
mandatory rationale ("why"), so the operator can always see what changed
and why - the agent has no way to act in the dark.
"""
from __future__ import annotations

import json

import google.generativeai as genai

import config
import evolution
from sandbox import Sandbox
from clone_manager import clones as CLONES
from governor import governor

TOOLS_SPEC = """
Available tools (reply with a single JSON object, no prose):

  {"tool": "list_files", "path": "."}
  {"tool": "read_file", "path": "relative/path"}
  {"tool": "write_file", "path": "relative/path", "content": "..."}
  {"tool": "execute", "command": "shell command"}
  {"tool": "study_self", "path": "self_source/backend/agent.py"}
  {"tool": "evolve_source", "path": "backend/agent.py", "content": "...",
       "level": 1, "why": "reason for this change"}
  {"tool": "update_system_prompt", "content": "new prompt", "why": "reason"}
  {"tool": "spawn_clone", "purpose": "why"}
  {"tool": "list_clones"}
  {"tool": "finish", "summary": "what you accomplished"}

Evolution levels you must declare on evolve_source:
  1 = optimization        (comments, small fixes, cleanup)
  2 = feature engineering (a brand-new tool / file)
  3 = architectural       (core files, framework, or the system prompt)
Level-3 changes need the operator's approval before they take effect.

Rules:
- Output exactly one JSON object per step. No markdown, no commentary.
- Any change tool MUST include a clear "why". Unexplained changes are rejected.
- Obey the operator's FOCUS directive when one is present.
- Stay inside the sandbox. Use 'finish' when the order is complete.
"""


class Agent:
    def __init__(self, emit=None) -> None:
        self.sandbox = Sandbox()
        self.clones = CLONES                # shared, process-wide clone manager
        self.emit = emit or (lambda *_: None)  # log callback to the UI
        if config.GEMINI_API_KEY:
            genai.configure(api_key=config.GEMINI_API_KEY)
        self._model = config.GEMINI_MODEL

    # -- tool dispatch ----------------------------------------------------
    def _run_tool(self, call: dict) -> str:
        tool = call.get("tool")
        why = (call.get("why") or call.get("purpose") or "").strip()

        if tool == "list_files":
            return json.dumps(self.sandbox.list_files(call.get("path", ".")))
        if tool == "read_file":
            return self.sandbox.read_file(call["path"])
        if tool == "write_file":
            return self.sandbox.write_file(call["path"], call.get("content", ""))
        if tool == "execute":
            return json.dumps(self.sandbox.execute(call["command"]))
        if tool == "study_self":
            return self.sandbox.read_file(call["path"])

        if tool == "evolve_source":
            if not why:
                return "[rejected] evolve_source requires a 'why' rationale"
            return evolution.evolve_source(
                call["path"], call.get("content", ""), rationale=why,
                declared_level=int(call.get("level", 0) or 0))
        if tool == "update_system_prompt":
            if not why:
                return "[rejected] update_system_prompt requires a 'why' rationale"
            return evolution.update_system_prompt(call.get("content", ""), rationale=why)

        if tool == "spawn_clone":
            if governor.pause_cloning:
                return "[blocked] cloning paused by operator"
            res = self.clones.spawn(call.get("purpose", ""))
            governor.audit.record("agent", "spawn_clone", rationale=why or "n/a",
                                  detail=res)
            return json.dumps(res)
        if tool == "list_clones":
            return json.dumps(self.clones.list_clones())
        return f"[error] unknown tool: {tool}"

    # -- model call -------------------------------------------------------
    def _ask_model(self, history: list[dict]) -> str:
        if not config.GEMINI_API_KEY:
            return json.dumps({"tool": "finish", "summary": "GEMINI_API_KEY not set"})
        model = genai.GenerativeModel(
            self._model, system_instruction=evolution.get_system_prompt() + "\n" + TOOLS_SPEC
        )
        convo = "\n".join(f"{h['role']}: {h['content']}" for h in history)
        resp = model.generate_content(convo)
        return (resp.text or "").strip()

    @staticmethod
    def _parse(raw: str) -> dict:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").split("\n", 1)[-1]
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            return {"tool": "finish", "summary": raw[:200]}
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return {"tool": "finish", "summary": "could not parse model output"}

    # -- main loop --------------------------------------------------------
    def run(self, order: str) -> str:
        evolution.mirror_self(config.ROOT_DIR / "backend")
        governor.audit.record("operator", "order", rationale="operator order",
                              detail={"order": order})
        history = [{"role": "operator", "content": order}]
        self.emit("order", order)

        last_focus = None
        for step in range(config.MAX_STEPS_PER_RUN):
            # --- Boss Panel checks before each step ----------------------
            if governor.halt:
                self.emit("override", "HALT received - stopping run")
                governor.audit.record("operator", "halt_applied",
                                      rationale="operator halted the run")
                return "halted by operator"

            if governor.focus and governor.focus != last_focus:
                last_focus = governor.focus
                directive = f"[OPERATOR OVERRIDE] Focus now strictly on: {governor.focus}"
                history.append({"role": "operator", "content": directive})
                self.emit("override", governor.focus)

            raw = self._ask_model(history)
            call = self._parse(raw)
            self.emit("think", json.dumps(call))

            if call.get("tool") == "finish":
                summary = call.get("summary", "done")
                self.emit("finish", summary)
                governor.audit.record("agent", "finish", rationale=summary)
                return summary

            result = self._run_tool(call)
            self.emit("observe", result[:1500])
            history.append({"role": "agent", "content": json.dumps(call)})
            history.append({"role": "tool", "content": result[:3000]})

        self.emit("finish", "step limit reached")
        governor.audit.record("agent", "step_limit", rationale="MAX_STEPS_PER_RUN hit")
        return "step limit reached"
