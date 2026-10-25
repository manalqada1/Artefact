import os
from datetime import datetime, timezone
from quality.rules import validate_interval

START = os.environ.get('START_DATE', '2023-01-01')
END = os.environ.get('END_DATE', '2023-04-01')
INTERVAL = validate_interval(START, END)
ROOT = f'interval={INTERVAL}'
STATE = f'_state/{ROOT}'
SOURCE = 'https://data.cityofchicago.org/resource/wrvz-psew'
BRONZE_MANIFEST = f'{STATE}/bronze.json'


def stamp():
    return datetime.now(timezone.utc).isoformat()
