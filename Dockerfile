FROM apache/airflow:2.11.0-python3.11
USER root
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl \
    && rm -rf /var/lib/apt/lists/*
# Keep Spark/report dependencies separate from Airflow's constrained environment.
RUN python -m venv /opt/pipeline-env
COPY requirements.txt /tmp/pipeline-requirements.txt
RUN /opt/pipeline-env/bin/pip install --no-cache-dir -r /tmp/pipeline-requirements.txt
RUN mkdir -p /opt/spark-jars \
    && curl -fSL --retry 3 https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar -o /opt/spark-jars/hadoop-aws.jar \
    && curl -fSL --retry 3 https://repo.maven.apache.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar -o /opt/spark-jars/aws-sdk.jar
COPY --chown=airflow:root src /opt/project/src
COPY --chown=airflow:root dags /opt/airflow/dags
COPY --chown=airflow:root tests /opt/project/tests
ENV PYTHONPATH=/opt/project/src SPARK_LOCAL_IP=127.0.0.1
USER airflow
