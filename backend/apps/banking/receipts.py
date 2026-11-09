"""PDF receipt of a posted / reversed transaction (reportlab, A4)."""

from io import BytesIO

from django.utils import timezone
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from . import txn_core as core
from .models import Transaction, TxnStatus, TxnType
from .receipt_text import (  # noqa: F401  (re-exported for callers and tests)
    CURRENCY_NAME,
    amount_in_words,
    format_phone,
    mask_id,
    number_to_words,
    title_case,
)

# Colours from docs/design/theme.md (PDF cannot read the web CSS tokens).
PRIMARY = colors.HexColor("#1E3A8A")  # bank-primary
NAVY = colors.HexColor("#0F2942")  # bank-navy
SUCCESS = colors.HexColor("#047857")  # fin-success-dark
DANGER = colors.HexColor("#B91C1C")  # fin-danger
MUTED = colors.HexColor("#64748B")  # text-muted
LINE = colors.HexColor("#E2E8F0")  # border
SOFT = colors.HexColor("#F1F5F9")  # surface

TYPE_LABEL = {
    TxnType.CASH_DEPOSIT: "Cash Deposit",
    TxnType.CASH_WITHDRAWAL: "Cash Withdrawal",
    TxnType.TRANSFER: "Transfer",
    TxnType.REVERSAL: "Reversal",
}
W, H = A4
L, R = 20 * mm, W - 20 * mm


def _acct(account) -> str:
    return str(account.account_no).zfill(8)


def _watermark(pdf):
    pdf.saveState()
    pdf.setFillColor(colors.Color(0.5, 0.5, 0.5, alpha=0.08))
    pdf.setFont("Helvetica-Bold", 110)
    pdf.translate(W / 2, H / 2)
    pdf.rotate(35)
    pdf.drawCentredString(0, -30, "TRAINING")
    pdf.restoreState()


def _header(pdf, txn, branch):
    y = H - 22 * mm
    pdf.setFillColor(PRIMARY)  # logo placeholder: rounded square with initials
    pdf.roundRect(L, y - 4 * mm, 14 * mm, 14 * mm, 3 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    initials = "".join(w[0] for w in txn.bank.name.split()[:2]).upper()
    pdf.drawCentredString(L + 7 * mm, y + 0.5 * mm, initials)
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(L + 18 * mm, y + 3 * mm, txn.bank.name)
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(MUTED)
    pdf.drawString(L + 18 * mm, y - 2.5 * mm, "Training bank - not a real bank")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.setFillColor(NAVY)
    if branch:
        pdf.drawRightString(R, y + 3 * mm, f"{branch.name} ({branch.code})")
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(MUTED)
        pdf.drawRightString(R, y - 2.5 * mm, branch.address or "No address on file")
    pdf.setFillColor(PRIMARY)
    pdf.rect(L, y - 9 * mm, R - L, 1.6 * mm, fill=1, stroke=0)
    return y - 20 * mm


def _title(pdf, txn, y):
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 14)
    title = f"{TYPE_LABEL.get(txn.type, txn.type)} Receipt".upper()
    pdf.drawString(L, y, " ".join(title))  # letter-spaced
    reversed_ = txn.status == TxnStatus.REVERSED
    label, colour = ("REVERSED", DANGER) if reversed_ else ("COMPLETED", SUCCESS)
    pdf.setFont("Helvetica-Bold", 9)
    bw = pdf.stringWidth(label, "Helvetica-Bold", 9) + 8 * mm
    pdf.setStrokeColor(colour)
    pdf.setFillColor(colors.white)
    pdf.roundRect(R - bw, y - 2 * mm, bw, 7 * mm, 3.5 * mm, fill=1, stroke=1)
    pdf.setFillColor(colour)
    pdf.drawCentredString(R - bw / 2, y, label)
    return y - 12 * mm


def _summary(pdf, txn, y):
    top = y
    pdf.setFillColor(SOFT)
    pdf.setStrokeColor(LINE)
    pdf.roundRect(L, top - 34 * mm, R - L, 34 * mm, 3 * mm, fill=1, stroke=1)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(L + 6 * mm, top - 7 * mm, "Amount")
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(L + 6 * mm, top - 16 * mm, f"{txn.currency} {txn.amount:,.2f}")
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawString(L + 6 * mm, top - 22.5 * mm, amount_in_words(txn.amount, txn.currency)[:90])
    when = timezone.localtime(txn.created_at)
    for i, (label, value) in enumerate(
        (("Reference", txn.ref_no), ("Date & time", when.strftime("%d %b %Y, %I:%M %p")))
    ):
        x = L + 6 * mm + i * 75 * mm
        pdf.setFont("Helvetica", 8.5)
        pdf.setFillColor(MUTED)
        pdf.drawString(x, top - 28 * mm, label)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColor(NAVY)
        pdf.drawString(x + 22 * mm, top - 28 * mm, value)
    return top - 44 * mm


