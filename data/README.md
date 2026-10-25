# Data location
The real bronze, silver, and gold files live in object storage, backed by the
Docker volume chicago-taxi-trust_objectstore-data, rather than this source folder.
Inspect them at http://localhost:9001. Export small CSVs from the report if needed.
A fresh computer has empty Docker volumes and downloads data when Airflow runs.
