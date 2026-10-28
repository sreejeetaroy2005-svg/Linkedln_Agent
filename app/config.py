"""Environment-backed settings; secrets are never exposed by the UI."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

class Settings:
    def __init__(self) -> None:
        self.database_path = os.getenv("DATABASE_PATH", str(ROOT / "data" / "outreach.sqlite3"))
        self.search_provider = os.getenv("SEARCH_PROVIDER", "serper").lower()
        self.serper_api_key = os.getenv("SERPER_API_KEY", "")
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
        self.openai_model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
        self.max_daily_sends = int(os.getenv("MAX_DAILY_SENDS", "15"))
        self.timezone = os.getenv("APP_TIMEZONE", "UTC")
        self.offline_mode_default = os.getenv("OFFLINE_MODE_DEFAULT", "true").lower() in {"1", "true", "yes"}
        if not 1 <= self.max_daily_sends <= 1000:
            raise ValueError("MAX_DAILY_SENDS must be between 1 and 1000")

settings = Settings()
MAX_DAILY_SENDS = 15
