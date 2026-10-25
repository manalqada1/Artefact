import hashlib, json, logging
from settings import STATE, stamp
from storage.object_store import read_json, put_json, optional_json, uri
from quality.rules import check_balance
from processing.spark_session import spark_session

def validate_and_publish():
    from decimal import Decimal
    from pyspark.sql import functions as F
    gold = read_json(f'{STATE}/gold.json')
    silver = gold['silver']
    quality = silver['metrics']
    check_balance(quality['raw'], quality['duplicates'], quality['rejected'], quality['accepted'])
    spark = spark_session()
    try:
        clean = spark.read.parquet(uri(silver['prefix'] + '/trips'))
        daily = spark.read.parquet(uri(gold['prefix'] + '/daily'))
        areas = spark.read.parquet(uri(gold['prefix'] + '/areas'))
        def totals(frame, count_column, amount_column):
            row = frame.agg(F.sum(count_column).alias('n'), F.sum(amount_column).alias('total')).first()
            return int(row['n']), Decimal(row['total'])
        silver_total = clean.agg(F.sum('recorded_total').alias('total')).first()['total']
        expected = quality['accepted'], Decimal(silver_total)
        assert totals(daily, 'trip_count', 'recorded_trip_total_usd') == expected, 'Daily metrics do not reconcile.'
        assert totals(areas, 'trip_count', 'recorded_trip_total_usd') == expected, 'Area metrics do not reconcile.'
        assert clean.select('trip_id').distinct().count() == quality['accepted'], 'Duplicate silver IDs.'
        assert daily.count() == daily.select('trip_date').distinct().count(), 'Duplicate daily keys.'
        assert areas.count() == areas.select('trip_date', 'pickup_area').distinct().count(), 'Duplicate area keys.'
        # Fingerprint only business output; physical Spark filenames may differ on rerun.
        payload = {
            'daily': [r.asDict() for r in daily.orderBy('trip_date').collect()],
            'areas': [r.asDict() for r in areas.orderBy('trip_date', 'pickup_area').collect()],
            'quality': quality,
        }
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        previous = optional_json(f'{STATE}/published.json')
        same_source = previous and previous['silver']['source']['extracted_at'] == silver['source']['extracted_at']
        if same_source and previous['business_fingerprint'] != fingerprint:
            raise ValueError('Identical source produced different results. Publication blocked.')
        gold.update(published_at=stamp(), business_fingerprint=fingerprint,
                    rerun_verified=bool(same_source), validation='passed')
        put_json(f'{STATE}/published.json', gold)
        # Readers see only complete immutable output referenced by this object.
        put_json('published/latest.json', gold)
        logging.info('PUBLISHED: %s; rerun verified: %s', fingerprint, bool(same_source))
    finally:
        spark.stop()
