# Start from zero — Chicago Taxi in VS Code

This guide is for a beginner using Windows and the ARTEFACT_TEST project package.
It explains running the supplied code. You do not have to write the application
from scratch or install its Python packages individually.

If Docker already works on your current laptop, use the migration section at the
end first. Do not install everything again.

## 1. What you are going to run

- VS Code: the editor where you browse and change project files.
- Docker Desktop: runs the software in Linux containers.
- Airflow: runs the five pipeline steps in order and shows their logs.
- PySpark: cleans taxi trips and creates analytical tables.
- RustFS: stores the bronze, silver, and gold files through an S3-compatible API.
- PostgreSQL: preserves Airflow history.
- Streamlit: displays the revenue and data-quality report.

Only VS Code and Docker Desktop must be installed for this ZIP-based workflow.
Python, Java, Spark, Airflow, PostgreSQL, and Streamlit are installed inside the
Docker image. A local .venv is not required. Git is optional for running the ZIP;
it is useful when preparing the final repository.

## 2. Check the computer

Use a Windows version supported by Docker Desktop. Windows 11 with current
updates is a reasonable starting point. Check Docker's current requirements:
https://docs.docker.com/desktop/setup/install/windows-install/

For this combined application, 14-16 GB total RAM is a practical target: the
earlier version ran on a laptop reporting 14 GB. Close memory-heavy applications.
Allow roughly 20 GB free disk space for images, build caches, and data; this is
a planning allowance, not a measured minimum. Use a stable internet connection.

Ports 8080, 8501, 9000, and 9001 must be free on your computer.

## 3. Install VS Code

1. Open https://code.visualstudio.com/download.
2. Download the Windows installer matching your computer.
3. Run the installer and complete the normal setup.
4. Open VS Code.

Official Windows installation guide:
https://code.visualstudio.com/docs/setup/windows

Extensions are optional for running the project. Python editing extensions may
show missing-package warnings because runtime packages live inside Docker.
Do not install Airflow on Windows to resolve those editor warnings.

## 4. Install and start Docker Desktop

1. Download Docker Desktop from:
   https://docs.docker.com/desktop/setup/install/windows-install/
2. Select x86_64 for most Intel/AMD PCs, or Arm for an ARM-based PC.
3. Install using the WSL 2 backend.
4. Restart Windows if requested.
5. Open Docker Desktop and complete the welcome screens.
6. Wait until its engine is running.
7. Use Linux containers.

If Docker asks you to install WSL:
- Open Windows Start, search PowerShell, right-click, Run as administrator.
- Run:

    wsl --install

- Restart Windows when requested.
- If Ubuntu opens and asks for a username/password, complete it if desired; our
  project commands still run in Windows PowerShell, not the Ubuntu terminal.

If Docker says WSL needs updating, run in Windows PowerShell:

    wsl --update

Then reopen Docker Desktop. WSL installation instructions:
https://learn.microsoft.com/en-us/windows/wsl/install

Do not install a separate Docker Engine inside Ubuntu for this workflow.

## 5. Verify Docker before touching the project

Open Windows PowerShell, then run each command separately:

    docker --version

    docker compose version

    docker run --rm hello-world

Expected checkpoint: the last command prints Hello from Docker!

If the command exists but cannot connect to the engine, start Docker Desktop and
wait. If Windows cannot find docker, reopen PowerShell after installation.

Do not continue until hello-world succeeds.

## 6. Extract and open the project

1. Download ARTEFACT_TEST-vscode.zip.
2. In File Explorer, right-click it and choose Extract All.
3. Put the extracted ARTEFACT_TEST folder somewhere such as Documents.
4. In VS Code, choose File > Open Folder.
5. Select the ARTEFACT_TEST folder containing compose.yaml.
6. If asked about trusting the folder, review the source and choose the normal
   workspace trust option when you are comfortable with the supplied files.
7. Open the left Explorer panel.

You should see:

    ARTEFACT_TEST/
      .vscode/
      config/
      dags/
      data/
      src/
        ingestion/
          fetch_chicago_taxi.py
        processing/
          spark_session.py
          transforms.py
          silver.py
          gold.py
        quality/
          rules.py
          validate_outputs.py
        reporting/
          business.py
          report.py
        storage/
          object_store.py
        settings.py
        pipeline.py
      tests/
      compose.yaml
      Dockerfile
      requirements.txt
      README.md
      START_FROM_ZERO.md

Some folders also contain __init__.py so Python can import their code.

## 7. Open the VS Code terminal and choose dates

In VS Code, select Terminal > New Terminal. Use a PowerShell terminal.
The prompt should end in ARTEFACT_TEST. To verify you are in the right folder:

    Get-ChildItem compose.yaml

You should see the file. If not, open the correct folder in VS Code.

