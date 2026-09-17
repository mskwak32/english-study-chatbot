# Development Guide

## Project purpose

Build a private English-study chatbot that runs locally on a Raspberry Pi 5.

## Working rules

- Read `plan.ai.md` before starting implementation.
- Explain before implementing; wait for explicit approval.
- Implement only the agreed phase and keep its plan and TODO status current.
- Write "도구" and "도구 호출" in Korean comments and explanations.
- Keep data in `data/` and fixed tutor instructions in `instructions/`.
- Keep the LLM model and Ollama URL configurable through environment variables.
- Test security boundaries, persistence, and date-based chat behavior without duplicate coverage.
- Run Ruff with auto-fix only once, immediately before a phase commit.
- When adding script comments, do not use the code-comment-style skill; explain purpose, inputs, side effects, and safety boundaries clearly enough for a learner.
