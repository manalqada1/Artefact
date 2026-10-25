import importlib.util
import unittest
from decimal import Decimal

HAS_SPARK = importlib.util.find_spec('pyspark') is not None


@unittest.skipUnless(HAS_SPARK, 'Run these tests inside the supplied Docker image.')
class SparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pyspark.sql import SparkSession
        cls.spark = (SparkSession.builder.master('local[1]').appName('taxi-tests')
                     .config('spark.sql.shuffle.partitions', '1')
                     .config('spark.sql.ansi.enabled', 'false')
                     .config('spark.sql.timestampType', 'TIMESTAMP_NTZ')
                     .getOrCreate())
        cls.spark.sparkContext.setLogLevel('ERROR')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def fixture(self, extra=None):
        from quality.rules import FIELDS
        rows = [
            ('a', '2023-01-01T10:00:00.000', '120', '1', '10.10', '8', 'Cash'),
            ('a', '2023-01-01T10:00:00.000', '120', '1', '10.10', '8', 'Cash'),
            ('b', '2023-01-01T11:00:00.000', '480', '2', '20.20', None, 'Credit Card'),
            ('c', '2023-01-01T12:00:00.000', '-1', '2', '5', '8', 'Cash'),
        ]
        if extra:
            rows += extra
        return self.spark.createDataFrame(rows, schema=list(FIELDS))

    def test_duplicates_and_rejected_records_reconcile(self):
        from processing.transforms import clean_trips
        clean, rejected, duplicates = clean_trips(self.fixture())
        self.assertEqual((clean.count(), rejected.count(), duplicates), (2, 1, 1))
        self.assertIn('invalid_duration', rejected.first()['rejection_reasons'])

    def test_known_aggregate_uses_decimal_money_and_reported_duration(self):
        from processing.transforms import clean_trips, daily_metrics
        clean, _, _ = clean_trips(self.fixture())
        row = daily_metrics(clean).first()
        self.assertEqual(row['trip_count'], 2)
        self.assertEqual(row['recorded_trip_total_usd'], Decimal('30.30'))
        self.assertAlmostEqual(row['average_duration_minutes'], 5.0)
        self.assertEqual(row['unknown_pickup_count'], 1)

    def test_missing_identifiers_are_rejected_individually(self):
        from processing.transforms import clean_trips
        extras = [
            (None, '2023-01-01T12:00:00.000', '10', '1', '1', '8', 'Cash'),
            (None, '2023-01-01T12:00:00.000', '20', '1', '1', '8', 'Cash'),
        ]
        _, rejected, duplicates = clean_trips(self.fixture(extras))
        self.assertEqual(rejected.count(), 3)
        self.assertEqual(duplicates, 1)

    def test_zero_duration_is_retained_and_visible(self):
        from processing.transforms import clean_trips, daily_metrics
        extra = [('d', '2023-01-01T12:00:00.000', '0', '0', '0', '8', 'Cash')]
        clean, _, _ = clean_trips(self.fixture(extra))
        self.assertEqual(daily_metrics(clean).first()['zero_duration_count'], 1)

    def test_repeated_transformation_has_identical_business_output(self):
        from processing.transforms import clean_trips, daily_metrics, area_metrics
        def result():
            clean, _, _ = clean_trips(self.fixture())
            return (
                daily_metrics(clean).orderBy('trip_date').collect(),
                area_metrics(clean).orderBy('trip_date', 'pickup_area').collect(),
            )
        self.assertEqual(result(), result())
