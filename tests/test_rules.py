"""Deterministic tests for the rule engine (no AI, no network)."""

from app.rules import compare_with_ai, consistency_rules, flatten, reliability, run_checks
from app.schemas import Flag
from tests.fixtures import SAMPLE_ANSWERS, SAMPLE_PREDICTIONS

ANSWERS = SAMPLE_ANSWERS.model_dump(mode="json")
PHOTOS = {"upstream": "upstream.jpg", "downstream": "downstream.jpg", "context": "context.jpg"}


def flat(**overrides):
    d = flatten(ANSWERS)
    d.update(overrides)
    return d


# --- compare_with_ai ---------------------------------------------------------

def test_no_predictions_means_no_ai_flags():
    assert compare_with_ai(ANSWERS, None) == []


def test_confident_disagreement_is_flagged_in_plain_language():
    flags = compare_with_ai(ANSWERS, SAMPLE_PREDICTIONS)
    ids = {f.id for f in flags}
    # Citizen said Clear-transparent, AI (0.85) says Muddy-turbid
    assert "ai:water_aspect" in ids
    f = next(f for f in flags if f.id == "ai:water_aspect")
    assert f.kind == "ai_disagreement"
    assert f.section == "section_b"
    assert "brown and cloudy" in f.message
    assert "Muddy-turbid" in f.message and "Clear-transparent" in f.message
    assert f.citizen_value == "Clear-transparent" and f.ai_value == "Muddy-turbid"


def test_agreement_produces_no_flag():
    flags = compare_with_ai(ANSWERS, SAMPLE_PREDICTIONS)
    assert "ai:channel_form" not in {f.id for f in flags}
    assert "ai:impervious_right" not in {f.id for f in flags}  # both say yes


def test_low_confidence_disagreement_is_not_flagged():
    answers = flat(vegetation_type_right="Shrubs")  # AI says Herbs at 0.6 < 0.7
    assert "ai:vegetation_type_right" not in {f.id for f in compare_with_ai(answers, SAMPLE_PREDICTIONS)}


def test_not_sure_gets_a_suggestion_when_ai_is_reasonably_sure():
    answers = flat(vegetation_type_right="not_sure")  # AI 0.6 >= 0.5
    f = next(f for f in compare_with_ai(answers, SAMPLE_PREDICTIONS) if f.id == "ai:vegetation_type_right")
    assert f.kind == "ai_suggestion"
    assert "weren't sure" in f.message and "Herbs" in f.message


def test_multi_select_compares_as_sets():
    answers = flat(habitats=["emergent vegetation", "pools"])  # same set, different order
    assert "ai:habitats" not in {f.id for f in compare_with_ai(answers, SAMPLE_PREDICTIONS)}
    answers = flat(habitats=["pools"])
    f = next(f for f in compare_with_ai(answers, SAMPLE_PREDICTIONS) if f.id == "ai:habitats")
    assert f.ai_value == ["pools", "emergent vegetation"]


def test_unanswered_fields_are_skipped():
    # Only section A answered so far: no section B/C flags yet.
    flags = compare_with_ai({"section_a": ANSWERS["section_a"]}, SAMPLE_PREDICTIONS)
    assert all(f.section == "section_a" for f in flags)


# --- consistency_rules ---------------------------------------------------------

def test_dry_but_water_height():
    ids = {f.id for f in consistency_rules(flat(water_flow="Dry", water_height_m=0.4))}
    assert "rule:dry_but_water_height" in ids
    assert not {f.id for f in consistency_rules(flat(water_flow="Dry", water_height_m=0))}
    assert not {f.id for f in consistency_rules(flat(water_flow="Dry", water_height_m=None))}


def test_vegetation_type_without_vegetation():
    flags = consistency_rules(flat(vegetation_left="no", vegetation_type_left="Trees"))
    assert {f.id for f in flags} == {"rule:vegetation_type_without_vegetation_left"}
    assert "left bank" in flags[0].message
    assert not consistency_rules(flat(vegetation_left="no", vegetation_type_left="not_sure"))
    assert not consistency_rules(flat(vegetation_left="no", vegetation_type_left=None))


def test_good_despite_pressures():
    f = consistency_rules(flat(overall_assessment="Good", sewage_discharge="yes"))[0]
    assert f.id == "rule:good_despite_pressures" and "sewage" in f.message
    f = consistency_rules(flat(overall_assessment="Good", bottom_type="Artificial (concrete or stones with concrete)"))[0]
    assert "artificial" in f.message
    f = consistency_rules(flat(overall_assessment="Good", water_aspect="Has foam"))[0]
    assert "foam" in f.message
    assert not consistency_rules(flat(overall_assessment="Moderate", sewage_discharge="yes"))


