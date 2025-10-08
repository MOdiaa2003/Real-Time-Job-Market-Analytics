import random
import numpy as np, datetime
import psycopg2
import os
from dotenv import load_dotenv
import time
import json
from kafka import KafkaProducer
import re
import uuid
from data_used import top_300_unique, job_titles, job_certifications, jobs_skills
from data_used import num_skills_needed, num_certifications_needed
from data_used import job_posting_platforms, employment_types
from data_used import country_languages, location, work_modes, industries
from data_used import  category_to_experience ,matching_keywords,employment_rules 
from data_used import salary_ranges_per_year, level_to_years, experience_years
from data_used import apply_methods
from data_used import male_names,female_names,years,nationalities,Gpa
from data_used import education_levels

def get_location_by_industry(industry=None):
    """
    Returns realistic location based on industry geographic hubs
    """
    industry_location_weights = {
        # Tech industries - heavily North American
        "Information Technology": {
            "North America": 45, "Europe": 30, "Asia": 20, "Oceania": 3, "South America": 1, "Africa": 1
        },
        "Software & Internet": {
            "North America": 45, "Europe": 35, "Asia": 15, "Oceania": 3, "South America": 1, "Africa": 1
        },
        "Artificial Intelligence": {
            "North America": 50, "Europe": 35, "Asia": 10, "Oceania": 3, "South America": 1, "Africa": 1
        },
        "Cybersecurity": {
            "North America": 50, "Europe": 30, "Asia": 15, "Oceania": 3, "South America": 1, "Africa": 1
        },
        "Gaming": {
            "North America": 40, "Europe": 30, "Asia": 25, "Oceania": 3, "South America": 1, "Africa": 1
        },
        "E-Commerce": {
            "North America": 45, "Europe": 25, "Asia": 25, "Oceania": 3, "South America": 1, "Africa": 1
        },
        
        # Finance - global but concentrated in financial hubs
        "Financial Services": {
            "North America": 40, "Europe": 35, "Asia": 20, "Oceania": 3, "South America": 1, "Africa": 1
        },
        "Banking": {
            "North America": 35, "Europe": 35, "Asia": 25, "Oceania": 3, "South America": 1, "Africa": 1
        },
        "Insurance": {
            "North America": 40, "Europe": 30, "Asia": 25, "Oceania": 3, "South America": 1, "Africa": 1
        },
        
        # Healthcare - more distributed
        "Healthcare": {
            "North America": 40, "Europe": 30, "Asia": 25, "Oceania": 3, "South America": 1, "Africa": 1
        },
        "Pharmaceuticals": {
            "North America": 45, "Europe": 35, "Asia": 15, "Oceania": 3, "South America": 1, "Africa": 1
        },
        "Biotechnology": {
            "North America": 50, "Europe": 30, "Asia": 15, "Oceania": 3, "South America": 1, "Africa": 1
        },
        
        # Manufacturing - Asia has strong presence
        "Manufacturing": {
            "North America": 25, "Europe": 25, "Asia": 45, "Oceania": 2, "South America": 2, "Africa": 1
        },
        "Automotive": {
            "North America": 30, "Europe": 35, "Asia": 30, "Oceania": 2, "South America": 2, "Africa": 1
        },
        
        # Energy & Resources - specific regional concentrations
        "Energy": {
            "North America": 35, "Europe": 25, "Asia": 30, "Oceania": 5, "South America": 3, "Africa": 2
        },
        "Oil & Gas": {
            "North America": 30, "Europe": 25, "Asia": 25, "Oceania": 5, "South America": 10, "Africa": 5
        },
        "Mining & Metals": {
            "North America": 25, "Europe": 20, "Asia": 30, "Oceania": 10, "South America": 10, "Africa": 5
        },
        
        # Default for other industries
        "default": {
            "North America": 35, "Europe": 30, "Asia": 25, "Oceania": 5, "South America": 3, "Africa": 2
        }
    }

    if industry and industry in industry_location_weights:
        weights_dict = industry_location_weights[industry]
    else:
        weights_dict = industry_location_weights["default"]

    continents = list(weights_dict.keys())
    weights = list(weights_dict.values())
    continent = random.choices(continents, weights=weights, k=1)[0]
    
    loc = random.choice(location[continent])
    city, country = [part.strip() for part in loc.split(",")]
    
    return continent, city, country

