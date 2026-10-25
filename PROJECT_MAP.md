# Project map

| Location | Responsibility |
|---|---|
| config/local.env.example | Date range and API page size example |
| dags/taxi_trust.py | Airflow task order |
| src/ingestion/fetch_chicago_taxi.py | API pagination, retries, bronze snapshots |
| src/processing/spark_session.py | Spark and S3 connector configuration |
| src/processing/transforms.py | Cleaning and aggregate definitions |
| src/processing/silver.py | Write clean and rejected trips |
| src/processing/gold.py | Write daily and pickup-area metrics |
| src/quality/rules.py | Date, header, and row-count rules |
| src/quality/validate_outputs.py | Reconciliation, fingerprints, publication |
| src/storage/object_store.py | Object-storage and manifest operations |
| src/reporting/business.py | Revenue comparisons from published sums/counts |
| src/reporting/report.py | Dashboard presentation and definitions |
| src/settings.py | Interval settings and storage paths |
| src/pipeline.py | Command entry point for Airflow |
| tests/ | Deterministic checks and synthetic Spark fixtures |
| data/README.md | Explains the Docker object-storage volume |
| compose.yaml | Services, credentials, and persistent volumes |
| Dockerfile | Builds the runtime |
| .vscode/tasks.json | Optional launch, test, and status shortcuts |

Docker provides the runtime. A local .venv folder is not required.
Changing source requires rebuilding the image because code is copied into it.

