from app.insights import one_health_risks, suggest_overall
from app.rules import flatten
from tests.fixtures import SAMPLE_ANSWERS

ANSWERS = SAMPLE_ANSWERS.model_dump(mode="json")
ARTIFICIAL = "Artificial (concrete or stones with concrete)"


def flat(**overrides):
    d = flatten(ANSWERS)
    d.update(overrides)
    return d


# --- suggested overall -----------------------------------------------------------

def test_sample_is_good():
    s = suggest_overall(ANSWERS)
    assert s.value == "Good" and s.pressure_points == 0
    assert "no pressures" in s.message


def test_moderate_for_concrete_channel():
    s = suggest_overall(flat(bottom_type=ARTIFICIAL, bank_type=ARTIFICIAL))
    assert s.value == "Moderate" and s.pressure_points == 3
    assert "bottom is artificial" in s.message and "banks are artificial" in s.message


def test_poor_for_sewage_plus_anything():
    s = suggest_overall(flat(sewage_discharge="yes", water_aspect="Has foam"))
    assert s.value == "Poor"
    assert "sewage" in s.message and "foam" in s.message


def test_not_sure_answers_are_reported_not_counted():
    s = suggest_overall(flat(sewage_discharge="not_sure", barriers="not_sure"))
    assert s.value == "Good"
    assert set(s.not_sure_fields) == {"sewage_discharge", "barriers"}
    assert "2 answer(s) you were not sure about" in s.message


def test_no_suggestion_with_too_few_answers():
    s = suggest_overall({"section_a": {"bottom_type": "Natural"}})
    assert s.value is None and "Not enough" in s.message


def test_suggestion_is_deterministic():
    a = flat(bottom_type=ARTIFICIAL, vegetation_left="no", vegetation_right="no")
    assert suggest_overall(a) == suggest_overall(a)
    assert suggest_overall(a).value == "Moderate"  # 2 + 2 = 4


# --- one health ------------------------------------------------------------------

def test_sample_gets_mosquito_note_and_positive_note():
    # Slow water with pools and leaves: a real, if modest, breeding risk even in a good stream.
    oh = one_health_risks(ANSWERS)
    assert [r.id for r in oh.risks] == ["mosquito_breeding", "wellbeing_positive"]
    assert oh.risk_level == "medium"


def test_fast_clear_vegetated_stream_is_positive():
    oh = one_health_risks(flat(water_flow="Fast (waves/high velocity)"))
    assert [r.id for r in oh.risks] == ["wellbeing_positive"]
    assert oh.risk_level == "positive"


def test_mosquito_risk_needs_still_water_and_somewhere_to_breed():
    oh = one_health_risks(flat(water_flow="Stagnant-intermittent", habitats=["pools"], natural_debris=["none"]))
    r = next(r for r in oh.risks if r.id == "mosquito_breeding")
    assert r.level == "medium" and "pools" in r.message and "dengue" in r.why_it_matters
    assert set(r.fields) == {"water_flow", "habitats", "natural_debris"}
    # Fast water: no mosquito risk even with pools.
    oh = one_health_risks(flat(water_flow="Fast (waves/high velocity)", habitats=["pools"]))
    assert "mosquito_breeding" not in {r.id for r in oh.risks}
    # Slow but nothing for larvae to sit in.
    oh = one_health_risks(flat(water_flow="Slow", habitats=["riffles"], natural_debris=["none"]))
    assert "mosquito_breeding" not in {r.id for r in oh.risks}


def test_pollution_is_high_and_cites_signs():
    oh = one_health_risks(flat(draining_pipes="yes", water_aspect="Has colours-altered colour"))
    r = next(r for r in oh.risks if r.id == "pathogen_pollution")
    assert r.level == "high"
    assert "pipes draining polluted water" in r.message and "altered water colour" in r.message
    assert oh.risk_level == "high"
    assert "wellbeing_positive" not in {r.id for r in oh.risks}


def test_biodiversity_risk_names_the_bank():
    oh = one_health_risks(flat(bottom_type=ARTIFICIAL, vegetation_left="no"))
    r = next(r for r in oh.risks if r.id == "low_biodiversity_resilience")
    assert "the left bank" in r.message
    oh = one_health_risks(flat(bottom_type=ARTIFICIAL, vegetation_left="no", vegetation_right="no"))
    assert "either bank" in next(r for r in oh.risks if r.id == "low_biodiversity_resilience").message
    # Artificial bottom alone is not enough.
    assert "low_biodiversity_resilience" not in {r.id for r in one_health_risks(flat(bottom_type=ARTIFICIAL)).risks}


def test_low_and_unknown_levels():
    oh = one_health_risks(flat(water_flow="Fast (waves/high velocity)", vegetation_left="no", water_aspect="Muddy-turbid"))
    assert oh.risks == [] and oh.risk_level == "low"
    assert one_health_risks({}).risk_level == "unknown"


def test_every_risk_has_the_three_one_health_angles():
    oh = one_health_risks(flat(water_flow="Slow", sewage_discharge="yes", bottom_type=ARTIFICIAL, vegetation_left="no"))
    assert len(oh.risks) == 3
    for r in oh.risks:
        assert "People" in r.why_it_matters and "Animals" in r.why_it_matters and "Environment" in r.why_it_matters
