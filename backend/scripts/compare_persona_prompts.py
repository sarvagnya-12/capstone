"""Measure whether the persona-prompt improvements actually improve reactions.

Runs the SAME personas against the SAME variants under each prompt condition
and scores the reactions. Nothing is written to the database -- this calls the
prompt builder and the LLM directly.

Conditions (each adds to the previous):
  baseline   variant description + scenario only (the original prompt)
  +product   the product's name/brand/category/description
  +reviews   real reviews of similar products (needs the review index)
  +image     the variant image itself (only with --vision; needs a vision model)

Metrics (all automatic, all rough -- read the sample texts too):
  persona_similarity  mean cosine similarity between different personas'
                      reactions to the same variant. LOWER = personas sound
                      more different from each other.
  likelihood_spread   std of purchase_likelihood across personas per variant.
                      Higher = personas disagree more (0 = all identical).
  specificity         share of reactions naming a concrete product aspect
                      (fit, sole, mesh, comfort, colour, price, ...).
  real_review_sim     cosine similarity to the nearest of ~350k real reviews.
                      Higher = sounds more like real shoppers.
  near_copies         reactions with >= 0.85 similarity to a review that was
                      in their own prompt (should be ~0: copying, not grounding).
  brand_leaks         reactions naming a known brand that is not the product's.
  jargon_leaks        reactions mentioning generator internals (latent, GAN, ...).
  rerun_drift         mean |change in purchase_likelihood| when the same prompt
                      is sent twice (lower = more consistent).
  failures            calls that errored or returned unparseable output.

Usage:
    cd backend
    .venv\\Scripts\\python.exe scripts\\compare_persona_prompts.py               # latest completed simulation
    .venv\\Scripts\\python.exe scripts\\compare_persona_prompts.py --vision      # adds the +image condition
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ml.llm.prompt_templates import build_persona_reaction_prompt, describe_product, parse_persona_reaction  # noqa: E402
from app.ml.llm.provider import get_llm_provider  # noqa: E402
from app.ml.retrieval import reviews as retrieval  # noqa: E402
from app.models.product_variant import ProductVariant  # noqa: E402
from app.models.reference_data import RefProduct  # noqa: E402
from app.models.simulation import Simulation, SimulationStatus  # noqa: E402
from app.services.persona_service import select_representative_personas  # noqa: E402
from app.services.storage_service import get_path  # noqa: E402

ASPECT_WORDS = {
    "fit", "fits", "size", "sizing", "narrow", "wide", "tight", "comfort", "comfortable", "cushion",
    "cushioning", "support", "arch", "sole", "soles", "outsole", "heel", "toe", "lace", "laces", "mesh",
    "upper", "leather", "suede", "fabric", "material", "materials", "breathable", "breathe", "weight",
    "lightweight", "heavy", "durable", "durability", "grip", "stitching", "colour", "color", "colourway",
    "colorway", "price", "priced", "expensive", "cheap", "value", "quality", "running", "walking",
}
JARGON_RE = re.compile(r"\b(latent|perturbation|gan\b|generator|anchor seed|hue shift|generation method)", re.I)
NEAR_COPY = 0.85


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def load_brands(db, own_brand: str | None, limit: int = 300) -> list[str]:
    from sqlalchemy import func

    rows = (db.query(RefProduct.brand, func.count()).group_by(RefProduct.brand)
            .order_by(func.count().desc()).limit(limit).all())
    own = (own_brand or "").lower()
    # Single common words ("Generic", "Comfort") would match ordinary prose.
    return [b for b, _ in rows if b and len(b) > 3 and b.lower() != own
            and b.lower() not in ASPECT_WORDS and b.lower() not in {"generic", "unknown", "comfort", "classic"}]


def call(provider, prompt: str, images) -> dict | None:
    try:
        return parse_persona_reaction(provider.complete(prompt, images=images))
    except Exception as e:  # noqa: BLE001 -- counted as a failure, reported, not fatal
        print(f"    call failed: {str(e)[:120]}", flush=True)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--simulation-id", type=uuid.UUID, help="Default: latest completed simulation")
    parser.add_argument("--variants", type=int, default=3)
    parser.add_argument("--personas", type=int, default=5)
    parser.add_argument("--vision", action="store_true", help="Add the +image condition (vision model required)")
    parser.add_argument("--no-rerun", action="store_true", help="Skip the consistency re-run (halves LLM calls)")
    parser.add_argument("--out", type=Path, default=BACKEND_ROOT / "storage" / "persona_eval")
    args = parser.parse_args()

    provider = get_llm_provider()
    index = retrieval._get_index(settings.REVIEW_INDEX_DIR)
    encoder = retrieval._get_encoder(index.model_name)

    with SessionLocal() as db:
        simulation = (db.get(Simulation, args.simulation_id) if args.simulation_id else
                      db.query(Simulation).filter(Simulation.status == SimulationStatus.COMPLETED)
                      .order_by(Simulation.created_at.desc()).first())
        if simulation is None:
            raise SystemExit("no completed simulation found")
        product = simulation.product
        variants = (db.query(ProductVariant).filter(ProductVariant.simulation_id == simulation.id)
                    .order_by(ProductVariant.created_at).limit(args.variants).all())
        personas = select_representative_personas(db, args.personas)
        product_text = describe_product(product.name, product.brand, product.category, product.description)
        brands = load_brands(db, product.brand)
        reviews_by_persona = {p.id: retrieval.fetch_reference_reviews(db, product_text, p.prompt_template,
                                                                      settings.REVIEW_GROUNDING_K,
                                                                      settings.REVIEW_INDEX_DIR)
                              for p in personas}
        images = {v.id: get_path(v.image_path).read_bytes() for v in variants}

        conditions = ["baseline", "+product", "+reviews"] + (["+image"] if args.vision else [])
        print(f"simulation {simulation.id}: {product_text}")
        print(f"{len(personas)} personas x {len(variants)} variants x {len(conditions)} conditions "
              f"({'with' if not args.no_rerun else 'without'} re-run) via {settings.LLM_PROVIDER}:"
              f"{settings.OLLAMA_MODEL if settings.LLM_PROVIDER == 'ollama' else settings.ANTHROPIC_MODEL}\n")

        results: dict[str, list[dict]] = {}
        started = time.time()
        for ci, condition in enumerate(conditions):
            rows = []
            for variant in variants:
                for persona in personas:
                    reviews = reviews_by_persona[persona.id] if ci >= 2 else None
                    prompt = build_persona_reaction_prompt(
                        persona_prompt_template=persona.prompt_template,
                        variant_attributes=variant.attributes,
                        pricing_strategy=simulation.pricing_strategy,
                        target_demographic=simulation.target_demographic,
                        promotional_messaging=simulation.promotional_messaging,
                        product_description=product_text if ci >= 1 else None,
                        has_image=condition == "+image",
                        reference_reviews=reviews,
                    )
                    imgs = [images[variant.id]] if condition == "+image" else None
                    first = call(provider, prompt, imgs)
                    second = None if args.no_rerun or first is None else call(provider, prompt, imgs)
                    rows.append({"variant": str(variant.id), "persona": persona.name, "first": first,
                                 "second": second, "reviews": reviews})
            results[condition] = rows
            print(f"  {condition}: {len(rows)} pairs done ({time.time() - started:.0f}s elapsed)", flush=True)

    # --- scoring --------------------------------------------------------
    summary = {}
    for condition, rows in results.items():
        ok = [r for r in rows if r["first"]]
        texts = [r["first"]["reaction_text"] for r in ok]
        emb = encoder.encode(texts, normalize_embeddings=True) if texts else np.zeros((0, 384))
        for r, e in zip(ok, emb):
            r["emb"] = e

        pair_sims, spreads = [], []
        for variant in {r["variant"] for r in ok}:
            group = [r for r in ok if r["variant"] == variant]
            pair_sims += [float(a["emb"] @ b["emb"]) for a, b in itertools.combinations(group, 2)]
            spreads.append(float(np.std([r["first"]["purchase_likelihood"] for r in group])))

        nearest = [float(np.max(index._similarity(e))) for e in emb]
        near_copies = 0
        for r in ok:
            if r["reviews"]:
                review_emb = encoder.encode([x["text"] for x in r["reviews"]], normalize_embeddings=True)
                if float(np.max(review_emb @ r["emb"])) >= NEAR_COPY:
                    near_copies += 1
        # Case-sensitive on purpose: brand names are capitalised, and a
        # case-insensitive match counted "...manageable, I guess." as the
        # brand Guess in the first run.
        brand_hits = [b for t in texts for b in brands if re.search(rf"\b{re.escape(b)}\b", t)]
        drift = [abs(r["first"]["purchase_likelihood"] - r["second"]["purchase_likelihood"])
                 for r in ok if r["second"]]

        summary[condition] = {
            "pairs": len(rows),
            "failures": len(rows) - len(ok),
            "persona_similarity": round(float(np.mean(pair_sims)), 3) if pair_sims else None,
            "likelihood_spread": round(float(np.mean(spreads)), 3) if spreads else None,
            "mean_likelihood": round(float(np.mean([r["first"]["purchase_likelihood"] for r in ok])), 3) if ok else None,
            "specificity": round(sum(1 for t in texts if words(t) & ASPECT_WORDS) / len(texts), 3) if texts else None,
            "aspects_per_reaction": round(float(np.mean([len(words(t) & ASPECT_WORDS) for t in texts])), 2) if texts else None,
            "real_review_sim": round(float(np.mean(nearest)), 3) if nearest else None,
            "near_copies": near_copies,
            "brand_leaks": len(brand_hits),
            "brand_leak_examples": sorted(set(brand_hits))[:10],
            "jargon_leaks": sum(1 for t in texts if JARGON_RE.search(t)),
            "rerun_drift": round(float(np.mean(drift)), 3) if drift else None,
        }

    out_dir = args.out / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    for rows in results.values():
        for r in rows:
            r.pop("emb", None)
    (out_dir / "results.json").write_text(json.dumps({"simulation": str(simulation.id), "product": product_text,
                                                      "model": settings.OLLAMA_MODEL, "summary": summary,
                                                      "rows": results}, indent=2, default=str), encoding="utf-8")

    metrics = ["failures", "persona_similarity", "likelihood_spread", "mean_likelihood", "specificity",
               "aspects_per_reaction", "real_review_sim", "near_copies", "brand_leaks", "jargon_leaks", "rerun_drift"]
    header = f"| metric | {' | '.join(conditions)} |\n|---|{'---|' * len(conditions)}\n"
    table = header + "".join(f"| {m} | {' | '.join(str(summary[c][m]) for c in conditions)} |\n" for m in metrics)

    samples = ["\n## Same pairs across conditions\n"]
    first_variant = results[conditions[0]][0]["variant"]
    for persona_name in [p.name for p in personas][:3]:
        samples.append(f"\n### {persona_name}\n")
        for c in conditions:
            row = next(r for r in results[c] if r["variant"] == first_variant and r["persona"] == persona_name)
            text = row["first"]["reaction_text"] if row["first"] else "(failed)"
            likelihood = row["first"]["purchase_likelihood"] if row["first"] else "-"
            samples.append(f"- **{c}** ({likelihood}): {text}\n")
    report = (f"# Persona prompt comparison\n\nSimulation `{simulation.id}` -- {product_text}\n\n"
              f"Model: {settings.LLM_PROVIDER}:{settings.OLLAMA_MODEL}\n\n{table}" + "".join(samples))
    (out_dir / "summary.md").write_text(report, encoding="utf-8")
    print("\n" + table)
    print(f"full results and sample texts: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
