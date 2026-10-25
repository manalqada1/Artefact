"""Spark business rules, independent of Airflow and object storage."""
from pyspark.sql import functions as F, Window


def clean_trips(raw):
    # Stable hash chooses one record when duplicate IDs have conflicting values.
    raw = raw.withColumn('trip_id', F.when(F.trim('trip_id') != '', F.trim('trip_id')))
    valid_id = raw.filter(F.col('trip_id').isNotNull())
    window = Window.partitionBy('trip_id').orderBy(F.sha2(F.to_json(F.struct(*sorted(raw.columns))), 256))
    unique = valid_id.withColumn('_n', F.row_number().over(window)).filter('_n = 1').drop('_n')
    deduped = unique.unionByName(raw.filter(F.col('trip_id').isNull()))
    duplicates = raw.count() - deduped.count()
    df = (deduped
          .withColumn('trip_start', F.coalesce(
              F.to_timestamp('trip_start_timestamp', "yyyy-MM-dd'T'HH:mm:ss[.SSSSSS]"),
              F.to_timestamp('trip_start_timestamp', 'MM/dd/yyyy hh:mm:ss a')))
          .withColumn('duration_seconds', F.col('trip_seconds').cast('double'))
          .withColumn('distance_miles', F.col('trip_miles').cast('double'))
          .withColumn('recorded_total', F.col('trip_total').cast('decimal(18,2)'))
          .withColumn('pickup_area', F.when(F.trim('pickup_community_area') != '',
                                          F.trim('pickup_community_area')).otherwise('Unknown'))
          .withColumn('trip_date', F.to_date('trip_start')))
    rules = [
        ('missing_trip_id', F.col('trip_id').isNull()),
        ('invalid_start', F.col('trip_start').isNull()),
        ('invalid_duration', F.col('duration_seconds').isNull() |
         F.isnan('duration_seconds') | (F.abs('duration_seconds') == float('inf')) |
         (F.col('duration_seconds') < 0)),
        ('invalid_distance', F.col('distance_miles').isNull() |
         F.isnan('distance_miles') | (F.abs('distance_miles') == float('inf')) |
         (F.col('distance_miles') < 0)),
        ('invalid_total', F.col('recorded_total').isNull() | (F.col('recorded_total') < 0)),
    ]
    df = df.withColumn('rejection_reasons', F.concat_ws('|', *[
        F.when(condition, F.lit(label)) for label, condition in rules
    ]))
    return df.filter("rejection_reasons = ''"), df.filter("rejection_reasons != ''"), duplicates


def daily_metrics(clean):
    return clean.groupBy('trip_date').agg(
        F.count('*').alias('trip_count'),
        F.sum('recorded_total').alias('recorded_trip_total_usd'),
        F.round(F.avg('duration_seconds') / 60, 6).alias('average_duration_minutes'),
        F.round(F.avg('distance_miles'), 6).alias('average_distance_miles'),
        F.sum(F.when(F.col('pickup_area') == 'Unknown', 1).otherwise(0)).alias('unknown_pickup_count'),
        F.sum(F.when(F.col('duration_seconds') == 0, 1).otherwise(0)).alias('zero_duration_count'),
    )


def area_metrics(clean):
    return clean.groupBy('trip_date', 'pickup_area').agg(
        F.count('*').alias('trip_count'),
        F.sum('recorded_total').alias('recorded_trip_total_usd'),
        F.round(F.avg('duration_seconds') / 60, 6).alias('average_duration_minutes'),
    )