# More sophisticated version with age consideration
def get_education_by_age_group(age=None):
    """
    Returns education level with probabilities that vary by age group
    Younger generations tend to have higher education levels
    """
    education_levels = [
        "High School Diploma",
        "Associate Degree", 
        "Bachelor's Degree",
        "Master's Degree",
        "MBA (Master of Business Administration)",
        "Doctorate (PhD)",
        "Professional Degree (MD, JD, etc.)",
        "Other"
    ]
    
    if age is None:
        age = random.randint(20, 65)
    
    # Different probability distributions by age group
    if age < 25:
        # Young adults, many still in college
        weights = [40, 20, 25, 5, 2, 1, 2, 5]
    elif age < 35:
        # Early career, more advanced degrees
        weights = [25, 15, 30, 15, 5, 3, 4, 3]
    elif age < 50:
        # Mid-career
        weights = [30, 15, 25, 12, 6, 4, 5, 3]
    else:
        # Older generation
        weights = [45, 15, 20, 8, 4, 2, 3, 3]
    
    return random.choices(education_levels, weights=weights, k=1)[0]
def extract_max_years(years_exp: str) -> int:
    """
    Extract the maximum years from experience string.
    Examples:
        "3-5 years" → 5
        "10+ years" → 12 (10 + buffer)
        "0-2 years" → 2
        "15-20 years" → 20
    """
    if "+" in years_exp:
        # e.g., "10+ years"
        base_years = int(re.findall(r'\d+', years_exp)[0])
        return base_years + 2  # Add buffer for "+"
    elif "-" in years_exp:
        # e.g., "7-9 years"
        max_years = int(years_exp.split('-')[1].split()[0])
        return max_years
    else:
        # e.g., "3 years"
        match = re.search(r'\d+', years_exp)
        if match:
            return int(match.group())
        return 0

def estimate_companies(experience_str: str) -> int:
    """
    Estimate number of previous companies based on experience range.
    Returns at least 1 for non-entry roles, except Internship/Entry Level.
    """

    years = 0

    # --- Parse years from string ---
    if "-" in experience_str:   # e.g. "7-9 years"
        years = int(experience_str.split('-')[1].split()[0])
    elif "+" in experience_str: # e.g. "10+ years"
        years = int(re.findall(r'\d+', experience_str)[0]) + 2  # add a buffer for "+"
    else:                       # e.g. "3 years"
        match = re.search(r'\d+', experience_str)
        if match:
            years = int(match.group())
    
    # --- Map years → number of previous companies ---
    if years == 0:
        return random.randint(0, 1)   # Internship, Entry Level
    elif years <= 2:
        return random.randint(0, 2)   # Junior
    elif years <= 5:
        return random.randint(1, 3)   # Analyst, Specialist, Consultant, Engineer
    elif years <= 7:
        return random.randint(2, 4)   # Mid-level
    elif years <= 10:
        return random.randint(3, 5)   # Senior, Lead, Architect
    elif years <= 15:
        return random.randint(4, 6)   # Director, Principal, Head
    elif years <= 20:
        return random.randint(5, 8)   # VP
    else:
        return random.randint(6, 10)  # C-level, Executives

# === Kafka Producer Connection ===
def connect_kafka():
    producer = KafkaProducer(
        bootstrap_servers=os.getenv("KAFKA_ADVERTISED_LISTENERS").replace("PLAINTEXT://", ""),
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8")
    )
    return producer


def get_salary_range(det_level_exp: str, salary_dict: dict):
    for key in salary_dict:
        if key.lower() in det_level_exp.lower():
            return (salary_dict[key], key)   # tuple

    return ({"min": 0, "max": 0}, None)     # fallback



