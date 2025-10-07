# 💼 JobStream Analytics  

A complete **real-time data engineering project** that simulates a live job market — including job postings, candidate profiles, and job applications — with **real-time analytics using Kafka, Spark, PostgreSQL, and Streamlit**.

---

## 🚀 Project Overview

**JobStream Analytics** demonstrates an **end-to-end real-time data pipeline** where multiple producers stream job-related data into Kafka topics.  
Spark Structured Streaming processes and aggregates the data, while a **Streamlit dashboard** visualizes it live.

---

## 🧩 Architecture

            ┌─────────────────────────┐
            │  Candidate Generator    │
            │  Job Post Generator     │
            └──────────┬──────────────┘
                       │
                       ▼
               ┌─────────────────┐
               │   Kafka Topics   │
               │ job_posts        │
               │ candidate_info   │
               │ job_applications │
               └────────┬────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │   Spark Streaming   │
             │ (joins & aggregates)│
             └────────┬────────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │  PostgreSQL / Parquet│
             └────────┬────────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │ Streamlit Dashboard │
             │ (Real-Time Insights)│
             └─────────────────────┘
📊 Dataset Summary
1. Job Categories & Titles

13 main job families (Technical, Business, Support, etc.)

300+ job titles by seniority and domain

Hierarchy: Category → Title → Skills

2. Skills Database

Technical (Python, Cloud, Security)

Business (Finance, Marketing, Strategy)

Soft (Leadership, Communication)

3. Certification Library

AWS, PMP, CISSP, CPA, CFA, etc.

0–5 certifications per role

4. Geographic Data

150+ global cities, country-language mappings

5. Employment Details

7 job types, 8 education levels, 3 work modes

50+ industries, 20 posting platforms

6. Company & Demographics

300+ global companies

Names, nationalities, GPA ranges, grad years

⚙️ Pipeline Scripts
1️⃣ job_post_generator.py

Generates realistic job posts and candidate profiles simultaneously, sending them to:

job_posts

candidate_info

Each job post contains:

Title, category, company, salary, work mode, location
Each candidate profile contains:

Education level, skills, experience, country

2️⃣ job_applications_generator.py

Generates job applications by linking candidates to job posts in:

job_applications topic

Fields include:

application_id, candidate_id, post_id, status, compatibility_score, timestamp

3️⃣ streamlit_dashboard.py

Consumes messages from Kafka and displays real-time analytics:

Application volume and trends

Compatibility score distribution

Education & employment insights

Global job market map

🧠 Tech Stack
Layer	Technology
Data Generation	Python, Faker
Messaging	Apache Kafka, Zookeeper
Processing	Apache Spark Structured Streaming
Storage	PostgreSQL
Visualization	Streamlit, Plotly
Containerization	Docker Compose
📈 Real-Time Workflow

Run Docker Compose:

docker-compose up -d


Start Kafka Topics:
(auto-created by generators)

Run Data Generators:

python job_post_generator.py
python job_applications_generator.py


Launch Dashboard:

streamlit run streamlit_dashboard.py


Watch live analytics update in real time.

🗂️ Folder Structure
📦 jobstream-analytics
 ┣ 📜 docker-compose.yml
 ┣ 📜 job_post_generator.py
 ┣ 📜 job_applications_generator.py
 ┣ 📜 streamlit_dashboard.py
 ┣ 📜 requirements.txt
 ┣ 📜 README.md
 ┗ 📂 data
    ┣ job_titles.csv
    ┣ skills.csv
    ┣ certifications.csv
    ┣ locations.csv
    ┗ companies.csv

💡 Use Cases

✅ HR Analytics Platform
✅ Real-time Job Market Simulation
✅ Recruitment System Prototyping
✅ Stream Processing Demonstration
✅ Data Engineering Portfolio Project

👤 Author

Mohamed Ahmed Diaa
📍 Cairo, Egypt
📧 mdiaa44359@gmail.com

🔗 LinkedIn

💻 GitHub
