import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import initialize_database
from app.workspace import load_agent_instructions, load_study_guidelines

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

logger.info(
    "Application configured: model=%s, timezone=%s", settings.model, settings.tz
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database(settings.database_url)
    agent_instructions = load_agent_instructions(settings.workspace_path)
    study_guidelines = load_study_guidelines(settings.workspace_path)

    app.state.agent_instructions = agent_instructions
    app.state.study_guidelines = study_guidelines

    logger.info("Workspace runtime documents loaded")

    yield


app = FastAPI(
    title="English Study Agent",
    lifespan=lifespan,
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
