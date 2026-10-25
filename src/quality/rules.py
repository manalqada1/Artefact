"""Small, dependency-free rules shared by the downloader and tests."""
from datetime import date
import re

FIELDS = (
    'trip_id', 'trip_start_timestamp', 'trip_seconds', 'trip_miles',
    'trip_total', 'pickup_community_area', 'payment_type',
)


def validate_interval(start, end):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    days = (last - first).days
    if not 1 <= days <= 31:
        raise ValueError('Choose a date interval between 1 and 31 days; end is exclusive.')
    return f'{first.isoformat()}_{last.isoformat()}'


def where_clause(start, end):
    validate_interval(start, end)
    return (f"trip_start_timestamp >= '{start}T00:00:00' AND "
            f"trip_start_timestamp < '{end}T00:00:00'")


def normalized_header(value):
    return re.sub(r'[^a-z0-9]+', '_', value.strip().lower()).strip('_')


def check_balance(raw, duplicates, rejected, accepted):
    if raw != duplicates + rejected + accepted:
        raise ValueError('Row counts do not reconcile.')
    if min(raw, duplicates, rejected, accepted) < 0:
        raise ValueError('Counts must be nonnegative.')