def detect_seniority(title):
    """Detect seniority keyword in a title"""
    for keyword, level in matching_keywords.items():
        if keyword.lower() in title.lower():
            return level
    return "Mid Level"  # default if no keyword found

def get_experience_from_title(title: str, allowed_levels: list) -> str:
    title_lower = title.lower()

    # 🔹 Executives (C-Level, VP, Chief, Director, Head)
    if any(word in title_lower for word in ["chief", "cxo", "cfo", "cio", "cto", "cmo", "cco", "vp", "vice president", "director", "head"]):
        return "C-Level Executive (CXO)" if "chief" in title_lower or "cxo" in title_lower else "Director/VP"
    
    # 🔹 Managers,Heads & Leads
    if "Head" in title_lower:
        return "Head"
   
    if "manager" in title_lower:
        return "Manager"
    if "lead" in title_lower:
        return "Lead"

    # 🔹 Seniors
    if "senior" in title_lower or "sr." in title_lower:
        return "Senior"

    # 🔹 New positions
    if "staff" in title_lower:
        return "Staff"
    if "principal" in title_lower:
        return "Principal"
    if "consultant" in title_lower:
        return "Consultant"
    if "architect" in title_lower:
        return "Architect"
    if "specialist" in title_lower:
        return "Specialist"
    if "analyst" in title_lower:
        return "Analyst"
    if "coordinator" in title_lower:
        return "Coordinator"
    if "representative" in title_lower:
        return "Representative"
    if "administrator" in title_lower:
        return "Administrator"
    if "engineer" in title_lower:
        return "Engineer"

    # 🔹 Mid-level default (Engineer, Analyst, Developer without junior/senior)
    if any(word in title_lower for word in ["engineer", "developer", "analyst", "architect", "consultant"]) \
            and not any(word in title_lower for word in ["junior", "intern", "entry", "senior", "lead", "chief", "vp", "director", "head"]):
        return "Mid Level"

    # 🔹 Junior / Entry / Interns
    if "junior" in title_lower:
        return "Junior"
    if "entry" in title_lower:
        return "Entry Level"
    if "intern" in title_lower or "graduate" in title_lower:
        return "Internship"

    # Default fallback if nothing matches
    return random.choice(allowed_levels)
# === Generate one job post ===
def generate_job_post():
    post_id = str(uuid.uuid4())
    random_company = random.choice(top_300_unique)
    app_method = random.choice(apply_methods)

    start, end = datetime.datetime(2025, 1, 1), datetime.datetime(2028, 12, 31, 23, 59, 59)
    total_seconds = int((end - start).total_seconds())
    rand_seconds = np.random.randint(total_seconds)
    post_dt = start + datetime.timedelta(seconds=rand_seconds)

    rand_days = np.random.randint(5, 30)  # deadline offset
    deadline_dt = post_dt + datetime.timedelta(days=rand_days)
    category = random.choice(list(job_titles.keys()))
    title = random.choice(job_titles[category])
    seniority = detect_seniority(title)
    min_val, max_val = num_certifications_needed[category]
    random_value = random.randint(min_val, max_val)
    certs = random.sample(job_certifications[category], random_value)

    skills_needed = random.sample(jobs_skills[category], num_skills_needed[category])
    posted_platform = random.choice(job_posting_platforms)
    # Pick allowed employment type based on seniority
    allowed_types = employment_rules.get(seniority, ["Full-time", "Contract"])
    emp_type = random.choice(allowed_types)

    mode = random.choice(work_modes)
    industry = random.choice(industries)
    continent, city, country=get_location_by_industry(industry)
    language = random.choice(country_languages[country])
    if emp_type=="Internship":
        det_level_exp="Internship"
    else:
      det_level_exp = get_experience_from_title(title, category_to_experience[category])

    salary_range, matched_key  = get_salary_range(det_level_exp, salary_ranges_per_year)
    salary = random.randint(salary_range["min"], salary_range["max"])

    years_category = level_to_years[matched_key]
    years_exp = random.choice(experience_years[years_category])

    return {
        "post_id" :post_id,
        "company": random_company,
        "category": category,
        "job_title": title,
        "application_method": app_method,
        "post_date": post_dt,
        "deadline": deadline_dt,
        "certifications": certs,
        "skills_needed": skills_needed,
        "platform": posted_platform,
        "employment_type": emp_type,
        "city": city,
        "country": country,
        "language": language,
        "work_mode": mode,
        "industry": industry,
        "detailed_experience_level": det_level_exp,
        "salary": salary,
        "years_experience": years_exp
    }

