import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.chats import router as chat_router
from app.config import PROJECT_ROOT, settings
from app.database import initialize_database
from app.instructions import load_agent_instructions, load_study_guidelines
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
    initialize_database(settings.database_url)
    agent_instructions = load_agent_instructions(settings.instructions_path)
    study_guidelines = load_study_guidelines(settings.instructions_path)
    llm_client = OllamaClient(
        settings.ollama_base_url,
        settings.model,
        keep_alive=settings.ollama_keep_alive,
    )

    app.state.agent_instructions = agent_instructions
    app.state.study_guidelines = study_guidelines
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


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

app.mount(
    "/",
    StaticFiles(
        directory=PROJECT_ROOT / "web",
        html=True
    ),
    name="web"
)
