import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.chats import router as chat_router
from app.api.learning_data import router as learning_data_router
from app.api.settings import router as settings_router
from app.config import PROJECT_ROOT, settings
from app.database import initialize_database
from app.instructions import (
    load_agent_instructions,
    load_initial_assessment_instructions,
    load_study_guidelines,
)
from app.llm import OllamaClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

logger.info(
    "Application configured: model=%s, timezone=%s", settings.model, settings.timezone
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """시작 시 DB·지침·LLM 클라이언트를 준비하고 종료 시 클라이언트를 닫습니다.

    Ollama의 준비 상태는 애플리케이션 시작 시 검사하지 않습니다.
    """
    initialize_database(settings.database_url)
    agent_instructions = load_agent_instructions(settings.instructions_path)
    study_guidelines = load_study_guidelines(settings.instructions_path)
    initial_assessment_instructions = load_initial_assessment_instructions(
        settings.instructions_path
    )
    llm_client = OllamaClient(
        settings.ollama_base_url,
        settings.model,
        timeout_seconds=settings.ollama_timeout_seconds,
        keep_alive=settings.ollama_keep_alive,
    )

    app.state.agent_instructions = agent_instructions
    app.state.study_guidelines = study_guidelines
    app.state.initial_assessment_instructions = initial_assessment_instructions
    app.state.llm_client = llm_client

    logger.info("Runtime instruction documents loaded")

    try:
        yield
    finally:
        await llm_client.aclose()


app = FastAPI(
    title="English Study Agent",
    lifespan=lifespan,
)
app.include_router(chat_router)
app.include_router(learning_data_router)
app.include_router(settings_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """애플리케이션의 기본 상태를 반환합니다."""
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=PROJECT_ROOT / "web", html=True), name="web")