# === Connect to PostgreSQL ===
load_dotenv()
def connect_postgres():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

def create_candidate_table(conn):
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS candidate_info (
                candidate_id VARCHAR(50) PRIMARY KEY,
                name TEXT,
                gender TEXT,
                date_of_birth INT,
                nationality TEXT,
                location TEXT,
                graduation_year INT,
                GPA FLOAT,
                education_level TEXT,
                job_category TEXT,
                current_title TEXT,
                seniority TEXT,
                experience_range TEXT,
                current_company TEXT,
                previous_companies TEXT[],
                previous_industries TEXT[],
                skills TEXT[],
                certifications TEXT[],
                current_salary INT
            );
        """)
        conn.commit()
        cur.close()
# === Create Table ===
def create_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS job_posts (
            post_id VARCHAR(50) PRIMARY KEY,
            company TEXT,
            category TEXT,
            job_title TEXT,
            application_method TEXT,
            post_date TIMESTAMP,
            deadline TIMESTAMP,
            certifications TEXT[],
            skills_needed TEXT[],
            platform TEXT,
            employment_type TEXT,
            city TEXT,
            country TEXT,
            language TEXT,
            work_mode TEXT,
            industry TEXT,
            detailed_experience_level TEXT,
            salary INT,
            years_experience  TEXT

        );
    """)
    conn.commit()
    cur.close()

def insert_candidate(conn, candidate):
    cur = conn.cursor()
    
    query = """
        INSERT INTO candidate_info (candidate_id,
            name, gender, date_of_birth, nationality, location,
            graduation_year, GPA, education_level, job_category,
            current_title, seniority, experience_range, current_company,
            previous_companies, previous_industries, skills, certifications, current_salary
        ) VALUES (%s,%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::text[], %s::text[], %s::text[], %s::text[], %s);
    """
    
    values = (
        candidate["candidate_id"],
        candidate["name"], 
        candidate["gender"], 
        candidate["date_of_birth"],
        candidate["nationality"], 
        candidate["location"], 
        candidate["graduation_year"],
        candidate["GPA"], 
        candidate["education_level"], 
        candidate["job_category"],
        candidate["current_title"], 
        candidate["seniority"], 
        candidate["experience_range"],
        candidate["current_company"], 
        candidate["previous_companies"],      # Position 14 → %s::text[]
        candidate["previous_industries"],     # Position 15 → %s::text[]
        candidate["skills"],                  # Position 16 → %s::text[]
        candidate["certifications"],          # Position 17 → %s::text[]
        candidate["current_salary"]
    )
    
    cur.execute(query, values)
    conn.commit()
    cur.close()
# === Insert One Job Post ===
def insert_job_post(conn, job_post):
    cur = conn.cursor()
    query = """
    INSERT INTO job_posts (post_id,
        company, category, job_title, application_method, post_date, deadline,
        certifications, skills_needed, platform, employment_type,
         city, country, language, work_mode, industry,
       detailed_experience_level, salary, years_experience
    ) VALUES (%(post_id)s,
        %(company)s, %(category)s, %(job_title)s, %(application_method)s, %(post_date)s, %(deadline)s,
        %(certifications)s, %(skills_needed)s, %(platform)s, %(employment_type)s,
         %(city)s, %(country)s, %(language)s, %(work_mode)s, %(industry)s,
         %(detailed_experience_level)s, %(salary)s, %(years_experience)s
    )
    """
    cur.execute(query, job_post)
    conn.commit()
    cur.close()

