import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import initialize_database
from app.workspace import (
    initialize_learning_documents,
    load_agent_instructions,
)

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
    created_files = initialize_learning_documents(settings.workspace_path)

    agent_instructions = load_agent_instructions(settings.workspace_path)

    app.state.agent_instructions = agent_instructions

    logger.info(
        "Workspace initialized: created_files=%s",
        created_files,
    )

    yield


app = FastAPI(
    title="English Study Agent",
    lifespan=lifespan,
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
