"""Object storage helpers. A single JSON object publishes each successful run."""
import io
import logging
import time
import json
import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

BUCKET = os.environ.get('S3_BUCKET', 'taxi-lake')


def client():
    return boto3.client(
        's3', endpoint_url=os.environ.get('S3_ENDPOINT', 'http://objectstore:9000'),
        aws_access_key_id=os.environ.get('S3_ACCESS_KEY', 'taxiadmin'),
        aws_secret_access_key=os.environ.get('S3_SECRET_KEY', 'taxi-local-demo-password'),
        region_name='us-east-1', config=Config(s3={'addressing_style': 'path'}),
    )


def read_bytes(key):
    return client().get_object(Bucket=BUCKET, Key=key)['Body'].read()


def put_bytes(key, body, content_type='application/octet-stream'):
    client().put_object(Bucket=BUCKET, Key=key, Body=body, ContentType=content_type)


def read_json(key):
    return json.loads(read_bytes(key))


def optional_json(key):
    try:
        return read_json(key)
    except ClientError as exc:
        if exc.response['Error']['Code'] in ('NoSuchKey', '404', 'NoSuchBucket'):
            return None
        raise


def put_json(key, value):
    put_bytes(key, json.dumps(value, indent=2, default=str).encode(), 'application/json')


def parquet_frame(prefix):
    import pandas as pd
    frames = []
    pages = client().get_paginator('list_objects_v2').paginate(Bucket=BUCKET, Prefix=prefix)
    for page in pages:
        for obj in page.get('Contents', []):
            if obj['Key'].endswith('.parquet'):
                frames.append(pd.read_parquet(io.BytesIO(read_bytes(obj['Key']))))
    if not frames:
        raise ValueError(f'No Parquet data found at {prefix}')
    return pd.concat(frames, ignore_index=True)


def check_storage():
    from botocore.exceptions import ClientError
    for attempt in range(30):
        try:
            s3 = client()
            buckets = [b['Name'] for b in s3.list_buckets()['Buckets']]
            if BUCKET not in buckets:
                s3.create_bucket(Bucket=BUCKET)
            logging.info('Object storage ready: %s', BUCKET)
            return
        except (ClientError, ConnectionError) as exc:
            if attempt == 29:
                raise
            logging.warning('Waiting for object storage: %s', exc)
            time.sleep(2)
        except Exception as exc:
            from botocore.exceptions import EndpointConnectionError
            if not isinstance(exc, EndpointConnectionError) or attempt == 29:
                raise
            time.sleep(2)

def uri(key):
    return f's3a://{BUCKET}/{key}'
