"""Persona prompts that know the product, can see the variant image, and are
grounded in real reviews. Everything external is faked: the LLM, the HTTP
layer and the embedding model -- these prove the wiring and the fallbacks,
not the quality of the reactions (that needs a real model run)."""

import base64
import json

import numpy as np
import pytest
import requests
from PIL import Image

from app.core.config import settings
from app.ml.llm.prompt_templates import build_persona_reaction_prompt, describe_product
from app.ml.llm.provider import AnthropicProvider, OllamaProvider
from app.ml.retrieval.reviews import ReviewIndex, band_quota, clean_review_text, rating_band


def _prompt(**kwargs):
    base = dict(persona_prompt_template="You are a budget shopper.", variant_attributes={},
                pricing_strategy={"tiers": [{"tier_name": "standard", "price": 49.0}]},
                target_demographic={}, promotional_messaging=None)
    base.update(kwargs)
    return build_persona_reaction_prompt(**base)


# --- prompt ---------------------------------------------------------------

def test_prompt_names_the_product():
    product = describe_product("Trail Runner", "Acme", "footwear", "Lightweight running shoe")
    prompt = _prompt(product_description=product)
    assert "The product: Acme Trail Runner (footwear) -- Lightweight running shoe" in prompt


def test_describe_product_handles_missing_fields():
    assert describe_product(None, None, None, None) is None
    assert describe_product("X", None, None, None) == "X"
    assert len(describe_product("X", None, None, "d" * 2000)) < 600


def test_image_instruction_only_when_an_image_is_sent():
    assert "photo of this exact design variant is attached" in _prompt(has_image=True)
    assert "attached" not in _prompt(has_image=False)


def test_reference_reviews_are_labelled_and_truncated():
    prompt = _prompt(reference_reviews=[{"rating": 1.0, "text": "Runs small. " * 100},
                                        {"rating": 5.0, "text": "Very comfy."}])
    assert "real buyers of similar products" in prompt
    assert "Do not copy" in prompt
    assert "(1/5) Runs small." in prompt and "(5/5) Very comfy." in prompt
    assert "Runs small. " * 40 not in prompt  # truncated


def test_no_review_block_without_reviews():
    assert "real buyers" not in _prompt(reference_reviews=None)
    assert "real buyers" not in _prompt(reference_reviews=[])


def test_prompt_still_ends_with_the_json_contract():
    assert _prompt(reference_reviews=[{"rating": 3, "text": "ok"}], has_image=True).rstrip().endswith(
        '"purchase_likelihood": <float between 0.0 and 1.0>}')


# --- providers --------------------------------------------------------------

class _Resp:
    status_code = 200
    text = ""

    def json(self):
        return {"response": "{}"}

    def raise_for_status(self):
        pass


