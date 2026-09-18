"""Vision providers. `get_provider()` is the only thing the rest of the app calls."""

from app import config
from app.vision.base import VisionProvider


def get_provider() -> VisionProvider:
    if config.ANTHROPIC_API_KEY:
        from app.vision.anthropic_provider import AnthropicVisionProvider

        return AnthropicVisionProvider(model=config.VISION_MODEL)
    from app.vision.null_provider import NullVisionProvider

    return NullVisionProvider()
