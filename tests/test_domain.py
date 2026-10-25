import unittest
from quality.rules import check_balance, normalized_header, validate_interval, where_clause


class DomainTests(unittest.TestCase):
    def test_exclusive_end_filter(self):
        query = where_clause('2023-01-01', '2023-01-02')
        self.assertIn(">= '2023-01-01T00:00:00'", query)
        self.assertIn("< '2023-01-02T00:00:00'", query)

    def test_invalid_and_excessive_intervals(self):
        for start, end in [('2023-01-02', '2023-01-01'),
                           ('2023-01-01', '2023-01-01'),
                           ('2023-01-01', '2023-03-01'),
                           ('not-a-date', '2023-01-02')]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                validate_interval(start, end)

    def test_header_normalization(self):
        self.assertEqual(normalized_header('Trip Start Timestamp'), 'trip_start_timestamp')
        self.assertEqual(normalized_header('trip_id'), 'trip_id')

    def test_balanced_counts(self):
        check_balance(100, 5, 10, 85)

    def test_unbalanced_or_negative_counts_fail(self):
        for values in [(100, 5, 10, 86), (100, -5, 10, 95)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                check_balance(*values)
