import os    
applications_stream= (spark
        .readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "kafka_job:29092")
        .option("subscribe", "job_posts")
        .option("startingOffsets", "earliest")
        .load()
        .select(from_json(col("value").cast("string"), job_post_schema).alias("job"))
        .select("job.*")
   
 # Get PostgreSQL connection details from environment variables
    postgres_user = os.getenv("POSTGRES_USER", "my_job")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "postgres")
    postgres_host = os.getenv("POSTGRES_HOST", "my_postgres")  # Docker service name
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    postgres_db = os.getenv("POSTGRES_DB", "mydb")
    
    jdbc_url = f"jdbc:postgresql://{postgres_host}:{postgres_port}/{postgres_db}"
    
    # Write to PostgreSQL
    def write_to_postgresql(batch_df, batch_id):
        """Write each micro-batch to PostgreSQL"""
        if batch_df.count() > 0:
            try:
                (batch_df
                 .write
                 .format("jdbc")
                 .option("url", jdbc_url)
                 .option("dbtable", "job_applications")
                 .option("user", postgres_user)
                 .option("password", "postgres")
                 .option("driver", "org.postgresql.Driver")
                 .mode("append")
                 .save())
                print(f"Batch {batch_id}: Successfully wrote {batch_df.count()} records to PostgreSQL")
            except Exception as e:
                if "does not exist" in str(e).lower():
                    print(f"Batch {batch_id}: Creating table job_applications...")
                    (batch_df
                     .write
                     .format("jdbc")
                     .option("url", jdbc_url)
                     .option("dbtable", "job_applications")
                     .option("user", "my_job")
                     .option("password", "postgres")
                     .option("driver", "org.postgresql.Driver")
                     .mode("overwrite")
                     .save())
                    print(f"Batch {batch_id}: Table created and data written")
                else:
                    print(f"Batch {batch_id}: Error writing to PostgreSQL - {str(e)}")
                    raise e
    
    postgres_query = (applications_stream
        .writeStream
        .foreachBatch(write_to_postgresql)
        .option("checkpointLocation", "/tmp/checkpoints/postgres_applications")
        .start())



