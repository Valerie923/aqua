"""The official OneAquaHealth Citizen Science form as Pydantic models.

This file is the single source of truth for field names, options, and wording.
The frontend, the vision prompt, and the (later) rule engine all derive from it.
Option strings are kept exactly as they appear in the official app so a judge
who knows the form recognises ours.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Option lists (exact official wording)
# --------------------------------------------------------------------------

class YesNo(str, Enum):
    yes = "yes"
    no = "no"
    not_sure = "not_sure"


class ChannelForm(str, Enum):
    flat = "Flat"
    u_shape = "U Shape"
    v_shape = "V Shape"
    not_sure = "not_sure"


class BottomType(str, Enum):
    natural = "Natural"
    artificial = "Artificial (concrete or stones with concrete)"
    not_sure = "not_sure"


class BankType(str, Enum):
    natural = "Natural"
    artificial = "Artificial (concrete or stones with concrete)"
    laid_stones = "Laid stones with no concrete"
    not_sure = "not_sure"


class Habitat(str, Enum):
    riffles = "riffles"
    pools = "pools"
    submerged_vegetation = "submerged vegetation"
    emergent_vegetation = "emergent vegetation"
    overhanging_vegetation = "overhanging vegetation"
    roots = "roots"
    woody_debris = "woody debris"
    gravel_cobbles = "gravel/cobbles"
    sand_silt = "sand/silt"
    none = "none"


class NaturalDebris(str, Enum):
    leaves = "leaves"
    branches = "branches"
    logs = "logs"
    none = "none"


class WaterFlow(str, Enum):
    fast = "Fast (waves/high velocity)"
    slow = "Slow"
    stagnant = "Stagnant-intermittent"
    dry = "Dry"
    not_sure = "not_sure"


class WaterAspect(str, Enum):
    clear = "Clear-transparent"
    muddy = "Muddy-turbid"
    foam = "Has foam"
    colour = "Has colours-altered colour"
    not_sure = "not_sure"


class VegetationType(str, Enum):
    herbs = "Herbs"
    shrubs = "Shrubs"
    trees = "Trees"
    not_sure = "not_sure"


class OverallAssessment(str, Enum):
    good = "Good"
    moderate = "Moderate"
    poor = "Poor"


# Official help text shown next to the overall assessment options.
OVERALL_ASSESSMENT_HELP = {
    OverallAssessment.good: (
        "The stream looks natural: clear water, natural bed and banks, "
        "plenty of vegetation and habitats, no visible pollution."
    ),
    OverallAssessment.moderate: (
        "Some human changes are visible (partly artificial banks or bed, "
        "some pollution signs or reduced vegetation) but the stream still "
        "has natural elements."
    ),
    OverallAssessment.poor: (
        "The stream is heavily modified or polluted: concrete channel, "
        "turbid or coloured water, foam, pipes, waste, or little to no vegetation."
    ),
}


# A feeling is rated 0–5, or "not_applicable" if the citizen cannot say.
FeelingScore = Literal[0, 1, 2, 3, 4, 5, "not_applicable"]


# --------------------------------------------------------------------------
# The form, section by section
# --------------------------------------------------------------------------

class Site(BaseModel):
    name: str = Field(..., min_length=1, description="Site name (free text)")
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class SectionA(BaseModel):
    """What do you see from where you stand (ca. 100m)?"""

    channel_form: ChannelForm
    bottom_type: BottomType
    bank_type: BankType
    habitats: list[Habitat] = Field(default_factory=list)
    natural_debris: list[NaturalDebris] = Field(default_factory=list)
    water_flow: WaterFlow


class SectionB(BaseModel):
    """Water and pressures."""

    water_aspect: WaterAspect
    water_withdrawal: YesNo
    barriers: YesNo = Field(..., description="Dams or transversal artificial barriers")
    draining_pipes: YesNo = Field(..., description="Pipes draining polluted water")
    sewage_discharge: YesNo
    construction: YesNo = Field(..., description="Works in stream")
    water_height_m: float | None = Field(None, ge=0, description="Water height in metres")


class SectionC(BaseModel):
    """Riparian zone (5–10 m from banktop). Left/right defined looking downstream."""

    impervious_left: YesNo = Field(..., description=">1/3 covered by roads/sidewalks/buildings")
    impervious_right: YesNo
    vegetation_left: YesNo
    vegetation_right: YesNo
    vegetation_type_left: VegetationType | None = None
    vegetation_type_right: VegetationType | None = None
    invasive_species: YesNo
    invasive_species_which: str = Field("", description="Which ones (free text)")
    vegetation_cuts: YesNo = Field(..., description="Recent cuts on banks")


class Feelings(BaseModel):
    joy: FeelingScore = "not_applicable"
    serenity: FeelingScore = "not_applicable"
    anger: FeelingScore = "not_applicable"
    fear: FeelingScore = "not_applicable"


class SectionD(BaseModel):
    """Feedback."""

    overall_assessment: OverallAssessment
    feelings: Feelings = Field(default_factory=Feelings)


class FormAnswers(BaseModel):
    """Everything the citizen fills in, in official form order."""

    site: Site
    section_a: SectionA
    section_b: SectionB
    section_c: SectionC
    section_d: SectionD


# --------------------------------------------------------------------------
# AI predictions (what the vision model returns for each readable field)
# --------------------------------------------------------------------------

# Fields the AI is asked to read from photos, in the order they appear in the form.
AI_READABLE_FIELDS: tuple[str, ...] = (
    "channel_form",
    "bottom_type",
    "bank_type",
    "habitats",
    "natural_debris",
    "water_flow",
    "water_aspect",
    "barriers",
    "draining_pipes",
    "construction",
    "impervious_left",
    "impervious_right",
    "vegetation_left",
    "vegetation_right",
    "vegetation_type_left",
    "vegetation_type_right",
)

# Fields a photo cannot answer. The AI never guesses these.
HUMAN_ONLY_FIELDS: tuple[str, ...] = (
    "water_withdrawal",
    "sewage_discharge",
    "water_height_m",
    "invasive_species",
    "invasive_species_which",
    "vegetation_cuts",
    "overall_assessment",
    "feelings",
)

# Which section each AI-readable field lives in (used by the frontend).
FIELD_SECTION: dict[str, str] = {
    **{f: "section_a" for f in ("channel_form", "bottom_type", "bank_type", "habitats", "natural_debris", "water_flow")},
    **{f: "section_b" for f in ("water_aspect", "barriers", "draining_pipes", "construction")},
    **{f: "section_c" for f in ("impervious_left", "impervious_right", "vegetation_left", "vegetation_right", "vegetation_type_left", "vegetation_type_right")},
}


class _Prediction(BaseModel):
    confidence: float = Field(..., ge=0, le=1, description="0 = pure guess, 1 = certain")
    evidence: str = Field(..., description="One plain-language sentence: what in the photo supports this")


class ChannelFormPrediction(_Prediction):
    value: ChannelForm


class BottomTypePrediction(_Prediction):
    value: BottomType


class BankTypePrediction(_Prediction):
    value: BankType


class HabitatsPrediction(_Prediction):
    value: list[Habitat]


class NaturalDebrisPrediction(_Prediction):
    value: list[NaturalDebris]


class WaterFlowPrediction(_Prediction):
    value: WaterFlow


class WaterAspectPrediction(_Prediction):
    value: WaterAspect


class YesNoPrediction(_Prediction):
    value: YesNo


class VegetationTypePrediction(_Prediction):
    value: VegetationType


class VisionPredictions(BaseModel):
    """Strict JSON the vision model must return. One entry per AI-readable field."""

    photo_quality: str = Field(
        ...,
        description="One sentence on how usable the photos are (lighting, angle, distance, obstructions).",
    )
    channel_form: ChannelFormPrediction
    bottom_type: BottomTypePrediction
    bank_type: BankTypePrediction
    habitats: HabitatsPrediction
    natural_debris: NaturalDebrisPrediction
    water_flow: WaterFlowPrediction
    water_aspect: WaterAspectPrediction
    barriers: YesNoPrediction
    draining_pipes: YesNoPrediction
    construction: YesNoPrediction
    impervious_left: YesNoPrediction
    impervious_right: YesNoPrediction
    vegetation_left: YesNoPrediction
    vegetation_right: YesNoPrediction
    vegetation_type_left: VegetationTypePrediction
    vegetation_type_right: VegetationTypePrediction


class AnalysisResult(BaseModel):
    """What the /api/analyze endpoint returns to the frontend."""

    photo_set_id: str
    photos: dict[str, str] = Field(..., description="photo role -> stored filename")
    ai_available: bool
    model: str | None = None
    predictions: VisionPredictions | None = None
    human_only: list[str] = Field(default_factory=lambda: list(HUMAN_ONLY_FIELDS))
    error: str | None = Field(None, description="Plain-language reason if the AI could not run")


# --------------------------------------------------------------------------
# Submissions
# --------------------------------------------------------------------------

class SubmissionIn(BaseModel):
    photo_set_id: str | None = None
    answers: FormAnswers


class SubmissionOut(BaseModel):
    id: str
    created_at: str
    photo_set_id: str | None
    photos: dict[str, str]
    answers: FormAnswers
    ai_predictions: VisionPredictions | None
    ai_model: str | None
    # Filled in by Phase 2+.
    flags: list[dict] = Field(default_factory=list)
    final_answers: FormAnswers | None = None
    reliability_score: int | None = None


def form_options() -> dict:
    """Option lists for the frontend, so it never hardcodes its own copy."""
    return {
        "yes_no": [e.value for e in YesNo],
        "channel_form": [e.value for e in ChannelForm],
        "bottom_type": [e.value for e in BottomType],
        "bank_type": [e.value for e in BankType],
        "habitats": [e.value for e in Habitat],
        "natural_debris": [e.value for e in NaturalDebris],
        "water_flow": [e.value for e in WaterFlow],
        "water_aspect": [e.value for e in WaterAspect],
        "vegetation_type": [e.value for e in VegetationType],
        "overall_assessment": [e.value for e in OverallAssessment],
        "overall_assessment_help": {k.value: v for k, v in OVERALL_ASSESSMENT_HELP.items()},
        "feeling_scores": [0, 1, 2, 3, 4, 5, "not_applicable"],
        "ai_readable_fields": list(AI_READABLE_FIELDS),
        "human_only_fields": list(HUMAN_ONLY_FIELDS),
        "field_section": FIELD_SECTION,
    }
