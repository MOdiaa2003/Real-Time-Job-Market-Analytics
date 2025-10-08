from pyspark.sql import SparkSession
from pyspark.sql.types import *
from pyspark.sql.functions import *
from pyspark.sql.avro.functions import from_avro
import random
from datetime import datetime, timedelta
import re
from data_used import job_family_groups
from pyspark.sql import functions as F
import os
from pyspark.sql.utils import AnalysisException
import math
from builtins import min as py_min, max as py_max

def create_spark_session():
    """Initialize Spark Session - spark-submit will configure master and resources"""
    spark = (SparkSession.builder
            .appName("RealTimeJobMatching")
            # No .master() - spark-submit sets this
            # No jars.packages - spark-submit sets this
            .config("spark.sql.adaptive.enabled", "false")
            .config("spark.streaming.stopGracefullyOnShutdown", "true")
            .config("spark.sql.crossJoin.enabled", "true")
            .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    return spark
# Define Schemas for Candidate and Job Post data
candidate_schema = StructType([
    StructField("candidate_id", StringType(), True),
    StructField("name", StringType(), True),
    StructField("gender", StringType(), True),
    StructField("date_of_birth", StringType(), True),
    StructField("nationality", StringType(), True),
    StructField("location", StringType(), True),
    StructField("graduation_year", IntegerType(), True),
    StructField("gpa", DoubleType(), True),
    StructField("education_level", StringType(), True),
    StructField("job_category", StringType(), True),
    StructField("current_title", StringType(), True),
    StructField("seniority", StringType(), True),
    StructField("experience_range", StringType(), True),
    StructField("current_company", StringType(), True),
    StructField("previous_companies", ArrayType(StringType()), True),
    StructField("previous_industries", ArrayType(StringType()), True),
    StructField("skills", ArrayType(StringType()), True),
    StructField("certifications", ArrayType(StringType()), True),
    StructField("current_salary", DoubleType(), True),
    StructField("timestamp", TimestampType(), True)
])

job_post_schema = StructType([
    StructField("post_id", StringType(), True),
    StructField("company", StringType(), True),
    StructField("category", StringType(), True),
    StructField("job_title", StringType(), True),
    StructField("application_method", StringType(), True),
    StructField("post_date", TimestampType(), True),
    StructField("deadline", TimestampType(), True),
    StructField("certifications", ArrayType(StringType()), True),
    StructField("skills_needed", ArrayType(StringType()), True),
    StructField("platform", StringType(), True),
    StructField("employment_type", StringType(), True),
    StructField("city", StringType(), True),
    StructField("country", StringType(), True),
    StructField("language", StringType(), True),
    StructField("work_mode", StringType(), True),
    StructField("industry", StringType(), True),
    StructField("detailed_experience_level", StringType(), True),
    StructField("salary", DoubleType(), True),
    StructField("years_experience", StringType(), True),
    StructField("timestamp", TimestampType(), True)
])

application_schema = StructType([
    StructField("application_id", StringType(), True),
    StructField("candidate_id", StringType(), True),
    StructField("post_id", StringType(), True),
    StructField("application_date", TimestampType(), True),
    StructField("compatibility_score", IntegerType(), True),
    StructField("status", StringType(), True),
    StructField("application_method", StringType(), True),
    StructField("match_reason", StringType(), True),
    StructField("timestamp", TimestampType(), True)
])



def parse_experience_range(exp_range: str):
    """
    Convert experience range string to numeric min and max values.
    Handles formats like:
        "0 years" → (0, 0)
        "0-1 years" → (0, 1)
        "10+ years" → (10, 20)
        "15+ years" → (15, 25)
        "3-5 years" → (3, 5)
        "3 years" → (3, 3)
    """
    if not exp_range:
        return 0, 0

    exp_range = exp_range.lower().strip()

    # Handle "10+ years" or "15+ years"
    if "+" in exp_range:
        base_years = int(re.findall(r'\d+', exp_range)[0])
        return base_years, base_years + 2  # Add buffer for "+" to define upper bound

    # Handle "3-5 years"
    if "-" in exp_range:
        numbers = re.findall(r'\d+', exp_range)
        if len(numbers) == 2:
            return int(numbers[0]), int(numbers[1])

    # Handle "3 years" or "0 years"
    numbers = re.findall(r'\d+', exp_range)
    if len(numbers) == 1:
        return int(numbers[0]), int(numbers[0])

    return 0, 0
def calculate_compatibility_score_udf(candidate_skills, candidate_category, candidate_exp, 
                                    candidate_seniority, candidate_salary,
                                    job_skills, job_category, job_exp, job_level, job_salary):
    """UDF to calculate compatibility score between candidate and job"""
    
    score = 0.0
    max_score = 100
    
    # 1. Category Match (25 points) - MUST MATCH
    if candidate_category == job_category:
        score += 25
    else:
        return 0
    
    # 2. Skills Match (30 points)
    if job_skills and candidate_skills:
        candidate_skills_set = set([s.lower() for s in candidate_skills])
        job_skills_set = set([s.lower() for s in job_skills])
        
        skills_intersection = candidate_skills_set.intersection(job_skills_set)
        if job_skills_set:
            skills_score = (len(skills_intersection) / len(job_skills_set)) * 30
            score += skills_score if skills_score <= 30 else 30
    
    # 3. Experience Match (20 points)
    cand_min_exp, _ = parse_experience_range(candidate_exp)
    job_min_exp, _ = parse_experience_range(job_exp)
    
    if cand_min_exp >= job_min_exp:
        exp_score = 20
    else:
        denominator = py_max(1, job_min_exp)  # Use py_max
        exp_score = (cand_min_exp / denominator) * 15
        exp_score = py_max(0, exp_score)  # Use py_max
    score += exp_score
    
    # 4. Seniority Level Match (15 points)
    seniority_mapping = {
        "intern": 1, "junior": 2, "associate": 3, "mid": 4, "senior": 5,
        "staff": 6, "lead": 7, "manager": 8, "principal": 9, "consultant": 10,
        "architect": 11, "specialist": 12, "analyst": 13, "coordinator": 14,
        "representative": 15, "administrator": 16, "engineer": 17, "head": 18,
        "director": 19, "vp": 20, "chief": 21
    }
    
    cand_seniority_str = str(candidate_seniority).lower() if candidate_seniority else 'mid level'
    job_level_str = str(job_level).lower() if job_level else 'mid level'
    
    cand_level = seniority_mapping.get(cand_seniority_str, 3)
    job_level_num = seniority_mapping.get(job_level_str, 3)
    
    if cand_level >= job_level_num:
        seniority_score = 15
    else:
        denominator = py_max(1, job_level_num)  # Use py_max
        seniority_score = (cand_level / denominator) * 10
        seniority_score = py_max(0, seniority_score)  # Use py_max
    score += seniority_score
    
    # 5. Salary Expectations (10 points)
    current_salary = candidate_salary if candidate_salary else 0
    job_salary_val = job_salary if job_salary else 0
    
    if job_salary_val >= current_salary * 1.2:
        salary_score = 10
    elif job_salary_val == current_salary:
        salary_score = 8
    elif job_salary_val >= current_salary * 0.9:
        salary_score = 6
    elif job_salary_val >= current_salary * 0.7:
        salary_score = 3
    else:
        salary_score = 0
    
    score += salary_score
    
    # Return capped score using math.floor instead of round
    final_score = int(math.floor(score + 0.5))  # Manual rounding
    return final_score if final_score <= max_score else max_score

def generate_match_reason_udf(candidate_skills, candidate_category, candidate_exp, 
                            candidate_seniority, job_skills, job_category, job_exp, job_level):
    """UDF to generate match reason"""
    
    reasons = []
    
    # Category match
    if candidate_category == job_category:
        reasons.append("Same career field")
    
    # Skills match
    if candidate_skills and job_skills:
        candidate_skills_set = set([s.lower() for s in candidate_skills])
        job_skills_set = set([s.lower() for s in job_skills])
        common_skills = candidate_skills_set.intersection(job_skills_set)
        if len(common_skills) >= 3:
            reasons.append(f"Strong skills match in {', '.join(list(common_skills)[:3])}")
    
    # Experience level
    cand_min_exp, _ = parse_experience_range(candidate_exp)
    job_min_exp, _ = parse_experience_range(job_exp)
    if cand_min_exp >= job_min_exp:
        reasons.append("Meets experience requirements")
    
    # Seniority
    if candidate_seniority and job_level:
        if str(candidate_seniority).lower() in str(job_level).lower():
            reasons.append("Appropriate seniority level")
    
    if not reasons:
        reasons.append("Career growth opportunity")
    
    return "; ".join(reasons[:3])

def determine_application_status_udf(compatibility_score, application_date, post_date):
    """UDF to determine application status based on compatibility and timing"""
    
    # Handle None/null values
    if not application_date or not post_date:
        return 'Applied'
    
    # Convert both to datetime.date for comparison
    # application_date might be date, post_date might be datetime
    try:
        if hasattr(application_date, 'date'):
            app_date = application_date.date()
        else:
            app_date = application_date
            
        if hasattr(post_date, 'date'):
            post_dt = post_date.date()
        else:
            post_dt = post_date
        
        days_after_post = (app_date - post_dt).days
    except (AttributeError, TypeError):
        # Fallback if conversion fails
        days_after_post = 0
    
    # Determine status based on score and timing
    if compatibility_score >= 80 and days_after_post <= 7:
        status_options = ['Under Review', 'Interview Scheduled', 'Shortlisted']
    elif compatibility_score >= 60:
        status_options = ['Applied', 'Under Review', 'Shortlisted']
    else:
        status_options = ['Applied', 'Under Review', 'Rejected']
    
    return random.choice(status_options)

def process_real_time_applications():
    """Main function to process real-time job applications"""
    
    spark = create_spark_session()
    
    # Register UDFs
    calculate_compatibility_udf = udf(calculate_compatibility_score_udf, IntegerType())
    generate_reason_udf = udf(generate_match_reason_udf, StringType())
    determine_status_udf = udf(determine_application_status_udf, StringType())
    
    # Read candidate data from Kafka
    candidate_stream = (spark
        .readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "kafka_job:29092")
        .option("subscribe", "candidate_info")
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
        .select(from_json(col("value").cast("string"), candidate_schema).alias("candidate"))
        .select("candidate.*")
        .withWatermark("timestamp", "2 minutes"))
    
    # Read job post data from Kafka
    job_stream = (spark
        .readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "kafka_job:29092")
        .option("subscribe", "job_posts")
        .option("startingOffsets", "earliest")
         .option("failOnDataLoss", "false")
        .load()
        .select(from_json(col("value").cast("string"), job_post_schema).alias("job"))
        .select("job.*")
        .withWatermark("timestamp", "2 minutes"))
   

    
        # Convert dict into Spark DataFrame for mapping
    job_family_df = spark.createDataFrame(
        [(cat, fam) for fam, cats in job_family_groups.items() for cat in cats],
        ["category", "family_group"]
    )

    # Enrich candidate categories with family_group
    candidates_enriched = (
        candidate_stream
        .join(job_family_df.withColumnRenamed("category", "candidate_category"),
            candidate_stream["job_category"] == F.col("candidate_category"),
            "left")
        .withColumnRenamed("family_group", "candidate_family_group")
    )

    # Enrich job posts with family_group
    jobs_enriched = (
        job_stream
        .join(job_family_df.withColumnRenamed("category", "job_post_category"),
            job_stream["category"] == F.col("job_post_category"),
            "left")
        .withColumnRenamed("family_group", "job_post_family_group")
    )

    # ✅ Join only if both are in the same family group
    applications_stream = (
        candidates_enriched
        .join(
            jobs_enriched,
            candidates_enriched["candidate_family_group"] == jobs_enriched["job_post_family_group"],
            "inner"
        )
        .withColumn("compatibility_score", 
                calculate_compatibility_udf(
                    col("skills"), col("job_category"), col("experience_range"),
                    col("seniority"), col("current_salary"),
                    col("skills_needed"), col("category"), col("years_experience"),
                    col("detailed_experience_level"), col("salary")
                ))
        .filter(col("compatibility_score") >= 30)  # Minimum compatibility threshold
        .withColumn("apply_probability", 
                when(col("compatibility_score") >= 70, 0.8)
                .when(col("compatibility_score") >= 50, 0.5)
                .when(col("compatibility_score") >= 30, 0.2)
                .otherwise(0.0))
        .withColumn("should_apply", expr("rand() < apply_probability"))
        .filter(col("should_apply") == True)
        .withColumn("days_after_post", expr("rand() * datediff(deadline, post_date)")) \
    .withColumn(
        "application_date",
        expr("""
            timestampadd(
                SECOND,
                cast(rand() * 86400 as int),  -- random seconds (0–86400 = 24h)
                date_add(post_date, cast(days_after_post as int))
            )
        """))
        .withColumn("match_reason",
                generate_reason_udf(
                    col("skills"), col("job_category"), col("experience_range"),
                    col("seniority"), col("skills_needed"), col("category"), 
                    col("years_experience"), col("detailed_experience_level")
                ))
        .withColumn("status",
                determine_status_udf(
                    col("compatibility_score"), col("application_date"), col("post_date")
                ))
        .withColumn("application_id", 
                concat(col("candidate_id"), lit("_"), col("post_id"), lit("_"), 
                        expr("substring(rand(), 3, 6)")))
        .select(
            col("application_id"),
            col("candidate_id"),
            col("post_id"),
            col("application_date"),
            col("compatibility_score"),
            col("status"),
            col("application_method"),
            col("match_reason"),
            current_timestamp().alias("timestamp"),
            col("job_post_family_group")
        )
    )

    
    
    # Write applications to console for debugging
    console_query = (applications_stream
        .writeStream
        .outputMode("append")
        .format("console")
        .option("truncate", "false")
        .option("numRows", 10)
        .start())
    
    # Write applications to Kafka topic
    # Use /tmp inside container for checkpoints (temporary)
    kafka_query = (applications_stream
        .select(to_json(struct("*")).alias("value"))
        .writeStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "kafka_job:29092")
        .option("topic", "job_applications")
        .option("kafka.allow.auto.create.topics", "true") \
        .option("checkpointLocation", "/tmp/checkpoints/kafka_applications")  # Linux path
        .outputMode("append")
        .start())
    
    # Wait for all streams to terminate
    spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    process_real_time_applications()
