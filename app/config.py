"""Runtime settings. Everything comes from environment variables so the same
code runs locally, in Docker, and on Render / Hugging Face Spaces."""

import os
from pathlib import Path

# Set one of these. Gemini is preferred if both are present (free tier).
GEMINI_API_KEY: str | None = os.environ.get("GEMINI_API_KEY")
ANTHROPIC_API_KEY: str | None = os.environ.get("ANTHROPIC_API_KEY")

# Optional override of the vision model. If unset, each provider uses its
# default (see app/vision/__init__.py).
VISION_MODEL: str | None = os.environ.get("VISION_MODEL") or None

# Where uploaded photos and the SQLite database live.
DATA_DIR: Path = Path(os.environ.get("DATA_DIR", "./data")).resolve()
UPLOAD_DIR: Path = DATA_DIR / "uploads"
DATABASE_URL: str = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'streamcheck.db'}")

# Photos are downscaled before being sent to the model. Vision models work
# at roughly this resolution internally; anything larger just costs upload time.
MAX_IMAGE_EDGE: int = 1568

# Public HAPI FHIR test server used by "Send to FHIR sandbox".
FHIR_SERVER_URL: str = os.environ.get("FHIR_SERVER_URL", "https://hapi.fhir.org/baseR4")
