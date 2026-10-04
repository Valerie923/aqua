"""Vision providers. `get_provider()` is the only thing the rest of the app calls.

Which provider runs is decided by which API key is set:
  GEMINI_API_KEY     -> Gemini (default; free tier)
  ANTHROPIC_API_KEY  -> Claude
  neither            -> null provider (form still works, AI reading is off)
"""

from app import config
from app.vision.base import VisionProvider

DEFAULT_MODELS = {"gemini": "gemini-2.5-flash", "anthropic": "claude-opus-5"}


def provider_name() -> str:
    if config.GEMINI_API_KEY:
        return "gemini"
    if config.ANTHROPIC_API_KEY:
        return "anthropic"
    return "none"


def model_name() -> str | None:
    name = provider_name()
    return config.VISION_MODEL or DEFAULT_MODELS.get(name)


def get_provider() -> VisionProvider:
    name = provider_name()
    if name == "gemini":
        from app.vision.gemini_provider import GeminiVisionProvider

        return GeminiVisionProvider(api_key=config.GEMINI_API_KEY, model=model_name())
    if name == "anthropic":
        from app.vision.anthropic_provider import AnthropicVisionProvider

        return AnthropicVisionProvider(model=model_name())
    from app.vision.null_provider import NullVisionProvider

    return NullVisionProvider()
