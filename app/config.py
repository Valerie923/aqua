"""Runtime settings. Everything comes from environment variables so the same
code runs locally, in Docker, and on Render / Hugging Face Spaces."""

import os
from pathlib import Path

ANTHROPIC_API_KEY: str | None = os.environ.get("ANTHROPIC_API_KEY")

# Vision model used to read the photos. Overridable so we can swap models
# without touching code.
VISION_MODEL: str = os.environ.get("VISION_MODEL", "claude-opus-5")

# Where uploaded photos and the SQLite database live.
DATA_DIR: Path = Path(os.environ.get("DATA_DIR", "./data")).resolve()
UPLOAD_DIR: Path = DATA_DIR / "uploads"
DATABASE_URL: str = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'streamcheck.db'}")

# Photos are downscaled before being sent to the model. 1568px is the longest
# edge Claude uses internally; anything larger just costs upload time.
MAX_IMAGE_EDGE: int = 1568
