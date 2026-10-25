# Chicago Taxi — Revenue, clearly.

A local data-engineering project built with Airflow, PySpark, S3-compatible object
storage, Docker Compose, and Streamlit. Open this folder in VS Code.

**Beginner guide:** [START_FROM_ZERO.md](START_FROM_ZERO.md).
**Source walkthrough:** [PROJECT_MAP.md](PROJECT_MAP.md).

## Quick start

With Docker Desktop running, open Terminal > New Terminal in VS Code:

~~~powershell
Copy-Item config/local.env.example .env
docker compose up -d --build
~~~

Do not overwrite an existing .env with custom settings.
Example interval: January 1-7, 2023. END_DATE is exclusive.
No host installation of Python, Java, Spark, or Airflow is required.

- Airflow: http://localhost:8080 — airflow / airflow
- Report: http://localhost:8501
- Object storage: http://localhost:9001 — taxiadmin / taxi-local-demo-password

Trigger chicago_taxi_trust once. Refresh the report after all tasks succeed.

## Architecture

~~~text
Chicago SODA API
    -> bronze: original CSV + source metadata + checksummed manifest
    -> PySpark
    -> silver: typed clean trips + rejected records
    -> PySpark
    -> gold: daily and daily-area metrics
    -> reconciliation + single publication manifest
    -> revenue and data-quality dashboard
~~~

RustFS stores all lake layers; a named Docker volume persists its files.
PostgreSQL stores Airflow history. Spark uses local[2]. LocalExecutor allows
one task and one DAG run at a time. The report reads small published tables.
The data folder explains storage; it does not contain the real lake.

## Source and download

Dataset: [Chicago Taxi Trips 2013-2023](https://data.cityofchicago.org/Transportation/Taxi-Trips-2013-2023-/wrvz-psew).

Selected fields: trip_id, trip_start_timestamp, trip_seconds, trip_miles,
trip_total, pickup_community_area, payment_type.

The downloader filters trip_start_timestamp >= start and < end, orders by
trip_start_timestamp and trip_id, and paginates with $limit/$offset.
PAGE_SIZE defaults to 5,000. It checks metadata, retries transient HTTP failures,
records expected/downloaded counts and checksums, and publishes only a complete
manifest. Existing captured bronze for the same dates is verified and reused.

The complete selected slice is downloaded, without a silent row cap. Source
metadata is saved alongside it. Offset/count checks cannot guarantee a
transactional snapshot if the public source changes during extraction.
Saved bronze pages are the reproducible input. Source refresh is future work.

## Cleaning rules

- Read CSV as strings; explicitly cast downstream values.
- Money uses decimal(18,2), duration seconds, distance miles.
- Deduplicate nonempty IDs with a stable hash-based choice.
- Reject missing IDs individually, invalid start times, missing/nonfinite/negative
  duration or distance, and missing/unparseable/negative recorded amounts.
- Preserve rejected records and their reason flags.
- Keep zeros; display zero-duration counts.
- Preserve unknown pickup areas; never invent locations.
- Partition accepted silver records by source trip_date.

A rejected record may carry multiple flags. Negative amounts could include real
adjustments: excluding them is a documented policy, not proof of a source error.
Source timestamps use local wall-clock TIMESTAMP_NTZ. Duration comes from
reported seconds, not subtraction of possibly rounded timestamps.

## Tables and metric definitions

Gold daily: one row per date, with count, recorded amount sum, average duration,
average distance, unknown-pickup count, and zero-duration count.
Gold areas: one row per date and pickup area, with count, recorded amount sum,
and average duration.

The report shows full-interval area revenue, trip count, revenue/trip ranks,
average amount per trip, share of known-area revenue, top-three concentration,
unknown-location revenue and its share of the total, and daily comparisons.

Unknown-location trips remain in headline totals and are excluded from area
rankings. Area averages use sums / counts rather than an average of daily means.
All known areas remain visible with sample counts. Exact ties share ranks.
Currency uses Decimal arithmetic until presentation; display values are rounded.

Revenue means the source trip_total for accepted records. No costs, profit
estimates, forecasts, or imputed locations are included. Findings describe the
captured source and interval, subject to the stated cleaning rules and limitations.

## Safe publication and repeatability

Versioned paths hold outputs. Before updating published/latest.json, checks verify:
- raw = duplicates + rejected + accepted;
- accepted IDs and gold keys are unique;
- daily/area counts and exact decimal sums reconcile to silver.

The report reads immutable output referenced by that manifest; an intermediate
failure leaves the previous publication available. This is serialized local
publication, not multi-writer transactions. Old versions are retained.

Repeating the same source compares a deterministic business fingerprint.
The reorganization keeps the DAG ID, storage paths, output definitions, and
Compose project/volume names unchanged.

## Tests and verification

~~~powershell
docker compose run --rm --no-deps --entrypoint /opt/pipeline-env/bin/python report -m unittest discover -s /opt/project/tests -v
~~~

Expected inside Docker: 20 tests, OK, no skipped Spark tests.
Coverage includes rules, duplicates, missing IDs, decimal sums, aggregates,
repeatability, intervals, rankings, weighted ratios, ties, and unknown areas.

The earlier layout was verified on the original laptop: image build, successful
one-day/week publications, report display, repeatability, and the original 10
tests including Spark. A week publication displayed 83,557 accepted trips and
$2,208,616.24; these are observed reference values, not hard-coded expectations.

The reorganized version is checked locally with syntax checks, CLI help, and
15 dependency-free tests. Five Spark tests need Docker. Its container build,
DAG execution, and report must still be verified on the target computer.

## Stop, restart, and changes

~~~powershell
docker compose stop
docker compose up -d
~~~

These preserve volumes. After editing source, use docker compose up -d --build.
After changing .env, use docker compose up -d and wait for startup before running.
START_FROM_ZERO.md explains migration from the existing project without deleting
its storage. Run only one old/new project copy at a time.

## Tradeoffs and next work

This is a local demonstration with demo credentials and localhost-only ports.
It uses the previously working Airflow 2.11 / Spark 3.5 baseline. PostgreSQL follows
the maintained 16-bookworm tag. Production requires supported-version and
security review, credentials management, and deployment controls.

Future improvements: daily backfills, deliberate source refresh, stronger source
snapshot guarantees, configurable quality policies, output cleanup, failure
integration tests, and CI. A distributed Spark cluster is unnecessary for this
selected slice.

