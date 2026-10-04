"""Claude (Anthropic API) vision provider.

Sends the photos plus the system prompt, and asks for structured JSON that must
match `VisionPredictions`. The SDK validates the JSON against the Pydantic
model, so a malformed answer becomes an error rather than a bad prediction.
"""

import base64

import anthropic

from app.schemas import VisionPredictions
from app.vision.base import Photo, VisionUnavailable
from app.vision.prompt import SYSTEM_PROMPT, USER_INSTRUCTION

ROLE_LABELS = {
    "upstream": "Photo 1 — looking UPSTREAM",
    "downstream": "Photo 2 — looking DOWNSTREAM",
    "context": "Photo 3 — surrounding context",
    "biodiversity": "Photo 4 — biodiversity element (optional extra)",
}


class AnthropicVisionProvider:
    name = "anthropic"

    def __init__(self, model: str):
        self.model = model
        # Reads ANTHROPIC_API_KEY from the environment.
        self.client = anthropic.Anthropic()

    def _content(self, photos: list[Photo]) -> list[dict]:
        content: list[dict] = []
        for photo in photos:
            content.append({"type": "text", "text": ROLE_LABELS.get(photo.role, photo.role)})
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": photo.media_type,
                        "data": base64.standard_b64encode(photo.data).decode("utf-8"),
                    },
                }
            )
        content.append({"type": "text", "text": USER_INSTRUCTION})
        return content

    def analyse(self, photos: list[Photo]) -> VisionPredictions:
        if not photos:
            raise VisionUnavailable("No photos were provided.")
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": self._content(photos)}],
                output_format=VisionPredictions,
            )
        except anthropic.AuthenticationError as e:
            raise VisionUnavailable("The AI service rejected our API key.") from e
        except anthropic.RateLimitError as e:
            raise VisionUnavailable("The AI service is busy. Please try again in a minute.") from e
        except anthropic.BadRequestError as e:
            raise VisionUnavailable(f"The AI service could not process these photos: {e.message}") from e
        except anthropic.APIStatusError as e:
            raise VisionUnavailable(f"The AI service returned an error ({e.status_code}).") from e
        except anthropic.APIConnectionError as e:
            raise VisionUnavailable("Could not reach the AI service. Check the network.") from e

        if response.stop_reason == "refusal":
            raise VisionUnavailable("The AI declined to analyse these photos.")
        if response.stop_reason == "max_tokens":
            raise VisionUnavailable("The AI answer was cut off. Please try again.")
        if response.parsed_output is None:
            raise VisionUnavailable("The AI did not return a usable answer.")
        return response.parsed_output
