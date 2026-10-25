import logging
from uuid import uuid4
from settings import START, END, STATE, ROOT, BRONZE_MANIFEST, stamp
from storage.object_store import read_json, put_json, uri
from processing.spark_session import spark_session
from quality.rules import check_balance, normalized_header

def build_silver():
    from pyspark.sql import functions as F
    from processing.transforms import clean_trips
    source = read_json(BRONZE_MANIFEST)
    spark = spark_session()
    try:
        raw = spark.read.option('header', True).option('inferSchema', False).option('mode', 'FAILFAST').csv(
            [uri(p['key']) for p in source['pages']])
        for column in raw.columns:
            raw = raw.withColumnRenamed(column, normalized_header(column))
        raw = raw.cache()
        if raw.count() != source['row_count']:
            raise ValueError('Spark raw count does not match extraction manifest.')
        clean, rejected, duplicates = clean_trips(raw)
        clean, rejected = clean.cache(), rejected.cache()
        accepted_count, rejected_count = clean.count(), rejected.count()
        check_balance(source['row_count'], duplicates, rejected_count, accepted_count)
        if accepted_count == 0:
            raise ValueError('No valid records remain.')
        invalid_dates = clean.filter((F.col('trip_date') < START) | (F.col('trip_date') >= END)).count()
        if invalid_dates:
            raise ValueError('Parsed dates lie outside the selected interval.')
        version = uuid4().hex
        prefix = f'silver/{ROOT}/version={version}'
        clean.withColumn('source_extracted_at', F.lit(source['extracted_at'])).write.partitionBy('trip_date').parquet(uri(prefix + '/trips'))
        if rejected_count:
            rejected.write.parquet(uri(prefix + '/rejected'))
        reasons = {r['reason']: r['count'] for r in rejected.select(
            F.explode(F.split('rejection_reasons', r'\|')).alias('reason')).groupBy('reason').count().collect()}
        metrics = dict(raw=source['row_count'], duplicates=duplicates, rejected=rejected_count,
                       accepted=accepted_count, rejection_reasons=reasons,
                       unknown_pickup=clean.filter("pickup_area = 'Unknown'").count(),
                       zero_duration=clean.filter('duration_seconds = 0').count())
        put_json(f'{STATE}/silver.json', dict(prefix=prefix, metrics=metrics,
                 start=START, end_exclusive=END, source=source, completed_at=stamp()))
        logging.info('Silver quality: %s', metrics)
    finally:
        spark.stop()
