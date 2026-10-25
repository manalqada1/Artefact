"""One manual DAG; only small status values are returned to Airflow."""
from datetime import datetime, timedelta
import logging
import subprocess
from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator


def stage(name):
    # Stream both output channels into the task logger so the original exception
    # appears in Airflow instead of only a generic CalledProcessError wrapper.
    with subprocess.Popen(
        ['/opt/pipeline-env/bin/python', '/opt/project/src/pipeline.py', name],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as process:
        for line in process.stdout:
            logging.info('[%s] %s', name, line.rstrip())
        return_code = process.wait()
    if return_code:
        raise AirflowException(
            f'Stage {name} failed with exit code {return_code}; see its error above.'
        )


with DAG(
    dag_id='chicago_taxi_trust',
    description='Taxi metrics with a visible data-quality trail',
    start_date=datetime(2023, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    default_args={'owner': 'taxi-project', 'retries': 0, 'execution_timeout': timedelta(minutes=30)},
    tags=['taxi', 'pyspark', 'data-quality'],
) as dag:
    steps = [PythonOperator(task_id=name, python_callable=stage, op_args=[name]) for name in (
        'check_storage', 'download_bronze', 'build_silver', 'build_gold', 'validate_and_publish'
    )]
    for upstream, downstream in zip(steps, steps[1:]):
        upstream >> downstream
