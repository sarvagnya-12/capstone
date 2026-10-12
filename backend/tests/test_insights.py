"""Business-facing summary (insights_service) and the reports built from it.

The point of this layer is that a non-technical reader sees honest, plain
statements -- so these tests check wording and counts, and that technical
internals (IDs, FID, rule names, the normalised PMF score) stay out."""

import csv
import io
import uuid

from PIL import Image

from app.models.feedback import SentimentLabel
from app.models.recommendation import Recommendation
from app.models.simulation import SimulationStatus
from app.services import insights_service, report_service
from app.services.insights_service import dominant_colour_name
from tests.conftest import make_feedback, make_persona, make_simulation_with_variants


def _simulation(db, likelihoods_a, likelihoods_b, *, tones_a=None, texts_a=None, recommend="A", risk_b=None):
    simulation, variants = make_simulation_with_variants(db, n_variants=2)
    simulation.pricing_strategy = {"tiers": [{"tier_name": "standard", "price": 65.0}]}
    simulation.target_demographic = {"age_min": 25, "age_max": 45, "region": "US"}
    simulation.promotional_messaging = "Comfort that goes anywhere"
    simulation.product.name, simulation.product.brand = "Gratis", "Skechers"
    personas = [make_persona(db, f"Profile {i}", f"style{i}") for i in range(len(likelihoods_a))]
    for i, persona in enumerate(personas):
        make_feedback(db, simulation, variants[0], persona, purchase_likelihood=likelihoods_a[i],
                      sentiment_label=(tones_a or [SentimentLabel.POSITIVE] * len(personas))[i],
                      qualitative_text=(texts_a or ["Love the look and the colour."] * len(personas))[i])
        make_feedback(db, simulation, variants[1], persona, purchase_likelihood=likelihoods_b[i],
                      sentiment_label=SentimentLabel.NEGATIVE, qualitative_text="Not for me.",
                      risk_flags=risk_b)
    first, second = (variants[0], variants[1]) if recommend == "A" else (variants[1], variants[0])
    db.add(Recommendation(simulation_id=simulation.id, recommended_variant_id=first.id, pmf_score=100.0,
                          ranking=[{"variant_id": str(first.id), "pmf_score": 100.0},
                                   {"variant_id": str(second.id), "pmf_score": 0.0}],
                          summary_text="technical summary"))
    simulation.status = SimulationStatus.COMPLETED
    db.flush()
    return simulation, variants


def test_counts_verdict_and_bottom_line(db_session):
    sim, _ = _simulation(db_session, [0.8, 0.7, 0.65, 0.2], [0.3, 0.2, 0.1, 0.1])
    ins = insights_service.build_insights(db_session, sim.id)
    a, b = ins.options
    assert (a.label, a.is_recommended, b.label, b.is_recommended) == ("Option A", True, "Option B", False)
    assert a.purchase_intent_pct == 59 and a.interest_level == "Moderate"
    assert (a.likely_buyers, a.undecided, a.unlikely_buyers, a.profiles) == (3, 0, 1, 4)
    assert ins.verdict == "Option A is promising but needs refinement before launch."
    assert "3 of 4 customer profiles" in ins.bottom_line and "59%" in ins.bottom_line
    assert "led Option B by" in ins.bottom_line
    assert a.least_interested == ["Profile 3"]
    assert ins.price_text == "Standard: 65.00" and ins.audience_text == "Ages 25-45, US"


def test_low_interest_says_not_launch_ready(db_session):
    sim, _ = _simulation(db_session, [0.2, 0.3], [0.1, 0.1])
    ins = insights_service.build_insights(db_session, sim.id)
    assert ins.verdict == "None of the tested options is launch-ready yet."
    assert ins.next_steps[0].startswith("No option generated strong buying interest")


def test_recommended_option_with_lower_intent_is_explained_not_hidden(db_session):
    # The system recommends A, but B had slightly higher purchase likelihood.
    sim, _ = _simulation(db_session, [0.5, 0.5], [0.6, 0.6])
    ins = insights_service.build_insights(db_session, sim.id)
    assert ins.options[0].is_recommended and ins.options[0].purchase_intent_pct < ins.options[1].purchase_intent_pct
    assert "had a slightly higher purchase likelihood" in ins.bottom_line


