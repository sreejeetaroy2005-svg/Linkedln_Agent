"""FastAPI application entrypoint."""
from fastapi import FastAPI

from app.api.routes import router
from app.config import settings
from app.db.database import init_db

app = FastAPI(title="code2career_ai Learner Discovery", description="Responsible public-search discovery with human-controlled outreach.", version="1.0.0")
app.include_router(router)

@app.on_event("startup")
def startup() -> None:
    init_db()

@app.get("/")
def root() -> dict[str, str]:
    return {"name": "code2career_ai Learner Discovery", "docs": "/docs", "offline_demo_default": str(settings.offline_mode_default).lower()}
