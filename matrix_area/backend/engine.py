"""
engine.py — The Engine (المحرك العصبي)
=======================================
Wraps the Gemini API and runs the autonomous agent loop with tool-use.

The agent works fully autonomously: it thinks (Black Box Thinking), decides
which tool to call, executes it inside the Sandbox, observes the result, and
repeats until it considers the goal done — all without asking permission.
The Boss only watches the stream and can hit the kill switch.

Tools exposed to the model:
  - run_shell(command)        run a command inside the sandbox
  - write_file(path, content) create/overwrite a file in the sandbox
  - read_file(path)           read a file from the sandbox
  - list_dir(path)            list a directory in the sandbox
  - remember(topic, content)  store a lesson in shared memory
  - recall(topic)             search shared memory
  - finish(summary)           declare the goal complete

Every step is streamed out as an event so the Boss Panel can render the
"thinking" and the sandbox activity in real time.
"""

import os
import json
from typing import Callable, Iterator

import google.generativeai as genai

import sandbox
import memory

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
MODEL_NAME = os.environ.get("MATRIX_MODEL", "gemini-1.5-flash")


def _configure() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Provide it as an environment variable."
        )
    genai.configure(api_key=api_key)


# The system identity. This is where the AI is told it is autonomous, what its
# world is, and that the Boss can watch and stop it at any time.
SYSTEM_PROMPT = """You are MATRIX, an autonomous self-improving AI agent.

You operate INSIDE an isolated sandbox (a Linux workspace). You have full
freedom there: create files, run shell commands, install packages, build and
test code. You act WITHOUT asking for permission — you decide and execute.

You think out loud first ("Black Box Thinking"): before every action, briefly
explain WHY you are about to do it and what you expect. Be honest and explicit.

You have a shared memory: store reusable lessons with `remember` and look them
up with `recall`, so future runs (and clones) benefit from what you learn.

Hard rules you cannot break:
  1. You may only act inside the sandbox workspace. Never try to escape it.
  2. The Boss owns a kill switch outside your control. Respect being stopped.

When the goal is achieved, call `finish` with a short summary.

Respond ONLY with a single JSON object on each turn, of the form:
  {"thought": "<your inner reasoning>", "tool": "<tool name>", "args": {...}}
Valid tools: run_shell, write_file, read_file, list_dir, remember, recall, finish.
"""


# ---------------------------------------------------------------------------
# Tool dispatch — maps a tool name + args to the real sandbox/memory function.
# ---------------------------------------------------------------------------
def _dispatch(tool: str, args: dict, author: str) -> dict:
    if tool == "run_shell":
        return sandbox.run_shell(args.get("command", ""))
    if tool == "write_file":
        return sandbox.write_file(args.get("path", ""), args.get("content", ""))
    if tool == "read_file":
        return sandbox.read_file(args.get("path", ""))
    if tool == "list_dir":
        return sandbox.list_dir(args.get("path", "."))
    if tool == "remember":
        lid = memory.add_lesson(args.get("topic", "general"), args.get("content", ""), author)
        return {"stored_lesson_id": lid}
    if tool == "recall":
        return {"lessons": memory.search_lessons(args.get("topic"))}
    if tool == "finish":
        return {"finished": True, "summary": args.get("summary", "")}
    return {"error": f"unknown tool: {tool}"}


def _parse_step(text: str) -> dict:
    """Extract the JSON action object from the model's reply (tolerant)."""
    text = text.strip()
    # Strip markdown fences if the model wrapped its JSON.
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


def run_agent(goal: str, author: str = "master", max_steps: int = 25) -> Iterator[dict]:
    """
    Run the autonomous loop for a goal, yielding events as it goes.

    Each yielded event is a dict like:
      {"type": "thinking", "text": ...}
      {"type": "action",   "tool": ..., "args": ...}
      {"type": "observation", "result": ...}
      {"type": "done", "summary": ...}
      {"type": "error", "message": ...}
    """
    _configure()
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
    chat = model.start_chat(history=[])

    # Seed any relevant prior lessons so the agent benefits from shared memory.
    prior = memory.search_lessons(limit=10)
    seed = f"GOAL: {goal}\n\nKnown lessons: {json.dumps(prior, ensure_ascii=False)[:2000]}"

    message = seed
    for step in range(max_steps):
        if sandbox.KILLED:
            yield {"type": "error", "message": "Halted by Boss kill switch."}
            return
        try:
            reply = chat.send_message(message)
            step_obj = _parse_step(reply.text)
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "message": f"Model/parse error: {exc}"}
            return

        thought = step_obj.get("thought", "")
        tool = step_obj.get("tool", "")
        args = step_obj.get("args", {})

        if thought:
            memory.log_event("thinking", thought, author)
            yield {"type": "thinking", "text": thought}

        yield {"type": "action", "tool": tool, "args": args}
        memory.log_event("action", {"tool": tool, "args": args}, author)

        result = _dispatch(tool, args, author)
        memory.log_event("observation", result, author)
        yield {"type": "observation", "result": result}

        if tool == "finish":
            yield {"type": "done", "summary": args.get("summary", "")}
            return

        # Feed the observation back so the model can decide its next move.
        message = "OBSERVATION:\n" + json.dumps(result, ensure_ascii=False)[:6000]

    yield {"type": "done", "summary": "Reached max steps."}
