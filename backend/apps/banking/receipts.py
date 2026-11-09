"""PDF receipt of a posted / reversed transaction (reportlab)."""

from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from . import txn_core as core
from .models import Transaction, TxnStatus, TxnType

_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
_SCALES = ((10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (10**3, "thousand"))
CURRENCY_NAME = {"USD": "US Dollars", "SOS": "Somali Shillings"}
TYPE_LABEL = {
    TxnType.CASH_DEPOSIT: "Cash Deposit",
    TxnType.CASH_WITHDRAWAL: "Cash Withdrawal",
    TxnType.TRANSFER: "Transfer",
    TxnType.REVERSAL: "Reversal",
}


def _below_1000(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(f"{_ONES[n // 100]} hundred")
        n %= 100
    if n >= 20:
        parts.append(_TENS[n // 10] + (f"-{_ONES[n % 10]}" if n % 10 else ""))
    elif n or not parts:
        parts.append(_ONES[n])
    return " ".join(parts)


def number_to_words(n: int) -> str:
    if n < 1000:
        return _below_1000(n)
    parts = []
    for size, name in _SCALES:
        if n >= size:
            parts.append(f"{_below_1000(n // size)} {name}")
            n %= size
    if n:
        parts.append(_below_1000(n))
    return " ".join(parts)


def amount_in_words(amount: Decimal, currency: str) -> str:
    whole, cents = divmod(int((abs(amount) * 100).to_integral_value()), 100)
    words = number_to_words(whole).capitalize()
    return f"{words} {CURRENCY_NAME.get(currency, currency)} and {cents:02d}/100"


def render_receipt(txn: Transaction) -> bytes:
    """Receipt for a posted or reversed transaction; anything else is refused (409)."""
    if txn.status not in (TxnStatus.POSTED, TxnStatus.REVERSED):
        raise core._conflict("no_receipt", "A receipt exists only for posted transactions")
    buf = BytesIO()
    width, height = A5
    pdf = canvas.Canvas(buf, pagesize=A5)
    pdf.setTitle(f"Receipt {txn.ref_no}")
    left, right = 15 * mm, width - 15 * mm
    y = height - 18 * mm
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(left, y, txn.bank.name)
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.grey)
    pdf.drawRightString(right, y, "Training bank - not a real bank")
    pdf.setFillColor(colors.black)
    y -= 5 * mm
    pdf.line(left, y, right, y)
    y -= 8 * mm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(left, y, f"{TYPE_LABEL.get(txn.type, txn.type)} Receipt")
    if txn.status == TxnStatus.REVERSED:
        pdf.setFillColor(colors.red)
        pdf.drawRightString(right, y, "REVERSED")
        pdf.setFillColor(colors.black)
    rows = [
        ("Reference", txn.ref_no),
        ("Date", txn.business_date.strftime("%d %b %Y")),
        ("Account", f"{txn.account.account_no} - {txn.account.customer.display_name}"),
    ]
    if txn.counter_account_id:
        rows.append(
            (
                "To account",
                f"{txn.counter_account.account_no} - {txn.counter_account.customer.display_name}",
            )
        )
    rows.append(("Amount", f"{txn.currency} {txn.amount:,.2f}"))
    rows.append(("In words", amount_in_words(txn.amount, txn.currency)))
    if txn.party_name:
        label = "Depositor" if txn.type == TxnType.CASH_DEPOSIT else "Withdrawn by"
        rows += [
            (label, txn.party_name),
            ("ID no.", txn.party_id_no),
            ("Phone", txn.party_phone),
        ]
    if txn.narration:
        rows.append(("Narration", txn.narration))
    teller = txn.created_by.user
    rows.append(("Served by", teller.full_name or teller.username))
    y -= 9 * mm
    for label, value in rows:
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(colors.grey)
        pdf.drawString(left, y, label)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold" if label == "Amount" else "Helvetica", 10)
        pdf.drawString(left + 30 * mm, y, str(value)[:70])
        y -= 6.5 * mm
    y = 32 * mm
    for x0, caption in ((left, "Customer signature"), (width / 2 + 3 * mm, "Teller signature")):
        pdf.line(x0, y, x0 + 52 * mm, y)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(x0, y - 4 * mm, caption)
    pdf.showPage()
    pdf.save()
    return buf.getvalue()
