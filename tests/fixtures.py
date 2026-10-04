"""Shared fixed data for deterministic tests."""

from app.schemas import (
    BankType,
    BottomType,
    ChannelForm,
    FormAnswers,
    Habitat,
    NaturalDebris,
    VegetationType,
    VisionPredictions,
    WaterAspect,
    WaterFlow,
    YesNo,
)

SAMPLE_ANSWERS = FormAnswers.model_validate(
    {
        "site": {"name": "Kallang River at Bishan-Ang Mo Kio Park", "lat": 1.362, "lon": 103.845},
        "section_a": {
            "channel_form": "U Shape",
            "bottom_type": "Natural",
            "bank_type": "Natural",
            "habitats": ["pools", "emergent vegetation"],
            "natural_debris": ["leaves"],
            "water_flow": "Slow",
        },
        "section_b": {
            "water_aspect": "Clear-transparent",
            "water_withdrawal": "no",
            "barriers": "no",
            "draining_pipes": "no",
            "sewage_discharge": "no",
            "construction": "no",
            "water_height_m": 0.3,
        },
        "section_c": {
            "impervious_left": "no",
            "impervious_right": "yes",
            "vegetation_left": "yes",
            "vegetation_right": "yes",
            "vegetation_type_left": "Trees",
            "vegetation_type_right": "Herbs",
            "invasive_species": "not_sure",
            "invasive_species_which": "",
            "vegetation_cuts": "no",
        },
        "section_d": {
            "overall_assessment": "Good",
            "feelings": {"joy": 4, "serenity": 5, "anger": 0, "fear": "not_applicable"},
        },
    }
)


def _p(value, confidence=0.9, evidence="visible in the photo"):
    return {"value": value, "confidence": confidence, "evidence": evidence}


SAMPLE_PREDICTIONS = VisionPredictions.model_validate(
    {
        "photo_quality": "Bright daylight, all three photos are sharp.",
        "channel_form": _p("U Shape"),
        "bottom_type": _p("Natural"),
        "bank_type": _p("Natural"),
        "habitats": _p(["pools", "emergent vegetation"]),
        "natural_debris": _p(["leaves"]),
        "water_flow": _p("Slow"),
        "water_aspect": _p("Muddy-turbid", 0.85, "the water looks brown and cloudy"),
        "barriers": _p("no"),
        "draining_pipes": _p("no"),
        "construction": _p("no"),
        "impervious_left": _p("no"),
        "impervious_right": _p("yes", 0.8, "a paved footpath runs right along the right bank"),
        "vegetation_left": _p("yes"),
        "vegetation_right": _p("yes"),
        "vegetation_type_left": _p("Trees"),
        "vegetation_type_right": _p("Herbs", 0.6, "mostly grass on the right bank"),
    }
)
