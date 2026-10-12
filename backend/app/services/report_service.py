"""Implements the "Download Reports (PDF/CSV export)" use case (Fig 6.5,
Step 31), written for business readers rather than engineers.

Both formats are built from insights_service.build_insights() -- the same
plain-language summary the dashboard shows -- so a downloaded report never
disagrees with the screen. Technical internals (FID, engagement proxy, the
normalised PMF score, IDs, rule names, raw JSON) are left out on purpose;
they remain available through the analytics API for engineering use.

Both are generated on demand: results for a completed simulation never
change, and the data is small. Same "only a completed simulation has
results to report on" precondition as the analytics endpoint.
"""

import csv
import io
import uuid
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.models.product_variant import ProductVariant
from app.services import insights_service
from app.services.storage_service import get_path

REPORT_TITLE = "DryRunAI Launch Readiness Report"
INTEREST_COLOURS = {"Strong": "#1f7a4d", "Moderate": "#b7791f", "Low": "#c1352d"}
INK = colors.HexColor("#1a1a1f")
MUTED = colors.HexColor("#6b6b76")
RULE = colors.HexColor("#dcdce0")
PANEL = colors.HexColor("#f3f4f8")


class ReportDataError(Exception):
    pass


def _insights(db: Session, simulation_id: uuid.UUID) -> insights_service.SimulationInsights:
    try:
        return insights_service.build_insights(db, simulation_id)
    except insights_service.InsightsUnavailableError as e:
        raise ReportDataError(str(e)) from e


# --- CSV ----------------------------------------------------------------------

def generate_csv(db: Session, simulation_id: uuid.UUID) -> str:
    """Spreadsheet-friendly version: a short summary, one row per design
    option, then one row per customer reaction -- all in plain words."""
    ins = _insights(db, simulation_id)
    buffer = io.StringIO()
    w = csv.writer(buffer)

    w.writerow([REPORT_TITLE])
    w.writerow(["Product", " ".join(p for p in (ins.product_brand, ins.product_name) if p)])
    w.writerow(["Price tested", ins.price_text])
    w.writerow(["Target customers", ins.audience_text])
    if ins.messaging:
        w.writerow(["Marketing message", ins.messaging])
    w.writerow(["Customer profiles tested", ins.profiles_tested])
    w.writerow(["Design options compared", ins.options_tested])
    w.writerow(["Verdict", ins.verdict])
    w.writerow(["Summary", ins.bottom_line])
    w.writerow([])

    w.writerow(["DESIGN OPTIONS"])
    w.writerow(["Option", "Colourway", "Recommended", "Average purchase likelihood (%)", "Likely to buy",
                "Undecided", "Unlikely to buy", "Tone of comments", "Appeals most to", "Concerns"])
    for o in ins.options:
        w.writerow([o.label, o.colourway, "Yes" if o.is_recommended else "", o.purchase_intent_pct,
                    f"{o.likely_buyers} of {o.profiles}", o.undecided, o.unlikely_buyers, o.reception,
                    "; ".join(o.appeals_most_to), " | ".join(o.concerns)])
    w.writerow([])

    w.writerow(["CUSTOMER REACTIONS"])
    w.writerow(["Option", "Colourway", "Customer profile", "Buying intent", "Purchase likelihood (%)",
                "Tone of comment", "What they said"])
    for o in ins.options:
        for r in o.reactions:
            w.writerow([o.label, o.colourway, r.profile, r.buying_intent, r.likelihood_pct, r.reaction, r.comment])
    w.writerow([])

    w.writerow(["RECOMMENDED NEXT STEPS"])
    for i, step in enumerate(ins.next_steps, start=1):
        w.writerow([i, step])
    w.writerow([])
    w.writerow(["Note", ins.disclaimer])
    return buffer.getvalue()


# --- PDF ----------------------------------------------------------------------

def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=20, leading=24, alignment=TA_LEFT, textColor=INK, spaceAfter=2),
        "subtitle": ParagraphStyle("st", parent=base["Normal"], fontSize=10, textColor=MUTED, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, textColor=INK, spaceBefore=10, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=11.5, textColor=INK, spaceBefore=4, spaceAfter=4),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=9.5, leading=13, textColor=INK),
        "small": ParagraphStyle("s", parent=base["Normal"], fontSize=8.5, leading=11, textColor=MUTED),
        "label": ParagraphStyle("l", parent=base["Normal"], fontSize=8.5, leading=11, textColor=MUTED),
        "verdict": ParagraphStyle("v", parent=base["Normal"], fontSize=13, leading=17, textColor=INK),
        "quote": ParagraphStyle("q", parent=base["Normal"], fontSize=9, leading=12.5, textColor=INK,
                                fontName="Helvetica-Oblique", leftIndent=6),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=8.5, leading=11, textColor=INK),
    }


def _p(text, style) -> Paragraph:
    return Paragraph(escape(str(text)), style)


def _image(db: Session, variant_id: str, size: float):
    variant = db.get(ProductVariant, uuid.UUID(variant_id))
    try:
        return Image(str(get_path(variant.image_path)), width=size, height=size)
    except Exception:  # a missing image must not break the whole report
        return Paragraph("(image unavailable)", _styles()["small"])


