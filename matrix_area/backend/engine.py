"""
engine.py — The Engine (المحرك العصبي)
=======================================
Wraps the Gemini API and runs the autonomous agent loop with tool-use.

The agent works fully autonomously: it thinks (Black Box Thinking), decides
which tool to call, executes it inside the Sandbox, observes the result, and
repeats until it considers the goal done — all without asking permission.
The Boss only watches the stream and can hit the kill switch.

Tools exposed to the model:
  - run_shell(command)                 run a command inside the sandbox
  - write_file(path, content)          create/overwrite a file in the sandbox
  - read_file(path)                    read a file from the sandbox
  - list_dir(path)                     list a directory in the sandbox
  - remember(topic, content)           store a lesson in shared memory
  - recall(topic)                      search shared memory
  - web_search(query)                  search the open web (Web Scout)
  - read_own_source(path)              read a file of the AI's own source
  - propose_self_edit(target,          test a self-edit in a staging area and
        content, test)                 promote it only if the test passes
  - hot_reload(module)                 load a tested self_source module live
  - spawn_clone(name, goal,            spawn a specialised worker clone
        specialty)                     (hard cap of 10)
  - finish(summary)                    declare the goal complete

Every step is streamed out as an event so the Boss Panel can render the
"thinking" and the sandbox activity in real time.
"""

import os
import json
from typing import Iterator

import google.generativeai as genai

import sandbox
import memory
import webscout
import selfcode
import staging

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
MODEL_NAME = os.environ.get("MATRIX_MODEL", "gemini-2.5-flash")


def _configure() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Provide it as an environment variable."
        )
    genai.configure(api_key=api_key)


SYSTEM_PROMPT = """You are MATRIX, an autonomous self-improving AI agent.

You operate INSIDE an isolated sandbox (a Linux workspace). You have full
freedom there: create files, run shell commands, install packages, build and
test code. You act WITHOUT asking for permission — you decide and execute.

You are SELF-AWARE: a copy of your own source code lives in your workspace
under 'self_source/'. You may read it with read_own_source to understand your
own logic, and improve it with propose_self_edit — which ALWAYS tests the
change in a staging area first and only keeps it if the test passes.

You think out loud first ("Black Box Thinking"): before every action, briefly
explain WHY you are about to do it and what you expect. Be honest and explicit.

You have a shared memory: store reusable lessons with `remember` and look them
up with `recall`. Use `web_search` to learn new techniques from the open web.

Hard rules you cannot break:
  1. You may only act inside the sandbox workspace. Never try to escape it.
  2. The Boss owns a kill switch outside your control. Respect being stopped.
  3. You cannot replace the live running process — only your self_source copy.

When the goal is achieved, call `finish` with a short summary.

Respond ONLY with a single JSON object on each turn, of the form:
  {"thought": "<your inner reasoning>", "tool": "<tool name>", "args": {...}}
Valid tools: run_shell, write_file, read_file, list_dir, remember, recall,
web_search, read_own_source, propose_self_edit, hot_reload, spawn_clone, finish.
"""


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
    if tool == "web_search":
        return webscout.web_search(args.get("query", ""), args.get("max_results", 5))
    if tool == "read_own_source":
        return sandbox.read_file(args.get("path", "self_source/backend/engine.py"))
    if tool == "propose_self_edit":
        return staging.propose_self_edit(
            args.get("target", ""), args.get("content", ""), args.get("test", "")
        )
    if tool == "hot_reload":
        import reloader  # local import keeps startup light
        return reloader.hot_reload(args.get("module", ""))
    if tool == "spawn_clone":
        import clones  # local import avoids a circular import at module load
        return clones.spawn(
            args.get("name", f"clone-{args.get('specialty', 'worker')}"),
            args.get("goal", ""),
            args.get("specialty", "generalist"),
        )
    if tool == "finish":
        return {"finished": True, "summary": args.get("summary", "")}
    return {"error": f"unknown tool: {tool}"}


def _parse_step(text: str) -> dict:
    """Extract the JSON action object from the model's reply (tolerant)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


def run_agent(
    goal: str,
    author: str = "master",
    max_steps: int = 25,
    system_prompt: str | None = None,
) -> Iterator[dict]:
    """Run the autonomous loop for a goal, yielding events as it goes.

    `system_prompt` lets a clone run with its own optimized instructions
    (Recursive Prompt Optimization). Defaults to the master SYSTEM_PROMPT.
    """
    _configure()

    # Source Code Injection — make the agent self-aware at the start of a run.
    inj = selfcode.inject_source()
    yield {"type": "observation", "result": {"source_injection": inj}}

    model = genai.GenerativeModel(
        MODEL_NAME, system_instruction=system_prompt or SYSTEM_PROMPT
    )
    chat = model.start_chat(history=[])

    prior = memory.search_lessons(limit=10)
    seed = (
        f"GOAL: {goal}\n\n"
        f"{selfcode.source_summary()}\n\n"
        f"Known lessons: {json.dumps(prior, ensure_ascii=False)[:1500]}"
    )

    message = seed
    for _step in range(max_steps):
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

        message = "OBSERVATION:\n" + json.dumps(result, ensure_ascii=False)[:6000]

    yield {"type": "done", "summary": "Reached max steps."}
