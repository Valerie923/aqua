"""The one interface every vision provider implements.

Keeping this tiny means we can swap Claude for another vision model (or, as
future work, an on-device model) without touching the API or the frontend.
"""

from dataclasses import dataclass
from typing import Protocol

from app.schemas import VisionPredictions


@dataclass
class Photo:
    role: str  # "upstream" | "downstream" | "context" | "biodiversity"
    media_type: str  # e.g. "image/jpeg"
    data: bytes


class VisionUnavailable(Exception):
    """Raised when no prediction can be made. The message is shown to the citizen."""


class VisionProvider(Protocol):
    name: str

    def analyse(self, photos: list[Photo]) -> VisionPredictions:
        """Read the photos and return one prediction per AI-readable field.

        Must raise VisionUnavailable rather than return made-up values.
        """
        ...
