"""
Application configuration.

Loads environment variables (from a local .env file, if present) and
exposes them as simple attributes on a single `settings` object that
the rest of the app can import.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    GEMINI_EMBEDDING_MODEL: str = os.getenv(
        "GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-2"
    )

    # Origins allowed to call this API from the browser during local
    # development. The frontend has no build step and may be served
    # by different static servers (Vite-style dev server on 5173,
    # or Python's http.server on 5500), so both are allowed.
    CORS_ORIGINS = [
    "http://localhost:5173",
    "https://codepilot-ai-zeta.vercel.app",
]


settings = Settings()