def test_ollama_sends_images_base64_and_bearer_token(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured.update(url=url, json=json, headers=headers)
        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    OllamaProvider("https://ollama.example", "gemma3:4b", api_key="secret").complete("p", images=[b"\xff\xd8jpg"])
    assert captured["json"]["images"] == [base64.b64encode(b"\xff\xd8jpg").decode()]
    assert captured["headers"] == {"Authorization": "Bearer secret"}


def test_ollama_local_sends_no_images_key_or_auth_by_default(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured.update(json=json, kwargs=kwargs)
        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    OllamaProvider("http://localhost:11434", "llama3.1:8b").complete("p")
    assert "images" not in captured["json"] and captured["kwargs"] == {}


def test_anthropic_puts_images_before_text(monkeypatch):
    sent = {}

    class _Messages:
        def create(self, **kwargs):
            sent.update(kwargs)

            class _R:
                content = [type("B", (), {"text": "{}"})()]
            return _R()

    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider._client = type("C", (), {"messages": _Messages()})()
    provider._model = "m"
    provider.complete("hello", images=[b"\x89PNGdata"])
    content = sent["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[0]["source"]["media_type"] == "image/png"
    assert content[1] == {"type": "text", "text": "hello"}


# --- retrieval --------------------------------------------------------------

def test_clean_review_text_strips_html():
    assert clean_review_text("Too small.<br />Returned &amp; reordered.") == "Too small. Returned & reordered."


def test_band_quota_is_more_critical_than_the_corpus():
    assert band_quota(5) == {"negative": 2, "mixed": 1, "positive": 2}
    assert sum(band_quota(3).values()) == 3
    assert sum(band_quota(1).values()) == 1


def _toy_index(ratings, sims):
    """One-dimensional-ish index where review i has cosine similarity sims[i] to the query."""
    sims = np.asarray(sims, dtype=np.float32)
    emb = np.stack([sims, np.sqrt(np.clip(1 - sims ** 2, 0, 1))], axis=1).astype(np.float16)
    return ReviewIndex(embeddings=emb, review_ids=np.array([f"r{i}" for i in range(len(sims))]),
                       ratings=np.asarray(ratings, dtype=np.float32), model_name="toy")


def test_search_balances_ratings_instead_of_returning_only_praise():
    # Ten most-similar reviews are all 5-star; the critical ones rank lower.
    ratings = [5] * 10 + [1, 2, 3]
    sims = [0.99 - i * 0.01 for i in range(10)] + [0.5, 0.45, 0.4]
    hits = _toy_index(ratings, sims).search(np.array([1.0, 0.0]), k=5)
    bands = [rating_band(rating) for _, rating, _ in hits]
    assert bands.count("negative") == 2 and bands.count("mixed") == 1 and bands.count("positive") == 2
    assert [s for _, _, s in hits] == sorted([s for _, _, s in hits], reverse=True)


def test_search_tops_up_when_a_band_is_empty():
    hits = _toy_index([5, 5, 5, 4, 4, 5], [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]).search(np.array([1.0, 0.0]), k=5)
    assert len(hits) == 5


def test_focus_reranks_within_the_products_relevant_reviews(monkeypatch):
    # Stage 1 keeps only the product's top PRODUCT_POOL reviews (3,000 of
    # ~350k in production); shrunk here so the off-product review is gated out.
    monkeypatch.setattr("app.ml.retrieval.reviews.PRODUCT_POOL", 2)
    # 2-D embeddings: axis 0 = "about this product", axis 1 = "about price".
    emb = np.array([[1.0, 0.0],      # r0 on-product, nothing about price
                    [0.8, 0.6],      # r1 on-product AND about price
                    [0.0, 1.0]],     # r2 all price, unrelated product
                   dtype=np.float16)
    index = ReviewIndex(embeddings=emb, review_ids=np.array(["r0", "r1", "r2"]),
                        ratings=np.array([5, 5, 5], dtype=np.float32), model_name="toy")
    product, price_focus = np.array([1.0, 0.0]), np.array([0.0, 1.0])
    assert index.search(product, 1)[0][0] == "r0"
    assert index.search(product, 1, focus_embedding=price_focus)[0][0] == "r1"


def test_persona_focus_uses_the_behaviour_clause():
    from app.ml.retrieval.reviews import persona_focus

    prompt = "Persona: Budget Shopper; Age: 18-25; Income: Low; Region: US; Behavior: waits for sales"
    assert persona_focus(prompt) == "A shoe review from a buyer who waits for sales"
    assert "free-form persona" in persona_focus("A free-form persona with no behaviour clause")


def test_index_round_trips_through_disk(tmp_path):
    index = _toy_index([1, 5, 3], [0.9, 0.8, 0.1])
    np.save(tmp_path / "embeddings.npy", index.embeddings)
    np.savez(tmp_path / "meta.npz", review_ids=index.review_ids, ratings=index.ratings)
    (tmp_path / "info.json").write_text(json.dumps({"model": "toy"}))
    loaded = ReviewIndex.load(tmp_path)
    assert loaded.search(np.array([1.0, 0.0]), 2) == index.search(np.array([1.0, 0.0]), 2)


# --- persona_service wiring ------------------------------------------------

def _simulation_with_real_variant_image(db):
    from tests.conftest import make_persona
    from app.models.product_variant import ProductVariant
    from app.services import storage_service
    from tests.test_hybrid_generation import _make_product_simulation

    simulation = _make_product_simulation(db)
    path = storage_service.save_pil_image(Image.new("RGB", (8, 8), (1, 2, 3)), subfolder="v", filename="v.jpg")
    variant = ProductVariant(product_id=simulation.product_id, simulation_id=simulation.id, image_path=path,
                             attributes={"color_hue_shift_degrees": 240}, generation_method="gan")
    db.add(variant)
    simulation.personas.extend([make_persona(db, "Budget", "budget"), make_persona(db, "Athlete", "athletic")])
    db.flush()
    return simulation


def test_personas_get_product_and_image(db_session, fake_llm_provider, monkeypatch):
    from app.services import persona_service

    monkeypatch.setattr(settings, "LLM_VISION", True)
    simulation = _simulation_with_real_variant_image(db_session)
    rows = persona_service.simulate_persona_reactions(db_session, simulation.id)

    assert len(rows) == 2
    for call in fake_llm_provider.calls:
        assert "Acme Trail Runner" in call["prompt"]
        assert call["images"] and call["images"][0][:2] == b"\xff\xd8"  # real JPEG bytes
        assert "attached" in call["prompt"]


def test_vision_off_sends_no_images(db_session, fake_llm_provider):
    from app.services import persona_service

    simulation = _simulation_with_real_variant_image(db_session)
    persona_service.simulate_persona_reactions(db_session, simulation.id)
    assert all(call["images"] is None for call in fake_llm_provider.calls)


def test_unreadable_image_falls_back_to_text(db_session, fake_llm_provider, monkeypatch):
    from app.services import persona_service

    monkeypatch.setattr(settings, "LLM_VISION", True)
    simulation = _simulation_with_real_variant_image(db_session)
    simulation.variants[0].image_path = "missing/nope.jpg"
    db_session.flush()
    rows = persona_service.simulate_persona_reactions(db_session, simulation.id)
    assert len(rows) == 2 and all(not r.qualitative_text.startswith("[LLM_ERROR]") for r in rows)
    assert all(call["images"] is None and "attached" not in call["prompt"] for call in fake_llm_provider.calls)


def test_grounding_retrieves_once_per_persona(db_session, fake_llm_provider, monkeypatch):
    from app.services import persona_service

    calls = []

    def fake_fetch(db, product_description, persona_prompt, k, index_dir):
        calls.append(persona_prompt)
        return [{"rating": 1.0, "text": "Fell apart in a month."}]

    monkeypatch.setattr(settings, "REVIEW_GROUNDING_ENABLED", True)
    monkeypatch.setattr(persona_service, "fetch_reference_reviews", fake_fetch)
    simulation = _simulation_with_real_variant_image(db_session)
    persona_service.simulate_persona_reactions(db_session, simulation.id)

    assert len(calls) == 2  # two personas, one variant
    assert all("Fell apart in a month." in c["prompt"] for c in fake_llm_provider.calls)


def test_missing_index_degrades_to_ungrounded_prompts(db_session, fake_llm_provider, monkeypatch, tmp_path):
    from app.services import persona_service

    monkeypatch.setattr(settings, "REVIEW_GROUNDING_ENABLED", True)
    monkeypatch.setattr(settings, "REVIEW_INDEX_DIR", str(tmp_path / "no-index"))
    monkeypatch.setattr("app.ml.retrieval.reviews._index_cache", None)
    simulation = _simulation_with_real_variant_image(db_session)
    rows = persona_service.simulate_persona_reactions(db_session, simulation.id)

    assert len(rows) == 2 and all(not r.qualitative_text.startswith("[LLM_ERROR]") for r in rows)
    assert all("real buyers" not in c["prompt"] for c in fake_llm_provider.calls)
