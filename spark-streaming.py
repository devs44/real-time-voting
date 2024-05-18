from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StringType, StructField, TimestampType, IntegerType
from pyspark.sql.functions import from_json, col
from pyspark.sql.functions import sum as _sum

if __name__ == '__main__':
    # Initialize Spark Session with Kafka and PostgreSQL configurations
    spark = (SparkSession.builder
         .appName("RealtimeVotingEngineering")
         .config('spark.jars', 'path/to/spark-sql-kafka-0-10_2.13-3.5.0.jar,path/to/other/required-jars.jar')
         .config('spark.jars', 'D:/projects/Data Engineer/demo/postgresql-42.7.3.jar')
         .config('spark.sql.adaptive.enable', 'false')
         .getOrCreate())



    # Define the schema for the vote data
    vote_schema = StructType([
        StructField("voter_id", StringType(), True),
        StructField("candidate_id", StringType(), True),
        StructField("voting_time", TimestampType(), True),
        StructField("voter_name", StringType(), True),
        StructField("party_affiliation", StringType(), True),
        StructField("biography", StringType(), True),
        StructField("campaign_platform", StringType(), True),
        StructField("photo_url", StringType(), True),
        StructField("candidate_name", StringType(), True),
        StructField("date_of_birth", StringType(), True),
        StructField("gender", StringType(), True),
        StructField("nationality", StringType(), True),
        StructField("registration_number", StringType(), True),
        StructField("address", StructType([
            StructField("street", StringType(), True),
            StructField("city", StringType(), True),
            StructField("state", StringType(), True),
            StructField("country", StringType(), True),
            StructField("postcode", StringType(), True)
        ]), True),
        StructField("email", StringType(), True),
        StructField("phone_number", StringType(), True),
        StructField("cell_number", StringType(), True),
        StructField("picture", StringType(), True),
        StructField("registered_age", IntegerType(), True),
        StructField("vote", IntegerType(), True)
    ])
    
    # Read streaming data from Kafka
    votes_df = (spark.readStream
                .format('kafka')
                .option('kafka.bootstrap.servers', 'localhost:9092')
                .option('subscribe', 'votes_topic')
                .option('startingOffsets', 'earliest')
                .load()
                .selectExpr('CAST(value AS STRING)')
                .select(from_json(col("value"), vote_schema).alias("data"))
                .select('data.*'))
    
    # Data preprocessing: type casting and watermarking
    votes_df = votes_df.withColumn("voting_time", col("voting_time").cast(TimestampType())) \
                       .withColumn('vote', col('vote').cast(IntegerType()))
                       
    enriched_votes_df = votes_df.withWatermark("voting_time", "1 minute")
    
    # Aggregate votes per candidate
    votes_per_candidate = enriched_votes_df.groupBy("candidate_id", "candidate_name", "party_affiliation", "photo_url").agg(_sum("vote").alias("total_votes"))
    
    # Aggregate turnout by location (state)
    turnout_by_location = enriched_votes_df.groupBy("address.state").agg(_sum("vote").alias("total_votes"))
    
    # Write aggregated data to Kafka topics
    votes_per_candidate_to_kafka = votes_per_candidate.selectExpr("to_json(struct(*)) AS value") \
        .writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "localhost:9092") \
        .option("topic", "aggregated_votes_per_candidate") \
        .option("checkpointLocation", "D:/projects/Data Engineer/demo/checkpoints/checkpoint1") \
        .outputMode("update") \
        .start()
                        
    turnout_by_location_to_kafka = turnout_by_location.selectExpr("to_json(struct(*)) AS value") \
        .writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "localhost:9092") \
        .option("topic", "aggregated_turnout_by_location") \
        .option("checkpointLocation", "D:/projects/Data Engineer/demo/checkpoints/checkpoint2") \
        .outputMode("update") \
        .start()
        
    # Await termination for the streaming queries
    votes_per_candidate_to_kafka.awaitTermination()
    turnout_by_location_to_kafka.awaitTermination()
