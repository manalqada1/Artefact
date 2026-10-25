# Chicago Taxi --- Revenue, Clearly

A local data engineering project that turns Chicago taxi trip records
into traceable, quality-checked business metrics.

Built with **Python, Apache Airflow, PySpark, RustFS (S3-compatible
object storage), Docker Compose, Parquet, and Streamlit**. The project
demonstrates an end-to-end batch pipeline with explicit data-quality
checks, reconciliation, repeatability checks, and controlled
publication.

> **Revenue definition:** Revenue means the sum of `trip_total` reported
> by the source for accepted records. It is not profit, net revenue, or
> an independently verified payment amount.

## Contents

-   [Project overview](#project-overview)
-   [Architecture](#architecture)
-   [Data source and extraction](#data-source-and-extraction)
-   [Data layers](#data-layers)
-   [Cleaning rules](#cleaning-rules)
-   [Gold tables and business
    metrics](#gold-tables-and-business-metrics)
-   [Quality checks and publication](#quality-checks-and-publication)
-   [Technology and repository
    layout](#technology-and-repository-layout)
-   [Run locally](#run-locally)
-   [Run the pipeline](#run-the-pipeline)
-   [Dashboard](#dashboard)
-   [Configuration](#configuration)
-   [Tests and verification status](#tests-and-verification-status)
-   [Stop, restart, and rebuild](#stop-restart-and-rebuild)
-   [Limitations and next steps](#limitations-and-next-steps)

## Project overview

The project extracts a configurable slice of Chicago taxi trips,
preserves the downloaded source pages, cleans and validates the records,
calculates business aggregates, and publishes the results for a
Streamlit dashboard.

The default interval is **January 1, 2023 inclusive through April 1,
2023 exclusive**. The end date is exclusive: records whose trip start
timestamp is on `END_DATE` are not included.

Project goals:

1.  Extract data from the City of Chicago's public Socrata API.
2.  Keep the raw source pages and extraction metadata in a Bronze layer.
3.  Clean, type, deduplicate, and validate records with PySpark in
    Silver.
4.  Produce daily and daily-by-pickup-area aggregates in Gold.
5.  Reconcile row counts and monetary totals across layers.
6.  Publish results only after the configured validation checks pass.
7.  Present business metrics and a visible quality trail in Streamlit.

## Architecture

``` mermaid
flowchart TD
    A[Chicago SODA API] --> B[Bronze: raw CSV pages, metadata, checksums]
    B --> C[Silver: PySpark cleaning and validation]
    C --> D[Gold: daily metrics]
    C --> E[Gold: daily pickup-area metrics]
    D --> F[Reconciliation and publication checks]
    E --> F
    F --> G[Published manifest]
    G --> H[Streamlit dashboard]
    I[Apache Airflow DAG] -. orchestrates stages .-> B
    I -. orchestrates stages .-> C
    I -. orchestrates stages .-> D
    I -. orchestrates stages .-> E
    I -. orchestrates stages .-> F
    B --- J[(RustFS S3-compatible object storage)]
    C --- J
    D --- J
    E --- J
    G --- J
```

Airflow orchestrates the stages in sequence. `src/pipeline.py` is the
command-line entry point used to run one stage at a time. The dashboard
reads the published output rather than recalculating the full pipeline.

Local infrastructure notes:

-   RustFS stores the data lake layers and manifests in S3-compatible
    object storage.
-   A named Docker volume persists object-storage files across container
    restarts.
-   PostgreSQL stores Airflow metadata and execution history.
-   Spark runs in local mode with `local[2]`.
-   The Airflow DAG is configured for one active DAG run and one active
    task at a time.
-   The report reads the relatively small published aggregate tables,
    not the entire raw dataset.

## Data source and extraction

**Dataset:** [Chicago Taxi Trips
2013--2023](https://data.cityofchicago.org/Transportation/Taxi-Trips-2013-2023-/wrvz-psew)

Selected fields include:

-   `trip_id`
-   `trip_start_timestamp`
-   `trip_seconds`
-   `trip_miles`
-   `trip_total`
-   `pickup_community_area`
-   `payment_type`

The downloader filters `trip_start_timestamp` using an inclusive start
and exclusive end, orders records by `trip_start_timestamp` and
`trip_id`, and paginates using `$limit` and `$offset`. `PAGE_SIZE`
defaults to 5,000.

The extraction process checks source metadata, retries transient HTTP
failures, records expected and downloaded row counts, calculates page
checksums, and publishes a complete extraction manifest. Existing
captured Bronze data for the same interval is verified and reused rather
than silently replaced.

The selected interval is downloaded without a silent row cap. Source
metadata is saved alongside the pages. However, offset pagination and
row-count checks cannot guarantee a transactional snapshot if the public
source changes during extraction. The saved Bronze pages are the
reproducible input for downstream processing. Refreshing the source
snapshot is a deliberate future improvement.

## Data layers

### Bronze --- raw source and extraction metadata

Bronze preserves the original CSV pages and the metadata needed to
describe the extraction. The manifest records the selected interval,
page information, counts, checksums, and extraction timestamp.

The goal is traceability: downstream transformations can be related to
the source snapshot that was actually captured.

### Silver --- cleaned trip records

PySpark reads the Bronze pages as strings, normalizes column names, and
applies explicit type conversions and validation rules.

-   Accepted records are written as Parquet partitioned by `trip_date`.
-   Rejected records are retained separately when there are any.
-   Rejection reasons are recorded so that a row can have more than one
    quality flag.
-   Quality counts are recorded in the Silver manifest.

### Gold --- business aggregates

Gold contains two aggregate datasets:

-   **Daily metrics:** one row per trip date, with trip count, sum of
    recorded trip totals, average duration, average distance,
    unknown-pickup count, and zero-duration count.
-   **Daily pickup-area metrics:** one row per trip date and pickup
    area, with trip count, sum of recorded trip totals, and average
    duration.

These tables are optimized for reporting and business comparisons rather
than row-level investigation.

## Cleaning rules

-   Read CSV columns as strings first, then explicitly cast downstream
    values.
-   Represent recorded money as `decimal(18,2)`, duration as seconds,
    and distance as miles.
-   Deduplicate non-empty trip IDs with a stable hash-based selection
    when conflicting records share an ID.
-   Reject records with missing trip IDs, invalid start timestamps, or
    missing, non-finite, or negative duration and distance.
-   Reject records with missing, unparseable, or negative recorded trip
    totals.
-   Preserve rejected records and their reason flags.
-   Keep zero values; zero-duration trips are counted and reported
    rather than automatically rejected.
-   Preserve missing pickup areas as `Unknown`; do not invent geographic
    locations.
-   Partition accepted Silver records by the parsed source trip date.

A rejected record can have multiple rejection flags. Negative trip
totals might represent real adjustments; excluding them is a project
policy, not proof that the source record is erroneous.

Source timestamps are handled as local wall-clock values using Spark's
`TIMESTAMP_NTZ` configuration. Duration comes from the reported
`trip_seconds`, not from subtracting timestamps that may have been
rounded or recorded under different conventions.

## Gold tables and business metrics

### Daily metrics

The daily Gold table contains:

-   Accepted trip count
-   Sum of accepted source-reported trip totals
-   Average trip duration in minutes
-   Average trip distance in miles
-   Number of trips with an unknown pickup area
-   Number of zero-duration trips

### Pickup-area metrics

The daily-area Gold table contains:

-   Accepted trip count
-   Sum of accepted source-reported trip totals
-   Average trip duration in minutes

The reporting layer summarizes these daily-area rows across the selected
interval. It calculates total recorded amount, trip count, average
recorded amount per trip, trip and revenue ranks, share of known-area
revenue, top-three concentration, and unknown-location revenue and its
share of total accepted recorded amount.

Important interpretation rules:

-   Trips with an unknown pickup area remain in headline totals but are
    excluded from geographic rankings.
-   Area averages use total amounts divided by total trip counts, not an
    unweighted average of daily averages.
-   All known areas remain available in the underlying comparison, with
    trip counts shown as context.
-   Exact ties share ranks.
-   Monetary calculations use `Decimal` until values reach the
    presentation layer.
-   Dashboard values may be rounded for display.

The metrics describe the captured source and selected interval under the
documented cleaning rules. They do not estimate costs, profit, or future
performance, and they do not impute missing locations.

## Quality checks and publication

Before a run is published, the pipeline checks the applicable
invariants:

-   `raw = duplicates + rejected + accepted`
-   Spark's Bronze row count matches the extraction manifest.
-   Parsed accepted trip dates fall within the selected interval.
-   Accepted trip IDs are unique.
-   Daily and daily-area Gold trip counts reconcile to the accepted
    Silver count.
-   Daily and daily-area recorded-total sums reconcile to the Silver
    recorded-total sum.
-   Daily keys and date/area keys are unique.
-   A repeat run against the same identified source compares a
    deterministic business fingerprint.

Outputs are written under versioned storage paths. The publication
manifest is updated only after validation succeeds. The report reads the
output referenced by that manifest, so an intermediate failure should
leave the previous publication available.

This is serialized local publication, not a multi-writer transaction
system. Failed attempts may leave versioned objects in storage, and old
versions are retained.

Repeatability is checked using the extraction metadata recorded for the
source and a fingerprint of the published business results. This check
helps detect unexpected differences on a rerun; it does not prove that
the public source itself is immutable.

## Technology and repository layout

### Technology

-   **Python** --- extraction, stage entry point, validation, and
    reporting logic
-   **Chicago Data Portal / Socrata API** --- source data
-   **Apache Airflow** --- orchestration
-   **PySpark** --- cleaning, deduplication, and aggregation
-   **Parquet** --- processed columnar data
-   **RustFS** --- S3-compatible object storage for the local data lake
-   **Pandas and Streamlit** --- dashboard data handling and
    presentation
-   **Docker Compose** --- local services
-   **PostgreSQL** --- Airflow metadata storage

### Key files

``` text
.
├── config/
│   └── local.env.example
├── dags/
│   └── taxi_trust.py
├── src/
│   ├── ingestion/
│   │   └── fetch_chicago_taxi.py
│   ├── processing/
│   │   ├── spark_session.py
│   │   ├── transforms.py
│   │   ├── silver.py
│   │   └── gold.py
│   ├── quality/
│   │   ├── rules.py
│   │   └── validate_outputs.py
│   ├── reporting/
│   │   └── business.py
│   ├── storage/
│   │   └── object_store.py
│   ├── settings.py
│   └── pipeline.py
├── tests/
├── docker-compose.yml
└── README.md
```

This is a map of the key project files; Docker configuration and
dashboard files may add other directories to the actual repository.

## Run locally

### Prerequisites

-   Docker Desktop installed and running on Windows
-   Docker Compose available as `docker compose`
-   The project folder opened in VS Code

Python, Java, Spark, and Airflow do not need to be installed directly on
the Windows host when using the configured containers.

### 1. Create the local environment file

Open **Terminal → New Terminal** in VS Code and run this from the
repository root:

``` powershell
Copy-Item config/local.env.example .env
```

If `.env` already exists, **do not overwrite it** if it contains custom
settings. Review the example configuration and keep credentials local;
do not commit secrets to version control.

### 2. Build and start the services

``` powershell
docker compose up -d --build
```

Check service status:

``` powershell
docker compose ps
```

If a service is unhealthy or fails to start, inspect its logs:

``` powershell
docker compose logs --tail=200
```

### 3. Open the local interfaces

  ------------------------------------------------------------------------------
  Service                 URL                       Local development
                                                    credentials
  ----------------------- ------------------------- ----------------------------
  Airflow                 <http://localhost:8080>   `airflow` / `airflow`

  Streamlit report        <http://localhost:8501>   No login documented

  RustFS console          <http://localhost:9001>   Use the values configured in
                                                    `.env`; the example setup
                                                    uses `taxiadmin` and
                                                    `taxi-local-demo-password`
  ------------------------------------------------------------------------------

These are local-development settings. Do not expose the services
publicly or reuse demo credentials in production.

## Run the pipeline

1.  Open [Airflow](http://localhost:8080).
2.  Find the DAG **`chicago_taxi_trust`**.
3.  Trigger it manually.
4.  Follow the tasks in sequence:
    1.  `check_storage`
    2.  `download_bronze`
    3.  `build_silver`
    4.  `build_gold`
    5.  `validate_and_publish`
5.  Wait for all tasks to succeed, then refresh the Streamlit report at
    <http://localhost:8501>.

The DAG uses manual scheduling (`schedule=None`), disables catch-up, and
limits the environment to one active DAG run and one active task at a
time. Retries are disabled in the DAG configuration, and each task has a
configured execution timeout.

The CLI entry point can run one stage at a time from the project's
configured container environment:

``` bash
python /opt/project/src/pipeline.py check_storage
python /opt/project/src/pipeline.py download_bronze
python /opt/project/src/pipeline.py build_silver
python /opt/project/src/pipeline.py build_gold
python /opt/project/src/pipeline.py validate_and_publish
```

These are container-environment examples; they are not guaranteed to
work directly from a Windows terminal without the project dependencies
and environment variables.

## Dashboard

The Streamlit report reads the published manifest and the corresponding
Gold Parquet outputs. It includes:

-   Headline recorded-revenue and accepted-trip KPIs
-   Revenue and trip comparisons by pickup area
-   Daily revenue and trip-activity views
-   Average recorded amount per trip
-   Data-quality counts and rejection reasons
-   Reconciliation and rerun-verification status
-   Exportable tables for further analysis

If no successful publication is available, the report asks the user to
run the Airflow pipeline first. After a successful run, refresh the
report to load the latest published results.

## Configuration

Use `config/local.env.example` as the source of truth for supported
local variables. Important settings include:

  ---------------------------------------------------------------------------
  Variable                Purpose                 Default or note
  ----------------------- ----------------------- ---------------------------
  `START_DATE`            Inclusive start date    `2023-01-01`
                          (`YYYY-MM-DD`)          

  `END_DATE`              Exclusive end date      `2023-04-01`
                          (`YYYY-MM-DD`)          

  `S3_BUCKET`             Object-storage bucket   `taxi-lake` in the storage
                                                  helper

  `S3_ENDPOINT`           S3-compatible endpoint  Commonly
                                                  `http://objectstore:9000`
                                                  inside the Docker network

  `S3_ACCESS_KEY`         Object-storage access   Set in the local
                          key                     environment

  `S3_SECRET_KEY`         Object-storage secret   Set in the local
                                                  environment
  ---------------------------------------------------------------------------

The interval must contain valid ISO dates and `END_DATE` must be later
than `START_DATE`. The end date is exclusive.

Defaults shown here describe the local code/configuration, not
production recommendations. If a value in the example environment file
differs from a code default, follow the actual Compose environment and
example configuration used by the project.

## Tests and verification status

### Run the unit tests in the configured container

The project's documented container test command is:

``` powershell
docker compose run --rm --no-deps --entrypoint /opt/pipeline-env/bin/python report -m unittest discover -s /opt/project/tests -v
```

This command assumes the Compose service is named `report` and that its
image contains the configured Python environment and tests.

The expected suite described in the project notes contains 20 tests,
including Spark tests. Confirm the actual test output in the environment
where you run it; do not treat the expected count as a result until the
command completes successfully.

Coverage described by the project includes shared validation rules,
duplicate handling, missing IDs, decimal sums, aggregations,
repeatability, date intervals, rankings, weighted ratios, ties, and
unknown pickup areas.

### Current verification status

The earlier project layout was reported as having been verified on the
original laptop: image build, successful one-day and one-week
publications, report display, repeatability, and the original 10 tests
including Spark. One observed week-run reference was 83,557 accepted
trips and `$2,208,616.24`; these are historical observations, not
hard-coded expectations or guarantees for another run.

For the reorganized version, the project notes report syntax checks, CLI
help, and 15 dependency-free tests checked. Five Spark tests require
Docker. The reorganized container build, full Airflow DAG execution, and
report still need verification on the target computer.

**Before submission:** run the test command, build the containers,
trigger the complete DAG, verify publication, and open the dashboard.
Update this section with the actual results and date. Only claim checks
that you have personally rerun or can otherwise verify.

## Stop, restart, and rebuild

Stop running containers without removing stored data:

``` powershell
docker compose stop
```

Start the existing services again:

``` powershell
docker compose up -d
```

After editing application source code, rebuild the images:

``` powershell
docker compose up -d --build
```

These commands preserve named volumes. Avoid `docker compose down -v`
unless you deliberately intend to delete persistent volumes, including
local object-storage data and potentially Airflow metadata.

If you change `.env`, recreate or restart services as required by the
Compose configuration, then wait for them to become healthy before
triggering the DAG.

## Limitations and next steps

This is a local demonstration, not a production deployment.

-   Local services use development credentials and localhost ports.
-   The project notes describe an Airflow 2.11 / Spark 3.5 baseline and
    PostgreSQL 16 image; supported versions and security settings should
    be reviewed before production use.
-   Offset pagination and count checks cannot guarantee a transactional
    source snapshot if the public dataset changes during extraction.
-   Validation checks cover defined structural and reconciliation rules;
    they cannot prove that every source value is factually correct.
-   Failed processing attempts can leave versioned objects in storage
    even when no new publication manifest is written.
-   The full container build, DAG execution, and report behavior of the
    reorganized version must be verified on the target computer.

Possible next steps:

-   Add continuous integration for unit tests and syntax checks.
-   Add automated container-based end-to-end tests from extraction
    through publication.
-   Measure and document runtime and resource usage.
-   Add monitoring for source API changes, extraction failures, and
    data-quality thresholds.
-   Define cleanup or retention for abandoned versioned outputs.
-   Consider a deliberate source-refresh workflow with stronger snapshot
    guarantees.

------------------------------------------------------------------------

## Design principles

-   **Traceability:** preserve raw inputs and extraction manifests.
-   **Reproducibility:** use deterministic duplicate selection and
    compare business fingerprints.
-   **Explicit quality:** account for accepted, rejected, and duplicate
    records.
-   **Reconciliation:** compare counts and recorded totals across data
    layers.
-   **Separation of concerns:** isolate ingestion, transformations,
    orchestration, storage, validation, and presentation.
-   **Honest reporting:** distinguish implemented checks from behavior
    that still needs end-to-end verification.
