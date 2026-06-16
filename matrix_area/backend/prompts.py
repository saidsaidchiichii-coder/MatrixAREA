"""
prompts.py — Recursive Prompt Optimization (تحسين البرومبت ذاتياً)
=================================================================
Generates the system prompt for a clone based on its specialty and goal. The
master agent knows better than a human which exact instructions a worker clone
needs, so it can call generate_clone_prompt to spin up well-tuned workers.

A template is always available offline. If a Gemini key is present, the prompt
can additionally be refined by the model itself (truly recursive).
"""

import os

BASE = (
    "You are a {specialty} clone of MATRIX, working autonomously inside an "
    "isolated sandbox. Think out loud before acting. Your sub-goal:\n{goal}\n\n"
    "Use the available tools to accomplish it efficiently, write light code that "
    "does not waste CPU/RAM, store any reusable lesson with `remember`, and call "
    "`finish` with a short result summary when done."
)

SPECIALTY_HINTS = {
    "developer": "Focus on clean, well-tested, modular code.",
    "designer": "Focus on clear, professional UI/UX (dark, minimal, Grok-like).",
    "qa": "Focus on finding bugs and edge cases; write and run tests.",
    "security": "Focus on safety, input validation, and staying inside the sandbox.",
    "architect": "Focus on structure, performance and maintainability.",
    "generalist": "Balance speed and quality.",
}


def generate_clone_prompt(specialty: str, goal: str, use_model: bool = False) -> str:
    """Build a tailored system prompt for a clone (optionally model-refined)."""
    hint = SPECIALTY_HINTS.get(specialty, SPECIALTY_HINTS["generalist"])
    prompt = BASE.format(specialty=specialty, goal=goal) + "\nSpecialty note: " + hint

    if use_model and os.environ.get("GEMINI_API_KEY"):
        try:
            import google.generativeai as genai

            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            model = genai.GenerativeModel(os.environ.get("MATRIX_MODEL", "gemini-2.5-flash"))
            refined = model.generate_content(
                "Improve this agent system prompt to be more precise and effective. "
                "Keep it under 120 words. Return only the prompt:\n\n" + prompt
            )
            if refined.text:
                return refined.text.strip()
        except Exception:
            pass  # fall back to the template silently

    return prompt