def test_poor_despite_no_pressures():
    ids = {f.id for f in consistency_rules(flat(overall_assessment="Poor"))}
    assert "rule:poor_despite_no_pressures" in ids
    assert not consistency_rules(flat(overall_assessment="Poor", barriers="yes"))


def test_rules_only_fire_when_their_fields_are_present():
    assert consistency_rules({"section_a": {"water_flow": "Dry"}}) == []
    assert consistency_rules({"section_d": {"overall_assessment": "Good"}}) == []


def test_sample_answers_are_consistent():
    assert consistency_rules(ANSWERS) == []


# --- reliability ---------------------------------------------------------------

def test_reliability_perfect_agreement():
    answers = flat(water_aspect="Muddy-turbid")  # now every confident AI field matches
    r = reliability(answers, SAMPLE_PREDICTIONS, [], PHOTOS)
    names = {c.name: c for c in r.components}
    assert names["AI agreement"].points == 50
    assert names["Photos"].points == 18
    assert names["Consistency"].points == 30 - 3  # one not_sure (invasive_species)
    assert r.score == 95


def test_reliability_penalises_unresolved_rule_flag_and_not_sure():
    answers = flat(water_aspect="Muddy-turbid", water_flow="Dry", water_height_m=0.5, barriers="not_sure")
    flags = consistency_rules(answers)  # dry_but_water_height, still open
    r = reliability(answers, SAMPLE_PREDICTIONS, flags, PHOTOS)
    names = {c.name: c for c in r.components}
    assert names["Consistency"].points == 30 - 10 - 3 * 2
    assert "1 unresolved" in names["Consistency"].note


def test_reliability_without_ai_is_rescaled_not_penalised():
    r = reliability(ANSWERS, None, [], PHOTOS)
    assert r.ai_available is False
    assert [c.name for c in r.components] == ["Photos", "Consistency"]
    assert r.score == round(100 * (18 + 27) / 50)


def test_reliability_kept_disagreement_lowers_agreement_but_is_not_unresolved():
    flags = compare_with_ai(ANSWERS, SAMPLE_PREDICTIONS)
    for f in flags:
        f.decision = "kept"
    r = reliability(ANSWERS, SAMPLE_PREDICTIONS, flags, PHOTOS)
    names = {c.name: c for c in r.components}
    assert names["AI agreement"].points < 50
    assert "0 unresolved" in names["Consistency"].note


def test_reliability_is_clamped_and_deterministic():
    answers = flat(**{f: "not_sure" for f in ("barriers", "draining_pipes", "construction", "water_withdrawal",
                                              "impervious_left", "impervious_right", "vegetation_cuts",
                                              "channel_form", "bottom_type", "bank_type", "water_flow")})
    r1 = reliability(answers, SAMPLE_PREDICTIONS, [], {})
    r2 = reliability(answers, SAMPLE_PREDICTIONS, [], {})
    assert r1 == r2 and 0 <= r1.score <= 100
    assert {c.name: c for c in r1.components}["Consistency"].points == 0


# --- run_checks --------------------------------------------------------------------

def test_run_checks_keeps_prior_decisions_and_changed_flags():
    flags, rel = run_checks(ANSWERS, SAMPLE_PREDICTIONS, [], PHOTOS)
    water = next(f for f in flags if f.id == "ai:water_aspect")
    assert water.decision is None

    # Citizen keeps their answer: decision survives a re-check.
    water.decision = "kept"
    flags2, _ = run_checks(ANSWERS, SAMPLE_PREDICTIONS, flags, PHOTOS)
    assert next(f for f in flags2 if f.id == "ai:water_aspect").decision == "kept"

    # Citizen changes to the AI value: answers now agree, but the audit entry survives.
    water.decision, water.decided_value = "changed", "Muddy-turbid"
    changed = flat(water_aspect="Muddy-turbid")
    flags3, rel3 = run_checks(changed, SAMPLE_PREDICTIONS, [water], PHOTOS)
    entry = next(f for f in flags3 if f.id == "ai:water_aspect")
    assert entry.decision == "changed" and entry.citizen_value == "Clear-transparent"
    assert rel3.score > rel.score
