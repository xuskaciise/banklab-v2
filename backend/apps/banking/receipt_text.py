"""Text helpers for receipts: amount in words, masking and readable formatting."""

import re
from decimal import Decimal

_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
_SCALES = ((10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (10**3, "thousand"))
CURRENCY_NAME = {"USD": "US Dollars", "SOS": "Somali Shillings"}


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


def title_case(name: str) -> str:
    """'hussein isse ali' -> 'Hussein Isse Ali' (keeps hyphenated parts readable)."""
    return " ".join(
        "-".join(p[:1].upper() + p[1:].lower() for p in word.split("-"))
        for word in (name or "").split()
    )


def mask_id(value: str) -> str:
    """Show only the first and last three characters: P009188181 -> P00****181."""
    v = (value or "").strip()
    if len(v) <= 6:
        return v[:1] + "*" * max(len(v) - 1, 0)
    return f"{v[:3]}{'*' * min(len(v) - 6, 6)}{v[-3:]}"


def format_phone(value: str) -> str:
    """0615844908 -> 061 584 4908; other lengths are grouped in threes."""
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return value or ""
    if len(digits) == 10:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    if digits.startswith("252") and len(digits) == 12:
        return f"+252 {digits[3:5]} {digits[5:8]} {digits[8:]}"
    return " ".join(digits[i : i + 3] for i in range(0, len(digits), 3))
