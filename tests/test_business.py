import unittest
from decimal import Decimal
from reporting.business import summarize_areas, summarize_days, business_insights


class BusinessTests(unittest.TestCase):
    def fixture(self):
        return [
            {'pickup_area': 'A', 'trip_count': 100, 'recorded_trip_total_usd': Decimal('500')},
            {'pickup_area': 'A', 'trip_count': 100, 'recorded_trip_total_usd': Decimal('500')},
            {'pickup_area': 'B', 'trip_count': 100, 'recorded_trip_total_usd': Decimal('2000')},
            {'pickup_area': 'C', 'trip_count': 1, 'recorded_trip_total_usd': Decimal('1000')},
            {'pickup_area': 'Unknown', 'trip_count': 50, 'recorded_trip_total_usd': Decimal('5000')},
        ]

    def test_highest_volume_is_not_highest_revenue(self):
        summary = summarize_areas(self.fixture())
        self.assertEqual(summary['ranking'][0]['pickup_area'], 'B')
        self.assertEqual(next(r for r in summary['ranking'] if r['trip_rank'] == 1)['pickup_area'], 'A')
        self.assertIn('different leaders', business_insights(summary)[0])

    def test_small_sample_does_not_win_eligible_yield(self):
        summary = summarize_areas(self.fixture(), min_trips=100)
        self.assertEqual(summary['eligible_yield_ranking'][0]['pickup_area'], 'B')
        self.assertNotIn('C', [r['pickup_area'] for r in summary['eligible_yield_ranking']])

    def test_unknown_amount_is_excluded_from_area_ranks_but_retained_in_totals(self):
        summary = summarize_areas(self.fixture())
        self.assertEqual(summary['known_revenue_usd'], Decimal('4000'))
        self.assertEqual(summary['total_revenue_usd'], Decimal('9000'))
        self.assertEqual(summary['unknown_revenue_usd'], Decimal('5000'))
        self.assertNotIn('Unknown', [r['pickup_area'] for r in summary['ranking']])
        self.assertAlmostEqual(float(summary['unknown_revenue_share_pct']), 5000 / 9000 * 100)

    def test_per_trip_amount_uses_sums_not_mean_of_daily_means(self):
        rows = [
            {'pickup_area': 'A', 'trip_count': 10, 'recorded_trip_total_usd': '100'},
            {'pickup_area': 'A', 'trip_count': 90, 'recorded_trip_total_usd': '180'},
        ]
        result = summarize_areas(rows)
        self.assertEqual(result['ranking'][0]['average_recorded_total_usd'], Decimal('2.8'))

    def test_ties_have_equal_rank(self):
        rows = [
            {'pickup_area': 'A', 'trip_count': 10, 'recorded_trip_total_usd': '100'},
            {'pickup_area': 'B', 'trip_count': 10, 'recorded_trip_total_usd': '100'},
        ]
        result = summarize_areas(rows, 1)
        self.assertEqual([r['revenue_rank'] for r in result['ranking']], [1, 1])
        self.assertIn('Tied leaders', business_insights(result)[0])

    def test_zero_revenue_produces_no_invalid_ratios(self):
        result = summarize_areas([{'pickup_area': 'A', 'trip_count': 1, 'recorded_trip_total_usd': '0'}], 1)
        self.assertIsNone(result['unknown_revenue_share_pct'])
        self.assertIsNone(result['top_n_known_revenue_share_pct'])
        self.assertTrue(business_insights(result))

    def test_no_known_areas_or_threshold_eligible_areas(self):
        result = summarize_areas([{'pickup_area': 'Unknown', 'trip_count': 1, 'recorded_trip_total_usd': '5'}])
        self.assertEqual(result['ranking'], [])
        self.assertIn('unavailable', business_insights(result)[0])
        self.assertTrue(any('No known area meets' in t for t in business_insights(summarize_areas(self.fixture(), 1000))))

    def test_money_preserves_cents(self):
        rows = [
            {'pickup_area': 'A', 'trip_count': 1, 'recorded_trip_total_usd': '0.10'},
            {'pickup_area': 'A', 'trip_count': 1, 'recorded_trip_total_usd': '0.20'},
        ]
        self.assertEqual(summarize_areas(rows)['known_revenue_usd'], Decimal('0.30'))

    def test_days_have_different_volume_and_revenue_leaders(self):
        rows = [
            {'trip_date': '2023-01-01', 'trip_count': 10, 'recorded_trip_total_usd': '100'},
            {'trip_date': '2023-01-02', 'trip_count': 5, 'recorded_trip_total_usd': '200'},
        ]
        result = summarize_days(rows)
        self.assertEqual(result['revenue_leaders'][0]['trip_date'], '2023-01-02')
        self.assertEqual(result['trip_leaders'][0]['trip_date'], '2023-01-01')
        self.assertEqual(result['average_recorded_total_usd'], Decimal('20'))

    def test_bad_gold_values_are_rejected(self):
        for amount in ('-1', 'NaN', 'Infinity'):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                summarize_areas([{'pickup_area': 'A', 'trip_count': 1, 'recorded_trip_total_usd': amount}])
