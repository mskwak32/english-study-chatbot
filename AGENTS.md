# Development Guide

## Project purpose

Build a private English-study chatbot that runs locally on a Raspberry Pi 5.

## Working rules

- Read `plan.ai.md` before starting implementation.
- Default to guidance and explanation; do not implement until the user explicitly asks.
- Explain the purpose, relevant concepts, and expected result before each requested implementation.
- Explain non-trivial code in detail; add concise comments where they clarify intent or behavior.
- Show complete production and corresponding test code together in implementation guidance; do not edit either before explicit approval.
- Add a concise module docstring to implementation modules; include one in new-file guidance. Exclude entry points and tests unless useful.
- Group related work into meaningful, testable tasks; avoid one-line increments unless a concept requires it.
- Implement only the current phase agreed with the user.
- Keep structured learning and chat data in SQLite under `data/`.
- Keep runtime tutor instructions and guidelines under `workspace/`.
- Treat `workspace/AGENT.md` as runtime instructions for the English tutor.
- Load only the fixed tutor instructions and study guidelines from `workspace/`.
- Keep the LLM model and Ollama URL configurable through environment variables.
- Add tests for security boundaries, persistence, and date-based chat behavior.
- Update the phase status and verification notes in `plan.ai.md` after each phase.
- Clear completed-phase items from `TODO.md`.
- Commit a completed phase after verification and documentation updates, before starting the next phase.
- Do not silently decide items marked as user decisions.