On a NEW extraction, copy the example configuration:

    Copy-Item config/local.env.example .env

Do not overwrite an existing .env if you want to preserve custom dates or tokens.

Open .env in the editor. The example selects one week:

    START_DATE=2023-01-01
    END_DATE=2023-01-08
    PAGE_SIZE=5000
    SOCRATA_APP_TOKEN=

The end is excluded: January 1 through January 7 will be downloaded.
For a quicker first attempt, set END_DATE=2023-01-02 to process January 1 only.
Leave the optional token empty initially. Save the file.

The folder data is documentation for where data lives; the actual lake files
will be created in the Docker object-storage volume, not in Git or this folder.

## 8. Build and start

Keep Docker Desktop open. In the project terminal:

    docker compose up -d --build

The first build downloads large images, Python dependencies, and Java libraries.
It can take 10-30 minutes or longer depending on your internet connection.
Wait for the command to finish and the terminal prompt to return.

Then run:

    docker compose ps -a

Expected:
- postgres running and healthy;
- objectstore running;
- airflow-init exited with code 0;
- airflow-webserver running (healthy after startup);
- airflow-scheduler running (healthy after startup);
- report running.

airflow-init exiting successfully is normal. It creates the database tables and
initial login. The other services should stay running.

After a restart, allow about 60 seconds for Airflow to become ready. A container
showing Started does not mean its web page is immediately ready.

## 9. Open the applications

Airflow:
http://localhost:8080
Username: airflow
Password: airflow

Revenue report:
http://localhost:8501
No report login is configured.

Object-storage console:
http://localhost:9001
Access key / username: taxiadmin
Secret key / password: taxi-local-demo-password

These are local demonstration credentials. Keep this configuration on localhost.
Do not click Streamlit's Deploy button; it is unrelated to this local workflow.

The first report will say there are no published results. This is expected.

## 10. Run the first pipeline

1. In Airflow, find chicago_taxi_trust.
2. Ensure its toggle is enabled.
3. Click the play button once.
4. Confirm Trigger DAG if a dialog appears.
5. Click chicago_taxi_trust and open the Graph tab or inspect its task status.

The steps are:

    check_storage
        -> download_bronze
        -> build_silver
        -> build_gold
        -> validate_and_publish

Wait for all five to succeed. Avoid repeatedly clicking play.

A DAG is the workflow definition. A task is one step in that workflow.

If a task turns red, open that task's Logs. Fix the reported issue first; do not
mark it successful manually.

## 11. Read and verify the report

Open http://localhost:8501 and click Refresh results.

First verify the source interval shown in the header. A report shows the LAST
successful publication, which may differ from .env if a new run failed.

Then inspect:
- total accepted recorded trip revenue;
- accepted trip count;
- average recorded amount per trip;
- percentage of revenue with a known pickup area;
- revenue leader versus trip-volume leader;
- area rankings, counts, revenue shares, and averages;
- daily comparisons;
- rejection reasons and the row-count balance.

Definitions:
- Revenue is the source trip_total summed over accepted trips.
- It is not a cost or profit calculation.
- Area means pickup community-area code, not destination.
- Unknown-location trips remain in totals but are excluded from area rankings.
- Revenue shares in the area table use KNOWN-area revenue.
- An area's average amount is its total amount divided by its trip count.
- A high average based on a small number of trips remains a small sample.
- The report contains descriptive observations, not forecasts.

The previous layout on the original computer showed 83,557 accepted trips and
$2,208,616.24 for January 1-7, 2023. This is a recorded reference observation, not
a hard-coded expected result or a guarantee if the public source changes.

## 12. Run the automated tests

In the VS Code terminal:

    docker compose run --rm --no-deps --entrypoint /opt/pipeline-env/bin/python report -m unittest discover -s /opt/project/tests -v

There are 20 tests. Expected on a working Docker setup: Ran 20 tests and OK,
without skipped Spark tests.

They use synthetic fixtures for dates, quality rules, duplicates, decimal money,
aggregation, repeatability, revenue ranking, unknown areas, ties, and weighted
averages. They do not alter the published lake data.

The original 10 tests previously passed in Docker on the original computer.
The 15 dependency-free tests passed after this reorganization in the author's
environment. The 5 Spark tests and full refactored container run still need to
be executed on the target computer.

ResourceWarning messages may appear from PySpark's internal connections. Read
the final test status: OK versus FAILED/ERROR. A warning is not itself a passed
test or a failed test.

## 13. Verify a repeat run

1. Keep the same dates.
2. Trigger the same DAG again once.
3. Wait for every task to succeed.
4. Refresh the report.
5. Look in Data quality & definitions for Rerun verified.

The extractor reuses the captured bronze files only after checking checksums.
The final step compares a business fingerprint. Results should not double.

