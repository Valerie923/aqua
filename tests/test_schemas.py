import pytest
from pydantic import ValidationError

from app.schemas import (
    AI_READABLE_FIELDS,
    HUMAN_ONLY_FIELDS,
    FormAnswers,
    VisionPredictions,
    form_options,
)
from tests.fixtures import SAMPLE_ANSWERS, SAMPLE_PREDICTIONS


def test_sample_answers_round_trip():
    data = SAMPLE_ANSWERS.model_dump(mode="json")
    assert FormAnswers.model_validate(data) == SAMPLE_ANSWERS


def test_official_option_strings_are_exact():
    opts = form_options()
    assert opts["bottom_type"] == ["Natural", "Artificial (concrete or stones with concrete)", "not_sure"]
    assert opts["water_flow"] == ["Fast (waves/high velocity)", "Slow", "Stagnant-intermittent", "Dry", "not_sure"]
    assert opts["water_aspect"] == [
        "Clear-transparent",
        "Muddy-turbid",
        "Has foam",
        "Has colours-altered colour",
        "not_sure",
    ]
    assert "Laid stones with no concrete" in opts["bank_type"]


def test_invalid_option_is_rejected():
    data = SAMPLE_ANSWERS.model_dump(mode="json")
    data["section_a"]["water_flow"] = "Rapid"
    with pytest.raises(ValidationError):
        FormAnswers.model_validate(data)


def test_feeling_score_range():
    data = SAMPLE_ANSWERS.model_dump(mode="json")
    data["section_d"]["feelings"]["joy"] = 6
    with pytest.raises(ValidationError):
        FormAnswers.model_validate(data)


def test_vision_predictions_cover_every_ai_readable_field():
    assert set(AI_READABLE_FIELDS) <= set(VisionPredictions.model_fields)
    # and never a human-only field
    assert not set(HUMAN_ONLY_FIELDS) & set(VisionPredictions.model_fields)


def test_vision_confidence_is_bounded():
    data = SAMPLE_PREDICTIONS.model_dump(mode="json")
    data["water_flow"]["confidence"] = 1.5
    with pytest.raises(ValidationError):
        VisionPredictions.model_validate(data)


def test_vision_schema_is_structured_output_compatible():
    # The SDK must be able to turn the model into an output_format schema.
    from anthropic.lib._parse._transform import transform_schema

    schema = transform_schema(VisionPredictions.model_json_schema())
    assert schema["additionalProperties"] is False
    assert set(AI_READABLE_FIELDS) <= set(schema["required"])
