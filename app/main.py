"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.routes import router
from app.config import settings
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="code2career_ai Learner Discovery",
    description="Responsible public-search discovery with human-controlled outreach.",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "code2career_ai Learner Discovery", "docs": "/docs", "offline_demo_default": str(settings.offline_mode_default).lower()}