def generate_candidate_info():
    gender = ["male", "female"]
    chosen_gender = random.choice(gender)
    candidate_id = str(uuid.uuid4())
    name = random.choice(male_names) if chosen_gender == "male" else random.choice(female_names)
    nat = random.choice(nationalities)
    continent = random.choice(list(location.keys()))
    loc = random.choice(location[continent])
    GPA = random.choice(Gpa)
    category = random.choice(list(job_titles.keys()))
    current_title = random.choice(job_titles[category])
    seniority = detect_seniority(current_title)
    years_category = level_to_years[seniority]
    years_exp = random.choice(experience_years[years_category])
    min_val, max_val = num_certifications_needed[category]
    random_value = random.randint(min_val, max_val)
    certs = random.sample(job_certifications[category], random_value)
    skills = random.sample(jobs_skills[category], num_skills_needed[category])

    if seniority == "Internship":
        curr_comp = ""
       
    else:
        curr_comp = random.choice(top_300_unique)
    # Extract the maximum years from experience range
    max_years_experience = extract_max_years(years_exp)
    current_year = 2025
    years_since_graduation = max_years_experience + random.randint(0, 2)  # Add small buffer
    Graduation_year = current_year - years_since_graduation
    DB = Graduation_year - 22    
    edu=get_education_by_age_group(2025-DB)
    num_prev_companies = int(estimate_companies(years_exp))
    prev_comp = [str(random.choice(top_300_unique)) for _ in range(num_prev_companies)]
    prev_industries = [str(random.choice(industries)) for _ in range(num_prev_companies)]

    # Get min and max salary
    salary_range = salary_ranges_per_year[seniority]
    min_salary = salary_range["min"]
    max_salary = salary_range["max"]

    # Generate random salary
    salary = random.randint(min_salary, max_salary)


    return {
        "candidate_id":candidate_id,
        "name": name,
        "gender": chosen_gender,
        "date_of_birth": DB,
        "nationality": nat,
        "location": loc,
        "graduation_year": Graduation_year,
        "GPA": GPA,
        "education_level": edu,
        "job_category": category,
        "current_title": current_title,
        "seniority": seniority,
        "experience_range": years_exp,
        "current_company": curr_comp,
        "previous_companies": prev_comp,
        "previous_industries": prev_industries,
        "skills": skills,
        "certifications": certs,
        "current_salary":salary
    }

# === Main Pipeline ===
if __name__ == "__main__":
    conn = connect_postgres()
    create_table(conn)
    create_candidate_table(conn)
    candidate_topic = "candidate_info"
    producer = connect_kafka()
    job_topic = "job_posts"  # 🔹 static name, can also load from .env if you want

    start_time = time.time()

    for i in range(1000):
        
        candidate = generate_candidate_info()
        # Insert into Postgres
        insert_candidate(conn, candidate)


        job_post = generate_job_post()

        # Insert into Postgres
        insert_job_post(conn, job_post)
        # Send to Kafka
        producer.send(candidate_topic, candidate)
        # Send to Kafka
        producer.send(job_topic, job_post)

        if (i + 1) % 100 == 0:
            print(f"✅ Inserted & Produced {i+1} job posts...")

    conn.close()
    producer.flush()
    producer.close()

    elapsed = time.time() - start_time
    print(f"🎯 Finished inserting + producing 1000 job posts in {elapsed:.2f} seconds")
import csv
import os
from dotenv import load_dotenv
conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
       port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
         user=os.getenv("POSTGRES_USER"),
         password=os.getenv("POSTGRES_PASSWORD")
    )

cur = conn.cursor()

# Export job_posts table
cur.execute("SELECT * FROM job_posts")
with open("job_posts.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([desc[0] for desc in cur.description])
    writer.writerows(cur.fetchall())

# Export candidate_profiles table
cur.execute("SELECT * FROM candidate_info")
with open("candidate_profiles.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([desc[0] for desc in cur.description])
    writer.writerows(cur.fetchall())

cur.close()
conn.close()
