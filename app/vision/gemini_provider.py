"""Gemini (Google AI API) vision provider.

Sends the photos plus the system prompt and asks for JSON constrained to the
`VisionPredictions` schema. The SDK parses and validates the answer against the
Pydantic model, so a malformed reply becomes an error rather than a bad prediction.
"""

from google import genai
from google.genai import errors, types

from app.schemas import VisionPredictions
from app.vision.base import Photo, VisionUnavailable
from app.vision.prompt import SYSTEM_PROMPT, USER_INSTRUCTION

ROLE_LABELS = {
    "upstream": "Photo 1 — looking UPSTREAM",
    "downstream": "Photo 2 — looking DOWNSTREAM",
    "context": "Photo 3 — surrounding context",
    "biodiversity": "Photo 4 — biodiversity element (optional extra)",
}


class GeminiVisionProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.model = model
        self.client = genai.Client(api_key=api_key)

    def _contents(self, photos: list[Photo]) -> list:
        parts: list = []
        for photo in photos:
            parts.append(ROLE_LABELS.get(photo.role, photo.role))
            parts.append(types.Part.from_bytes(data=photo.data, mime_type=photo.media_type))
        parts.append(USER_INSTRUCTION)
        return parts

    def analyse(self, photos: list[Photo]) -> VisionPredictions:
        if not photos:
            raise VisionUnavailable("No photos were provided.")
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=self._contents(photos),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=VisionPredictions,
                    temperature=0.2,  # we want a careful reader, not a creative one
                ),
            )
        except errors.ClientError as e:
            if e.code == 429:
                raise VisionUnavailable("The AI service is busy (free-tier limit). Please try again in a minute.") from e
            if e.code in (401, 403):
                raise VisionUnavailable("The AI service rejected our API key.") from e
            raise VisionUnavailable(f"The AI service could not process these photos ({e.code}).") from e
        except errors.ServerError as e:
            raise VisionUnavailable(f"The AI service returned an error ({e.code}). Please try again.") from e
        except errors.APIError as e:
            raise VisionUnavailable(f"Could not reach the AI service ({e.code}).") from e

        feedback = response.prompt_feedback
        if feedback is not None and feedback.block_reason:
            raise VisionUnavailable("The AI declined to analyse these photos.")

        parsed = response.parsed
        if isinstance(parsed, VisionPredictions):
            return parsed
        # Fall back to validating the raw text ourselves.
        text = response.text
        if not text:
            raise VisionUnavailable("The AI did not return a usable answer.")
        try:
            return VisionPredictions.model_validate_json(text)
        except ValueError as e:
            raise VisionUnavailable("The AI answer did not match the form. Please try again.") from e
