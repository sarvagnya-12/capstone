"""Implements the "Download Reports (PDF/CSV export)" use case (Fig 6.5,
Step 31). Both formats are generated on-demand rather than cached --
results for a `completed` simulation never change, and the data volume
here is small enough that caching isn't worth the added invalidation
complexity. Same "only a completed simulation has a Recommendation to
report on" precondition as Step 30's analytics endpoint.
"""

import csv
import io
import uuid

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback import Feedback
from app.models.persona import Persona
from app.models.product_variant import ProductVariant
from app.models.recommendation import Recommendation
from app.models.simulation import Simulation

REPORT_CSV_FIELDS = [
    "iteration_number", "variant_id", "persona_name", "generation_method", "fid_score",
    "qualitative_text", "purchase_likelihood", "sentiment_label", "sentiment_score", "risk_flags",
]


class ReportDataError(Exception):
    pass


def _load_simulation_and_recommendation(db: Session, simulation_id: uuid.UUID) -> tuple[Simulation, Recommendation]:
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise ReportDataError(f"Simulation {simulation_id} not found")
    recommendation = db.query(Recommendation).filter(Recommendation.simulation_id == simulation_id).one_or_none()
    if recommendation is None:
        raise ReportDataError(f"No completed results yet for simulation {simulation_id}")
    return simulation, recommendation


def _load_report_rows(db: Session, simulation_id: uuid.UUID) -> list[dict]:
    """One row per persona x variant feedback entry, joined against persona
    name and variant metadata for a human-readable export -- flattening
    Feedback (+ its Persona/ProductVariant context), per this step's own
    plan text, rather than a raw table dump."""
    joined = db.execute(
        select(Feedback, Persona.name, ProductVariant.generation_method, ProductVariant.fid_score)
        .join(Persona, Feedback.persona_id == Persona.id)
        .join(ProductVariant, Feedback.variant_id == ProductVariant.id)
        .where(Feedback.simulation_id == simulation_id)
        .order_by(Feedback.iteration_number, Feedback.variant_id, Persona.name)
    ).all()

    return [
        {
            "iteration_number": fb.iteration_number,
            "variant_id": str(fb.variant_id),
            "persona_name": persona_name,
            "generation_method": generation_method,
            "fid_score": fid_score,
            "qualitative_text": fb.qualitative_text,
            "purchase_likelihood": fb.purchase_likelihood,
            "sentiment_label": fb.sentiment_label.value if fb.sentiment_label else "",
            "sentiment_score": fb.sentiment_score,
            "risk_flags": "; ".join(f"{f['rule']} ({f['severity']})" for f in (fb.risk_flags or [])),
        }
        for fb, persona_name, generation_method, fid_score in joined
    ]


def generate_csv(db: Session, simulation_id: uuid.UUID) -> str:
    simulation, recommendation = _load_simulation_and_recommendation(db, simulation_id)
    rows = _load_report_rows(db, simulation_id)

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["DryRunAI Simulation Report"])
    writer.writerow(["simulation_id", str(simulation_id)])
    writer.writerow(["status", simulation.status.value])
    writer.writerow(["recommended_variant_id", str(recommendation.recommended_variant_id)])
    writer.writerow(["pmf_score", recommendation.pmf_score])
    writer.writerow([])

    writer.writerow(["-- Feedback Detail --"])
    writer.writerow(REPORT_CSV_FIELDS)
    for row in rows:
        writer.writerow([row[field] for field in REPORT_CSV_FIELDS])
    writer.writerow([])

    writer.writerow(["-- Final Ranking --"])
    writer.writerow(["rank", "variant_id", "pmf_score"])
    for rank, entry in enumerate(recommendation.ranking, start=1):
        writer.writerow([rank, entry["variant_id"], entry["pmf_score"]])

    return buffer.getvalue()


def generate_pdf(db: Session, simulation_id: uuid.UUID) -> bytes:
    simulation, recommendation = _load_simulation_and_recommendation(db, simulation_id)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title="DryRunAI Simulation Report")
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("DryRunAI Simulation Report", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Simulation ID: {simulation_id}", styles["Normal"]))
    story.append(Paragraph(f"Status: {simulation.status.value}", styles["Normal"]))
    story.append(Paragraph(f"Pricing strategy: {simulation.pricing_strategy}", styles["Normal"]))
    story.append(Paragraph(f"Target demographic: {simulation.target_demographic}", styles["Normal"]))
    if simulation.promotional_messaging:
        story.append(Paragraph(f"Promotional messaging: {simulation.promotional_messaging}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Recommendation", styles["Heading2"]))
    story.append(Paragraph(recommendation.summary_text, styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Variant Ranking (PMF Score)", styles["Heading2"]))
    ranking_data = [["Rank", "Variant ID", "PMF Score"]]
    for rank, entry in enumerate(recommendation.ranking, start=1):
        ranking_data.append([str(rank), entry["variant_id"][:8], f"{entry['pmf_score']:.1f}"])
    ranking_table = Table(ranking_data, hAlign="LEFT")
    ranking_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(ranking_table)
    story.append(Spacer(1, 12))

    # Risk flags are denormalized across every Feedback row for a variant
    # (risk_service.py writes the same list to each row) -- dedupe by
    # variant so each triggered rule is listed once, not once per persona.
    variant_ids = [uuid.UUID(entry["variant_id"]) for entry in recommendation.ranking]
    risk_rows = list(
        db.execute(
            select(Feedback.variant_id, Feedback.risk_flags).where(
                Feedback.variant_id.in_(variant_ids), Feedback.risk_flags.isnot(None)
            )
        ).all()
    )
    seen_variants: set[uuid.UUID] = set()
    risk_lines: list[str] = []
    for variant_id, flags in risk_rows:
        if variant_id in seen_variants or not flags:
            continue
        seen_variants.add(variant_id)
        for flag in flags:
            risk_lines.append(f"{str(variant_id)[:8]}: {flag['rule']} ({flag['severity']}) -- {flag['detail']}")

    story.append(Paragraph("Key Risk Flags", styles["Heading2"]))
    if risk_lines:
        for line in risk_lines:
            story.append(Paragraph(line, styles["Normal"]))
    else:
        story.append(Paragraph("No risk flags were triggered.", styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()
