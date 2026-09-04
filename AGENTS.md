# Development Guide

## Project purpose

Build a private English-study chatbot that runs locally on a Raspberry Pi 5.

## Working rules

- Read `plan.ai.md` before starting implementation.
- Default to guidance and explanation; do not implement until the user explicitly asks.
- Explain the purpose, relevant concepts, and expected result before each requested implementation.
- Group related work into meaningful, testable tasks; avoid one-line increments unless a concept requires it.
- Implement only the current phase agreed with the user.
- Keep long-term study data under `workspace/` and chat data under `data/`.
- Treat `workspace/AGENT.md` as runtime instructions for the English tutor.
- Restrict application file tools to the configured workspace root.
- Keep the LLM model and Ollama URL configurable through environment variables.
- Add tests for security boundaries, persistence, and date-based chat behavior.
- Update the phase status and verification notes in `plan.ai.md` after each phase.
- Clear completed-phase items from `TODO.md`.
- Do not silently decide items marked as user decisions.
