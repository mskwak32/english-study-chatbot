from fastapi import FastAPI
from app.config import settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

logger.info(
    "Application configured: model=%s, timezone=%s",
    settings.model,
    settings.tz
)

app = FastAPI(title="English Study Agent")

@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status":"ok"}