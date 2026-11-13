from decimal import Decimal

import pytest

from apps.banking.receipt_text import amount_in_words

D = Decimal


@pytest.mark.parametrize(
    ("amount", "currency", "expected"),
    [
        ("0", "USD", "Zero US Dollars and 00/100"),
        ("0.05", "USD", "Zero US Dollars and 05/100"),
        ("1", "USD", "One US Dollars and 00/100"),
        ("15", "USD", "Fifteen US Dollars and 00/100"),
        ("100", "USD", "One hundred US Dollars and 00/100"),
        ("1001", "USD", "One thousand one US Dollars and 00/100"),
        (
            "1000000.50",
            "USD",
            "One million US Dollars and 50/100",
        ),
        ("5000000000", "SOS", "Five billion Somali Shillings and 00/100"),
        ("-250", "USD", "Two hundred fifty US Dollars and 00/100"),
        (
            "9999999999999999.99",
            "USD",
            "Nine thousand nine hundred ninety-nine trillion nine hundred ninety-nine billion "
            "nine hundred ninety-nine million nine hundred ninety-nine thousand "
            "nine hundred ninety-nine US Dollars and 99/100",
        ),
        ("10.005", "USD", "Ten US Dollars and 01/100"),
        ("10.004", "USD", "Ten US Dollars and 00/100"),
        ("7", "EUR", "Seven EUR and 00/100"),
    ],
)
def test_amount_in_words(amount, currency, expected):
    assert amount_in_words(D(amount), currency) == expected
