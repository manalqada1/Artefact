"""Business comparisons derived from published gold sums and counts.

Revenue means accepted, source-reported trip totals, not profit.
Keep Decimal arithmetic until the presentation boundary.
"""
from decimal import Decimal


def _amount(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError('Gold amounts must be finite and nonnegative.')
    return result


def _rank(rows, field, name):
    ordered = sorted(rows, key=lambda r: (-r[field], r['pickup_area']))
    previous = None
    rank = 0
    for position, row in enumerate(ordered, 1):
        if previous is None or row[field] != previous:
            rank = position
        row[name] = rank
        previous = row[field]


def summarize_areas(rows, min_trips=100):
    """Aggregate daily-area gold rows over the entire published interval.

    All shares use known-area revenue unless explicitly named total.
    Minimum trips is a visibility filter, not a confidence interval.
    """
    if min_trips < 1:
        raise ValueError('Minimum trips must be positive.')
    groups = {}
    for row in rows:
        name = str(row['pickup_area']).strip()
        name = name if name and name.lower() not in ('unknown', 'none', 'nan') else 'Unknown'
        count = int(row['trip_count'])
        if count <= 0:
            raise ValueError('Each gold group must contain positive trip counts.')
        group = groups.setdefault(name, {
            'pickup_area': name, 'trip_count': 0, 'recorded_trip_total_usd': Decimal('0')
        })
        group['trip_count'] += count
        group['recorded_trip_total_usd'] += _amount(row['recorded_trip_total_usd'])
    all_rows = list(groups.values())
    known = [r for r in all_rows if r['pickup_area'] != 'Unknown']
    unknown = groups.get('Unknown', {
        'trip_count': 0, 'recorded_trip_total_usd': Decimal('0')
    })
    known_amount = sum((r['recorded_trip_total_usd'] for r in known), Decimal('0'))
    total_amount = known_amount + unknown['recorded_trip_total_usd']
    known_count = sum(r['trip_count'] for r in known)
    for row in known:
        row['average_recorded_total_usd'] = row['recorded_trip_total_usd'] / row['trip_count']
        row['known_revenue_share_pct'] = (
            100 * row['recorded_trip_total_usd'] / known_amount if known_amount else None
        )
    _rank(known, 'trip_count', 'trip_rank')
    _rank(known, 'recorded_trip_total_usd', 'revenue_rank')
    ranked = sorted(known, key=lambda r: (-r['recorded_trip_total_usd'], r['pickup_area']))
    eligible = sorted(
        [r for r in known if r['trip_count'] >= min_trips],
        key=lambda r: (-r['average_recorded_total_usd'], r['pickup_area']),
    )
    top_n = min(3, len(known))
    top_amount = sum((r['recorded_trip_total_usd'] for r in ranked[:top_n]), Decimal('0'))
    return {
        'ranking': ranked,
        'eligible_yield_ranking': eligible,
        'min_trips': min_trips,
        'known_trip_count': known_count,
        'known_revenue_usd': known_amount,
        'total_revenue_usd': total_amount,
        'unknown_trip_count': unknown['trip_count'],
        'unknown_revenue_usd': unknown['recorded_trip_total_usd'],
        'unknown_revenue_share_pct': (
            100 * unknown['recorded_trip_total_usd'] / total_amount if total_amount else None
        ),
        'known_average_recorded_total_usd': known_amount / known_count if known_count else None,
        'top_n': top_n,
        'top_n_known_revenue_share_pct': 100 * top_amount / known_amount if known_amount else None,
    }


def business_insights(summary):
    """Only observations calculated from the published records; no forecasts."""
    ranked = summary['ranking']
    if not ranked:
        return ['No accepted trips have a known pickup area, so area comparisons are unavailable.']
    revenue_leaders = [r for r in ranked if r['revenue_rank'] == 1]
    trip_leaders = [r for r in ranked if r['trip_rank'] == 1]
    revenue_names = ', '.join(r['pickup_area'] for r in revenue_leaders)
    trip_names = ', '.join(r['pickup_area'] for r in trip_leaders)
    messages = []
    if len(revenue_leaders) == len(trip_leaders) == 1:
        lead, busy = revenue_leaders[0], trip_leaders[0]
        if lead['pickup_area'] != busy['pickup_area']:
            messages.append(
                f"Volume and recorded revenue have different leaders: area {busy['pickup_area']} "
                f"has the most accepted trips ({busy['trip_count']:,}), while area {lead['pickup_area']} "
                f"has the highest recorded revenue (${lead['recorded_trip_total_usd']:,.2f})."
            )
        else:
            messages.append(
                f"Area {lead['pickup_area']} leads both accepted trip volume and recorded revenue: "
                f"{lead['trip_count']:,} trips and ${lead['recorded_trip_total_usd']:,.2f}."
            )
    else:
        messages.append(
            f"Highest recorded revenue: area(s) {revenue_names}. "
            f"Highest accepted trip volume: area(s) {trip_names}. Tied leaders are shown together."
        )
    eligible = summary['eligible_yield_ranking']
    if eligible:
        top = eligible[0]
        tied = [r for r in eligible if r['average_recorded_total_usd'] == top['average_recorded_total_usd']]
        names = ', '.join(r['pickup_area'] for r in tied)
        baseline = summary['known_average_recorded_total_usd']
        comparison = ''
        if baseline and baseline > 0:
            pct = 100 * (top['average_recorded_total_usd'] / baseline - 1)
            direction = 'above' if pct >= 0 else 'below'
            comparison = f" ({abs(pct):.1f}% {direction} the trip-weighted known-area average)"
        counts = ', '.join(f"{r['pickup_area']}: {r['trip_count']:,} trips" for r in tied)
        messages.append(
            f"Among known areas with at least {summary['min_trips']:,} accepted trip(s), "
            f"area(s) {names} have the highest observed average recorded amount per trip: "
            f"${top['average_recorded_total_usd']:,.2f}{comparison}. Sample sizes: {counts}."
        )
    else:
        messages.append(f"No known area meets the {summary['min_trips']:,}-trip threshold.")
    share = summary['top_n_known_revenue_share_pct']
    if share is not None:
        messages.append(
            f"The top {summary['top_n']} area(s) account for {share:.1f}% of recorded revenue "
            "assigned to known pickup areas in the selected period."
        )
    missing_share = summary['unknown_revenue_share_pct']
    if missing_share is not None:
        messages.append(
            f"${summary['unknown_revenue_usd']:,.2f} ({missing_share:.1f}% of all accepted "
            f"recorded revenue) has no known pickup area. It is included in headline totals "
            "and excluded from geographic rankings."
        )
    return messages


def summarize_days(rows):
    days = sorted(rows, key=lambda r: str(r['trip_date']))
    if not days:
        return None
    if len({str(r['trip_date']) for r in days}) != len(days):
        raise ValueError('Daily gold keys must be unique.')
    total_count = sum(int(r['trip_count']) for r in days)
    total_amount = sum((_amount(r['recorded_trip_total_usd']) for r in days), Decimal('0'))
    return {
        'day_count': len(days),
        'average_recorded_total_usd': total_amount / total_count if total_count else None,
        'revenue_leaders': [r for r in days if _amount(r['recorded_trip_total_usd']) ==
                            max(_amount(d['recorded_trip_total_usd']) for d in days)],
        'trip_leaders': [r for r in days if int(r['trip_count']) ==
                         max(int(d['trip_count']) for d in days)],
    }
