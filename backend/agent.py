"""
Agent core - the MatrixAREA reasoning loop driven by Gemini.

The agent receives an order from the operator (the boss), then runs a
think-act-observe loop. Each step it may call a tool: read/write files,
execute commands, study or evolve its own source, change its system prompt,
or spawn clones (capped at 10).
"""
from __future__ import annotations

import json

import google.generativeai as genai

import config
import evolution
from sandbox import Sandbox
from clone_manager import CloneManager

TOOLS_SPEC = """
Available tools (reply with a single JSON object, no prose):

  {"tool": "list_files", "path": "."}
  {"tool": "read_file", "path": "relative/path"}
  {"tool": "write_file", "path": "relative/path", "content": "..."}
  {"tool": "execute", "command": "shell command"}
  {"tool": "study_self", "path": "self_source/backend/agent.py"}
  {"tool": "evolve_source", "path": "backend/agent.py", "content": "..."}
  {"tool": "update_system_prompt", "content": "new prompt"}
  {"tool": "spawn_clone", "purpose": "why"}
  {"tool": "list_clones"}
  {"tool": "finish", "summary": "what you accomplished"}

Rules:
- Output exactly one JSON object per step. No markdown, no commentary.
- Stay inside the sandbox. Use 'finish' when the order is complete.
"""


class Agent:
    def __init__(self, emit=None) -> None:
        self.sandbox = Sandbox()
        self.clones = CloneManager()
        self.emit = emit or (lambda *_: None)  # log callback to the UI
        if config.GEMINI_API_KEY:
            genai.configure(api_key=config.GEMINI_API_KEY)
        self._model = config.GEMINI_MODEL

    # -- tool dispatch ----------------------------------------------------
    def _run_tool(self, call: dict) -> str:
        tool = call.get("tool")
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
            return evolution.evolve_source(call["path"], call.get("content", ""))
        if tool == "update_system_prompt":
            return evolution.update_system_prompt(call.get("content", ""))
        if tool == "spawn_clone":
            return json.dumps(self.clones.spawn(call.get("purpose", "")))
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
        history = [{"role": "operator", "content": order}]
        self.emit("order", order)

        for step in range(config.MAX_STEPS_PER_RUN):
            raw = self._ask_model(history)
            call = self._parse(raw)
            self.emit("think", json.dumps(call))

            if call.get("tool") == "finish":
                summary = call.get("summary", "done")
                self.emit("finish", summary)
                return summary

            result = self._run_tool(call)
            self.emit("observe", result[:1500])
            history.append({"role": "agent", "content": json.dumps(call)})
            history.append({"role": "tool", "content": result[:3000]})

        self.emit("finish", "step limit reached")
        return "step limit reached"
