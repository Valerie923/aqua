"""Provider used when no API key is configured. It never pretends to see anything."""

from app.schemas import VisionPredictions
from app.vision.base import Photo, VisionUnavailable


class NullVisionProvider:
    name = "none"

    def analyse(self, photos: list[Photo]) -> VisionPredictions:
        raise VisionUnavailable(
            "AI photo reading is not configured on this server (no GEMINI_API_KEY or ANTHROPIC_API_KEY). "
            "You can still complete the form yourself."
        )
