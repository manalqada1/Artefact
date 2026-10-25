# Command-line entry point used by Airflow.
import argparse, importlib, logging
STAGES = {
    'check_storage': 'storage.object_store',
    'download_bronze': 'ingestion.fetch_chicago_taxi',
    'build_silver': 'processing.silver',
    'build_gold': 'processing.gold',
    'validate_and_publish': 'quality.validate_outputs',
}
def main():
    parser=argparse.ArgumentParser(description='Run one Chicago Taxi pipeline stage.')
    parser.add_argument('stage', choices=STAGES)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    getattr(importlib.import_module(STAGES[args.stage]),args.stage)()
if __name__ == '__main__':
    main()
