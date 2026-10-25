# Download an immutable bronze snapshot of the selected Chicago taxi interval.
import csv, hashlib, io, logging, os
from uuid import uuid4
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from quality.rules import FIELDS, normalized_header, where_clause
from settings import START, END, ROOT, SOURCE, BRONZE_MANIFEST, stamp
from storage.object_store import optional_json, read_bytes, put_bytes, put_json

def session():
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=['GET'], respect_retry_after_header=True)
    s.mount('https://', HTTPAdapter(max_retries=retry))
    if os.environ.get('SOCRATA_APP_TOKEN'):
        s.headers['X-App-Token'] = os.environ['SOCRATA_APP_TOKEN']
    return s

def download_bronze():
    existing = optional_json(BRONZE_MANIFEST)
    if existing:
        for page in existing['pages']:
            if hashlib.sha256(read_bytes(page['key'])).hexdigest() != page['sha256']:
                raise ValueError('Stored bronze checksum mismatch.')
        logging.info('Reusing verified immutable extraction: %s rows', existing['row_count'])
        return
    size = int(os.environ.get('PAGE_SIZE', '5000'))
    if not 1 <= size <= 50000:
        raise ValueError('PAGE_SIZE must be between 1 and 50000.')
    query = where_clause(START, END)
    s = session()
    # Capture the source metadata alongside the extraction for the data dictionary.
    meta = s.get('https://data.cityofchicago.org/api/views/wrvz-psew.json', timeout=(15, 120))
    meta.raise_for_status()
    metadata = meta.json()
    available = {col['fieldName'] for col in metadata['columns']}
    if not set(FIELDS).issubset(available):
        raise ValueError(f'Source schema changed; missing {set(FIELDS) - available}')
    response = s.get(SOURCE + '.json', params={'$select': 'count(*) as n', '$where': query}, timeout=(15, 120))
    response.raise_for_status()
    expected = int(response.json()[0]['n'])
    if expected == 0:
        raise ValueError('No trips found. Check the selected dates.')
    prefix = f'bronze/{ROOT}/extraction={uuid4().hex}'
    put_json(f'{prefix}/source_metadata.json', metadata)
    pages, offset = [], 0
    while offset < expected:
        response = s.get(SOURCE + '.csv', params={
            '$select': ','.join(FIELDS), '$where': query,
            '$order': 'trip_start_timestamp,trip_id', '$limit': size, '$offset': offset,
        }, timeout=(15, 120))
        response.raise_for_status()
        body = response.content
        reader = csv.DictReader(io.StringIO(body.decode('utf-8-sig')))
        if set(normalized_header(c) for c in reader.fieldnames or []) != set(FIELDS):
            raise ValueError(f'Unexpected CSV header: {reader.fieldnames}')
        rows = sum(1 for _ in reader)
        if rows == 0:
            raise ValueError('Source ended before the expected count; extraction was not published.')
        key = f'{prefix}/page_{len(pages):05d}.csv'
        put_bytes(key, body, 'text/csv')
        pages.append({'key': key, 'rows': rows, 'sha256': hashlib.sha256(body).hexdigest()})
        offset += rows
        logging.info('Downloaded %s / %s rows', offset, expected)
    if offset != expected:
        raise ValueError('Source count changed during extraction. Retry the download.')
    manifest = dict(source=SOURCE, start=START, end_exclusive=END, extracted_at=stamp(),
                    row_count=offset, pages=pages, metadata_key=f'{prefix}/source_metadata.json')
    put_json(f'{prefix}/manifest.json', manifest)
    put_json(BRONZE_MANIFEST, manifest)