This verifies repeatability against the captured source. It does not prove the
original public dataset is complete or free of real-world errors.

## 14. Change dates or code later

For dates:
1. Edit .env and save it.
2. Run docker compose up -d.
3. Wait for Airflow startup.
4. Trigger a new run.
5. Verify the report header after successful publication.

For code:
1. Edit the appropriate file under src or dags.
2. Save it.
3. Run docker compose up -d --build.
4. Wait for startup and test the relevant behavior.

Source is copied into the image, so simply saving a file does not update the
running containers. Do not use VS Code's Run Python File button to start Airflow.

Useful VS Code shortcuts: Terminal > Run Task offers supplied tasks for starting
services, tests, service status, and stopping. The terminal commands above do the
same work.

## 15. Stop and return tomorrow

Stop while retaining data:

    docker compose stop

Later, open Docker Desktop, open the SAME project folder in VS Code, then:

    docker compose up -d

The Docker volumes preserve Airflow history, logs, and object-storage data.
Keep the project name in compose.yaml unchanged if you want to reuse those volumes.
Do not delete Docker volumes as a routine troubleshooting step.

## 16. Troubleshooting

Airflow blank page / ERR_EMPTY_RESPONSE:
- Wait 60 seconds after startup.
- Run:

    docker compose ps -a

    docker compose logs --tail=80 airflow-webserver airflow-scheduler

Report error:

    docker compose logs --tail=80 report

Initialization error:

    docker compose logs --tail=80 airflow-init postgres

Storage error:

    docker compose logs --tail=80 objectstore

Airflow task failure:
- Click the failed task and open Logs.
- Read the last actual exception.
- After a fix, clear the failed and downstream tasks, or trigger a new run.
- Check existing runs before clicking play again.

Port already allocated:
- Another application or another copy of this project may use the same port.
- Stop the other project from its own folder. Do not launch two copies at once.

Image pull denied / package download error:
- Confirm the exact image name or failing URL in the log.
- Check internet access and Docker Hub access; do not change random versions.
- The package uses RustFS 1.0.3 because the original MinIO image was unavailable.

Memory-related exit:
- Close heavy applications and inspect Docker Desktop's resource availability.
- Start with one source day and one active DAG run.
- Do not assume an unavailable browser page proves the pipeline failed.

When asking for help, share the relevant service log and docker compose ps -a.
Do not share a populated .env containing private tokens.

## 17. Move the working project to another computer

For the SAME code and a fresh download:
1. Share this ZIP or a Git repository containing the project.
2. Follow steps 2-13 on the new computer.
3. Recreate .env with the same dates.
4. Run the tests and pipeline.
5. Compare definitions, interval, and actual outputs.

The ZIP contains code, NOT your laptop's Docker volumes. A new computer downloads
the selected public source again. If it changed, matching dates alone do not
guarantee byte-identical input.

For a strictly identical captured dataset, the bronze objects and their manifest
would also need a deliberate export/import. That data transfer is not performed
by this source package.

## Existing computer: migrate from chicago-taxi-trust to ARTEFACT_TEST

This section is for the original laptop where the application already runs.

1. Wait for any active Airflow run to finish.
2. In the OLD project terminal, run:

    docker compose stop

3. Keep the old folder as a backup.
4. Extract the new ARTEFACT_TEST package into a SEPARATE folder.
5. Copy your existing .env from the old folder into ARTEFACT_TEST. If you have no
   .env, copy config/local.env.example to .env in the new folder.
6. Open ARTEFACT_TEST with VS Code > File > Open Folder.
7. Open Terminal > New Terminal and run:

    docker compose up -d --build

8. Wait for Airflow startup, then check:

    docker compose ps -a

9. Open the report. Existing published data should remain available because
   compose.yaml retains the same project name and named-volume definitions.
10. Run the 20 tests.
11. Trigger the DAG once to validate the reorganized code on the original data.
    Inspect Rerun verified after it succeeds.

Only one of the old/new copies should run at a time. The old code folder is a
backup; the named Docker volumes are shared by the same Compose project name.

## Submission checklist

- [ ] Fresh build succeeds on the target computer.
- [ ] Airflow imports the DAG without errors.
- [ ] All 20 tests pass, including all Spark tests.
- [ ] Live extraction, cleaning, aggregation, and validation succeed.
- [ ] All three layers appear in object storage.
- [ ] Report interval and totals are inspected.
- [ ] Repeat run is verified.
- [ ] README documents actual measurements and limitations.
- [ ] No tokens, .env, downloaded datasets, or Docker volumes are committed.

To submit a Git repository, install Git if needed, create your own empty remote
repository, and follow its displayed push instructions from the ARTEFACT_TEST
folder. Review git status before committing. The source includes .gitignore;
creating a remote repository and publishing it are separate from running locally.