def _section(pdf, title, rows, y):
    pdf.setFillColor(PRIMARY)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(L, y, title.upper())
    y -= 3 * mm
    for label, value in rows:
        pdf.setStrokeColor(LINE)
        pdf.line(L, y, R, y)
        y -= 6 * mm
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(MUTED)
        pdf.drawString(L, y, label)
        pdf.setFont("Helvetica-Bold", 10.5)
        pdf.setFillColor(NAVY)
        pdf.drawRightString(R, y, str(value or "-")[:70])
        y -= 2.5 * mm
    pdf.line(L, y, R, y)
    return y - 9 * mm


def _sections(txn, branch):
    teller = txn.created_by.user
    acct = txn.account
    out = []
    if txn.counter_account_id:
        to = txn.counter_account
        out.append(
            (
                "From account",
                [
                    ("Account number", _acct(acct)),
                    ("Account name", title_case(acct.customer.display_name)),
                ],
            )
        )
        out.append(
            (
                "To account",
                [
                    ("Account number", _acct(to)),
                    ("Account name", title_case(to.customer.display_name)),
                ],
            )
        )
    else:
        out.append(
            (
                "Account details",
                [
                    ("Account number", _acct(acct)),
                    ("Account name", title_case(acct.customer.display_name)),
                ],
            )
        )
    if txn.party_name:
        who = "Depositor" if txn.type == TxnType.CASH_DEPOSIT else "Withdrawer"
        out.append(
            (
                f"{who} details",
                [
                    ("Name", title_case(txn.party_name)),
                    ("ID number", mask_id(txn.party_id_no)),
                    ("Phone", format_phone(txn.party_phone)),
                ],
            )
        )
    details = []
    if txn.teller_session_id:
        details.append(("Till", txn.teller_session.till.code))
    if branch:
        details.append(("Branch", f"{branch.name} ({branch.code})"))
    if txn.reversal_of_id:
        details.append(("Reverses", txn.reversal_of.ref_no))
    if txn.narration:
        details.append(("Narration", txn.narration))
    details.append(("Served by", title_case(teller.full_name or teller.username)))
    out.append(("Transaction details", details))
    return out


def _signatures_and_footer(pdf, txn, party):
    y = 52 * mm
    left_caption = f"{party} signature" if party else "Customer signature"
    for x0, caption in ((L, left_caption), (W / 2 + 6 * mm, "Teller signature / stamp")):
        pdf.setStrokeColor(NAVY)
        pdf.line(x0, y, x0 + 70 * mm, y)
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(MUTED)
        pdf.drawString(x0, y - 5 * mm, caption)
    qr = QrCodeWidget(txn.ref_no)
    x1, y1, x2, y2 = qr.getBounds()
    size = 20 * mm
    d = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    d.add(qr)
    renderPDF.draw(d, pdf, R - size, 14 * mm)
    pdf.setStrokeColor(LINE)
    pdf.line(L, 36 * mm, R - size - 4 * mm, 36 * mm)
    pdf.setFont("Helvetica", 8.5)
    pdf.setFillColor(MUTED)
    pdf.drawString(
        L,
        30 * mm,
        "Thank you for banking with us. Please keep this receipt for your records.",
    )
    printed = timezone.localtime().strftime("%d %b %Y, %I:%M %p")
    pdf.drawString(L, 24 * mm, f"Printed {printed}  |  Ref {txn.ref_no}  |  Page 1 of 1")
    pdf.drawString(
        L, 18 * mm, "Training bank - not a real bank. Not valid as a financial document."
    )


def render_receipt(txn: Transaction) -> bytes:
    """Receipt for a posted or reversed transaction; anything else is refused (409)."""
    if txn.status not in (TxnStatus.POSTED, TxnStatus.REVERSED):
        raise core._conflict("no_receipt", "A receipt exists only for posted transactions")
    branch = txn.teller_session.till.branch if txn.teller_session_id else None
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    pdf.setTitle(f"Receipt {txn.ref_no}")
    _watermark(pdf)
    y = _header(pdf, txn, branch)
    y = _title(pdf, txn, y)
    y = _summary(pdf, txn, y)
    for title, rows in _sections(txn, branch):
        y = _section(pdf, title, rows, y)
    party = None
    if txn.party_name:
        party = "Depositor" if txn.type == TxnType.CASH_DEPOSIT else "Withdrawer"
    _signatures_and_footer(pdf, txn, party)
    pdf.showPage()
    pdf.save()
    return buf.getvalue()
