import logging
from uuid import uuid4
from settings import START, END, STATE, ROOT, BRONZE_MANIFEST, stamp
from storage.object_store import read_json, put_json, uri
from processing.spark_session import spark_session
from quality.rules import check_balance, normalized_header

def build_gold():
    from processing.transforms import daily_metrics, area_metrics
    silver = read_json(f'{STATE}/silver.json')
    spark = spark_session()
    try:
        clean = spark.read.parquet(uri(silver['prefix'] + '/trips'))
        prefix = f'gold/{ROOT}/version={uuid4().hex}'
        daily_metrics(clean).coalesce(1).write.parquet(uri(prefix + '/daily'))
        area_metrics(clean).coalesce(1).write.parquet(uri(prefix + '/areas'))
        put_json(f'{STATE}/gold.json', dict(prefix=prefix, silver=silver, completed_at=stamp()))
    finally:
        spark.stop()
