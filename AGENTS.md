# Development Guide

## Project purpose

Build a private English-study chatbot that runs locally on a Raspberry Pi 5.

## Working rules

- Read `plan.ai.md` before starting implementation.
- Default to guidance and explanation; do not implement until the user explicitly asks.
- Explain the purpose, relevant concepts, and expected result before each requested implementation.
- In Korean comments and explanations, write "도구" for tool and "도구 호출" for tool call.
- Implement only the current phase agreed with the user.
- Keep structured learning and chat data in SQLite under `data/`.
- Keep runtime tutor instructions and guidelines under `instructions/`.
- Treat `instructions/AGENT.md` as runtime instructions for the English tutor.
- Load only the fixed tutor instructions and study guidelines from `instructions/`.
- Keep the LLM model and Ollama URL configurable through environment variables.
- Add tests for security boundaries, persistence, and date-based chat behavior.
- Update the phase status and verification notes in `plan.ai.md` after each phase.
- Clear completed-phase items from `TODO.md`.
- Do not run Ruff during incremental work; run Ruff with auto-fix once immediately before the phase commit.
- Commit a completed phase after verification and documentation updates, before starting the next phase.