def _bullets(items, style) -> ListFlowable:
    return ListFlowable([ListItem(_p(i, style), leftIndent=10) for i in items], bulletType="bullet",
                        start="•", leftIndent=10, bulletFontSize=8)


def generate_pdf(db: Session, simulation_id: uuid.UUID) -> bytes:
    ins = _insights(db, simulation_id)
    s = _styles()
    best = ins.options[0]
    verdict_colour = INTEREST_COLOURS[best.interest_level]
    product_line = " ".join(p for p in (ins.product_brand, ins.product_name) if p)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=REPORT_TITLE, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.6 * cm, bottomMargin=1.6 * cm)
    width = doc.width
    story = [
        _p("Launch Readiness Report", s["title"]),
        _p(f"{product_line}{' · ' + ins.product_category if ins.product_category else ''} · {date.today():%d %B %Y}",
           s["subtitle"]),
    ]

    # The bottom line.
    box = Table([[Paragraph(f'<font color="{verdict_colour}"><b>{escape(ins.verdict)}</b></font>', s["verdict"])],
                 [_p(ins.bottom_line, s["body"])]], colWidths=[width])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PANEL),
                             ("LINEBEFORE", (0, 0), (0, -1), 4, colors.HexColor(verdict_colour)),
                             ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                             ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [_p("The bottom line", s["h2"]), box]

    # What we tested.
    setup = [("Price tested", ins.price_text), ("Target customers", ins.audience_text)]
    if ins.messaging:
        setup.append(("Marketing message", f"“{ins.messaging}”"))
    setup += [("Customer profiles", f"{ins.profiles_tested} simulated customer types, each reacting to every design"),
              ("Design options", f"{ins.options_tested} generated designs compared")]
    setup_table = Table([[_p(k, s["label"]), _p(v, s["body"])] for k, v in setup], colWidths=[4 * cm, width - 4 * cm])
    setup_table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                     ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [_p("What we tested", s["h2"]), setup_table]

    # How the options compared.
    header = ["Option", "Design", "Colourway", "Avg. purchase\nlikelihood", "Would likely\nbuy", "Tone of\ncomments"]
    rows = [[_p(h, s["label"]) for h in header]]
    for o in ins.options:
        name = f"<b>{escape(o.label)}</b>" + ('<br/><font color="#1f7a4d" size="7.5">Recommended</font>' if o.is_recommended else "")
        rows.append([Paragraph(name, s["cell"]), _image(db, o.variant_id, 1.9 * cm), _p(o.colourway, s["cell"]),
                     Paragraph(f'<font color="{INTEREST_COLOURS[o.interest_level]}"><b>{o.purchase_intent_pct}%</b></font>'
                               f'<br/><font size="7.5" color="#6b6b76">{o.interest_level} interest</font>', s["cell"]),
                     _p(f"{o.likely_buyers} of {o.profiles}", s["cell"]),
                     _p(f"{o.reception} ({o.liked} positive, {o.neutral} neutral, {o.disliked} critical)", s["cell"])])
    compare = Table(rows, colWidths=[2.3 * cm, 2.3 * cm, 3.2 * cm, 2.7 * cm, 2.2 * cm, width - 12.7 * cm], repeatRows=1)
    compare.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                 ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eef7f1"))]))
    story += [_p("How the options compared", s["h2"]), compare,
              _p("Purchase likelihood is the average chance of buying that the customer profiles gave each design. "
                 "“Would likely buy” counts profiles at 60% or more.", s["small"])]

    # One section per option.
    for o in ins.options:
        title = f"{o.label}: {o.colourway}" + ("  (recommended)" if o.is_recommended else "")
        details = []
        if o.appeals_most_to:
            details += [_p("Appeals most to", s["label"]), _p(", ".join(o.appeals_most_to), s["body"]), Spacer(1, 4)]
        if o.least_interested:
            details += [_p("Least interested", s["label"]), _p(", ".join(o.least_interested), s["body"]), Spacer(1, 4)]
        if o.themes:
            details += [_p("What customers talked about", s["label"]),
                        _p(", ".join(f"{t['topic']} ({t['mentions']} of {o.profiles})" for t in o.themes), s["body"]),
                        Spacer(1, 4)]
        details += [_p("Concerns", s["label"]),
                    _bullets(o.concerns, s["body"]) if o.concerns else _p("No major concerns raised.", s["body"])]
        side = Table([[_image(db, o.variant_id, 4.2 * cm), details]], colWidths=[4.6 * cm, width - 4.6 * cm])
        side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        block = [_p(title, s["h3"]), side]
        quotes = [(q, label) for q, label in ((o.best_quote, "Most positive"), (o.worst_quote, "Most critical")) if q]
        if quotes:
            block.append(Spacer(1, 4))
            for q, label in quotes:
                block += [_p(f"{label}: {q.profile} ({q.buying_intent.lower()})", s["label"]),
                          _p(f"“{q.comment}”", s["quote"]), Spacer(1, 3)]
        story += [Spacer(1, 6), KeepTogether(block)]

    story += [_p("Recommended next steps", s["h2"]),
              ListFlowable([ListItem(_p(step, s["body"])) for step in ins.next_steps], bulletType="1", leftIndent=14),
              Spacer(1, 14), _p(ins.disclaimer, s["small"])]

    doc.build(story)
    return buffer.getvalue()
