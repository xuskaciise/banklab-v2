"""Query-parameter schemas of the reports (every field optional unless noted)."""

from datetime import date
from uuid import UUID

from ninja import Schema


class AsOfFilters(Schema):
    as_of: date | None = None  # default: current business date
    currency: str | None = None  # default: both currencies


class RangeFilters(Schema):
    date_from: date | None = None  # default: first day of the month of date_to
    date_to: date | None = None  # default: current business date
    currency: str | None = None


class StatementFilters(Schema):
    account_id: UUID  # required
    date_from: date | None = None
    date_to: date | None = None


class GlLedgerFilters(Schema):
    gl_account_id: UUID  # required
    currency: str  # required: USD or SOS
    date_from: date | None = None
    date_to: date | None = None


class TellerCashFilters(Schema):
    teller_session_id: UUID  # required


class DailyFilters(Schema):
    business_date: date | None = None  # default: current business date


class JournalFilters(Schema):
    business_date: date | None = None
    type: str | None = None
    status: str | None = None
    currency: str | None = None
    teller_id: UUID | None = None  # session member id of the user who posted