def test_tone_labels_describe_comments_not_purchase(db_session):
    sim, _ = _simulation(db_session, [0.7, 0.2], [0.1, 0.1],
                         tones_a=[SentimentLabel.NEGATIVE, SentimentLabel.POSITIVE])
    a = insights_service.build_insights(db_session, sim.id).options[0]
    critical_but_buying = next(r for r in a.reactions if r.profile == "Profile 0")
    assert (critical_but_buying.buying_intent, critical_but_buying.reaction) == ("Likely to buy", "Critical")
    assert a.reception == "Mixed"


def test_price_barrier_detected_from_comments(db_session):
    texts = ["Too expensive for me, I'll wait for a sale.", "The price is too high.", "Nice colour."]
    sim, _ = _simulation(db_session, [0.2, 0.3, 0.8], [0.1, 0.1, 0.1], texts_a=texts)
    a = insights_service.build_insights(db_session, sim.id).options[0]
    assert any(c.startswith("Price is a barrier: 2 of 3") for c in a.concerns)
    assert {"topic": "Price", "mentions": 2} in a.themes


def test_risk_rules_become_plain_language(db_session):
    risk = [{"rule": "low_purchase_likelihood", "severity": "high", "detail": "avg 0.10 < 0.30"}]
    sim, _ = _simulation(db_session, [0.8, 0.7], [0.1, 0.1], risk_b=risk)
    b = insights_service.build_insights(db_session, sim.id).options[1]
    assert b.concerns == ["Weak buying interest overall: customers rated their chance of buying below 35% on average."]


def test_llm_error_rows_are_excluded_and_disclosed(db_session):
    sim, _ = _simulation(db_session, [0.8, 0.7], [0.1, 0.1], texts_a=["[LLM_ERROR] timeout", "Love it."])
    a = insights_service.build_insights(db_session, sim.id).options[0]
    assert a.profiles == 1 and a.purchase_intent_pct == 70
    assert any("gave no usable reaction" in c for c in a.concerns)


def test_reports_are_free_of_technical_internals(db_session):
    sim, variants = _simulation(db_session, [0.8, 0.7], [0.1, 0.1])
    text = report_service.generate_csv(db_session, sim.id)
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["DryRunAI Launch Readiness Report"]
    for forbidden in (str(variants[0].id), str(sim.id), "fid", "pmf", "iteration", "sentiment_score", "risk_flags"):
        assert forbidden.lower() not in text.lower()
    assert ["Option", "Colourway", "Customer profile", "Buying intent", "Purchase likelihood (%)",
            "Tone of comment", "What they said"] in rows
    assert report_service.generate_pdf(db_session, sim.id)[:4] == b"%PDF"


def test_missing_results_raise(db_session):
    simulation, _ = make_simulation_with_variants(db_session, n_variants=1)
    import pytest

    with pytest.raises(insights_service.InsightsUnavailableError):
        insights_service.build_insights(db_session, simulation.id)
    with pytest.raises(insights_service.InsightsUnavailableError):
        insights_service.build_insights(db_session, uuid.uuid4())


def _product_shot(rgb):
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    img.paste(rgb, (12, 20, 52, 44))
    return img


def test_dominant_colour_names_match_what_a_person_would_say():
    assert dominant_colour_name(_product_shot((20, 20, 20))) == "black"
    assert dominant_colour_name(_product_shot((205, 205, 210))) == "light grey"
    assert dominant_colour_name(_product_shot((40, 190, 190))) == "teal"
    assert dominant_colour_name(_product_shot((30, 50, 120))) == "dark blue"
    # Leather tan measured from real renders: warm hue, moderate saturation.
    assert dominant_colour_name(_product_shot((166, 112, 86))) == "tan"
    assert dominant_colour_name(_product_shot((140, 40, 150))) == "purple"
    assert dominant_colour_name(Image.new("RGB", (64, 64), (255, 255, 255))) is None
