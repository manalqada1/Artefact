import os

def spark_session():
    from pyspark.sql import SparkSession
    jars = '/opt/spark-jars/hadoop-aws.jar,/opt/spark-jars/aws-sdk.jar'
    spark = (SparkSession.builder.master('local[2]').appName('ChicagoTaxiTrust')
             .config('spark.jars', jars)
             .config('spark.driver.memory', '2g')
             .config('spark.sql.shuffle.partitions', '4')
             .config('spark.sql.session.timeZone', 'UTC')
             .config('spark.sql.timestampType', 'TIMESTAMP_NTZ')
             .config('spark.sql.ansi.enabled', 'false')
             .config('spark.hadoop.fs.s3a.endpoint', os.environ['S3_ENDPOINT'])
             .config('spark.hadoop.fs.s3a.access.key', os.environ['S3_ACCESS_KEY'])
             .config('spark.hadoop.fs.s3a.secret.key', os.environ['S3_SECRET_KEY'])
             .config('spark.hadoop.fs.s3a.path.style.access', 'true')
             .config('spark.hadoop.fs.s3a.connection.ssl.enabled', 'false')
             .config('spark.hadoop.fs.s3a.aws.credentials.provider',
                     'org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider')
             .getOrCreate())
    spark.sparkContext.setLogLevel('WARN')
    return spark
